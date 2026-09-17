"""Turn a panel's Blender layout into a comic panel with the Gemini API (gemini-3-pro-image).

  python3 tools/panel_images.py edit V-03 [--anchor <accepted panel>]   one attempt -> temp/panels/V-03-aN.jpg
  python3 tools/panel_images.py fix V-03 <attempt> "<what to change>"    refine an attempt
  python3 tools/panel_images.py score V-03 <attempt>                    layout-keeping score, and a side-by-side sheet
  python3 tools/panel_images.py accept V-03 <attempt>                   -> volumes/images/V-03.jpg (then run volume_panels.py)

Inputs: renders/panels/<id>-layout.png (from tools/blender_panels.py) as image 1, then the panel's reference sheets from
references/, then optionally an accepted panel as the style anchor. The prompt comes from volumes/<vol>-panels.json (scene,
notes) and volumes/<vol>-shots.json (what each colour-coded mannequin and stand-in prop becomes, and where it is in the
frame). Every prompt is written to temp/panels/<id>-aN.txt next to its image.

The score measures how much of the layout's line structure survives: the share of the layout's strongest edges that
have an edge in the generated image within a few pixels (at 480 px wide). The same measure against the generated
image flipped left-right is the baseline an unrelated composition gets. It catches reframing or lost architecture;
it can't judge canon (ledger form, marble, the verandah), which needs a person to look.
"""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageFilter, ImageOps

sys.path.insert(0, str(Path(__file__).resolve().parent))
from reference_sheets import call, ROOT

OUT, FINAL = ROOT / "temp" / "panels", ROOT / "volumes" / "images"
STYLE = ("vintage 1970s comic book illustration: bold black ink outlines, visible halftone dot shading, slightly aged newsprint paper "
         "texture, flat Mediterranean palette (aegean blue #136f9e, terracotta red #bf4a26, olive green #66722c, marble white, sand #f2e7cd, "
         "gold accents #c1912b, ink #1c1512); a Hellenistic Greek setting with ancient clothing and objects only")
SHEETS = {"IV-benches": "legislators: faces, costume, shoulder bags, ledgers", "IV-legislators": "legislators and priests: faces, costume, hourglass, stone seats",
          "IV-ledger": "the ledger: a parchment strip on two rods, closed and open (written top to bottom)", "IV-messengers": "messengers: costume, satchels, message scrolls",
          "IV-townsfolk": "townsfolk: costume and trades", "IV-symbols": "seals, tokens, emblems and pictograms", "III-props": "the glass hourglass, lantern and other props",
          "I-props": "scroll case, lamps and other props", "I-characters": "shepherds, goats and messengers", "III-characters": "navigators and townsfolk"}
CANON = ("Canon: every ledger is a single strip of parchment wound between two wooden rods, never a bound book or a single sheet: carried closed, "
         "it is two rolls side by side tied with a cord, their four rod-ends knobbed. It is written like a log: each entry is one line parallel to the rods, "
         "entries running top to bottom down the strip with no side-by-side columns, and open it is held upright, one rod across the top and one across the bottom. The Great Round is warm limestone ashlar and marble, not whitewash. "
         "Its ring wall is plain masonry with a row of square windows high up; the colonnaded verandah is inside the ring, never on the outside.")

def where(xy):
    x, y = xy
    h = "left" if x < .36 else ("right" if x > .64 else "centre")
    v = "foreground" if y > .7 else ("background" if y < .45 else "middle distance")
    return f"{v}, {h}; {round(100 * x)}% from the left, {round(100 * y)}% from the top"

def prompt_for(pid, anchor):
    vol = pid.split("-")[0]
    brief = {p["id"]: p for p in json.loads((ROOT / "volumes" / f"{vol}-panels.json").read_text())["panels"]}[pid]
    shot = json.loads((ROOT / "volumes" / f"{vol}-shots.json").read_text())["panels"][pid]
    people = [f for f in shot["figures"] if f.get("in_frame")]
    lines = [f"- the {f['color']} mannequin ({where(f['screen'])}): {f['label']}" for f in people]
    lines += [f"- the stand-in {p['kind'].replace('_', ' ')} ({where(p['screen'])}): {p['label']}" for p in shot["props"] if p.get("in_frame")]
    refs = [ROOT / "references" / f"{r}.jpg" for r in brief["refs"]]
    cam = shot["camera"]; (cx, cy, cz), (tx, ty, tz) = cam["loc"], cam["target"]
    cz = cam.get("z_resolved", cz) if isinstance(cz, str) else cz                                      # "surface+1.6", resolved by the layout render
    down = math.degrees(math.atan2(cz - tz, math.hypot(tx - cx, ty - cy)))
    heights = sorted(f["screen_h"] for f in people if f.get("screen_h"))
    camera = (f"The camera looks {'down' if down > 0 else 'up'} at about {abs(round(down))} degrees"
              + (f" from high above, so the scene is seen from above, not at eye level" if down > 20 else "") + ". "
              + (f"People are small in this view: a standing person is about {round(100 * heights[len(heights) // 2])}% of the image height "
                 f"(from {round(100 * heights[0])}% to {round(100 * heights[-1])}%); keep every person at that size. " if heights else ""))
    ref_text = "; ".join(f"image {i + 2} is the {SHEETS.get(r, r)} reference sheet" for i, r in enumerate(brief["refs"]))
    text = (f"Image 1 is a 3D layout render for one comic panel. Redraw it as a finished comic panel in the style of a {STYLE}.\n"
            f"Keep image 1's camera, framing, horizon and perspective exactly. {camera}Keep every piece of architecture, terrain, sea and sky where it is "
            "and at its size: the walls, gates, doors, windows, columns, seat rows, stairways and statues are the layout and must stay as laid out. "
            "Treat this as a careful tracing: the silhouettes and edges of image 1 are the drawing's skeleton. Do not widen, narrow or re-crop the view, "
            "do not move the horizon, and do not redesign or simplify any building: draw the architecture exactly as shaped in image 1. "
            "Replace only the render's flat 3D look with inked linework, halftone shading and hand-drawn texture. Draw no panel border or frame; the art runs to the image edges.\n"
            "The plain colour-coded mannequins and simple stand-in shapes in image 1 are placeholders. Replace each with a fully drawn character "
            "or object at the same place, size and facing, and draw nothing of the placeholder colours unless they suit the costume. "
            + "Each mannequin is already posed as its character: keep its pose, and give the character a facial expression that fits the scene. "
            +
            f"Draw exactly {len(people)} people, one for each mannequin listed below, each where its mannequin stands and at its mannequin's size, "
            "doing what the list says; add no other people anywhere in the image:\n"
            + "\n".join(lines) + "\n"
            f"Scene: {brief['scene']}\n"
            f"Draw characters and objects from the reference sheets ({ref_text}), matching their costume, faces and objects but not copying their layout.\n"
            + (f"Image {len(refs) + 2} is an accepted panel from the same book: match its drawing style, line weight, halftone and colour treatment, not its content.\n" if anchor else "")
            + f"{CANON} {brief.get('notes', '')}\n"
            "No speech balloons, captions, labels, numbers, panel borders or legible writing anywhere in the image.")
    images = [ROOT / "renders" / "panels" / f"{pid}-layout.png"] + refs + ([Path(anchor)] if anchor else [])
    return text, images, shot["aspect"]

def edges(path, w=480, share=.12):
    """The strongest `share` of edges, after a blur that removes halftone dots and paper grain."""
    im = Image.open(path).convert("L").filter(ImageFilter.GaussianBlur(3)); im = im.resize((w, round(w * im.height / im.width)))
    e = np.asarray(im.filter(ImageFilter.FIND_EDGES), float).ravel(); k = int(share * e.size)
    thr = max(np.partition(e, -k)[-k], 1.0)
    return (e >= thr).reshape(im.height, im.width)

def score(pid, attempt):
    lay = edges(ROOT / "renders" / "panels" / f"{pid}-layout.png"); gen_img = Image.open(attempt)
    def cover(gen):
        g = Image.fromarray((gen * 255).astype(np.uint8)).resize((lay.shape[1], lay.shape[0])).filter(ImageFilter.MaxFilter(7))
        return float((lay & (np.asarray(g) > 0)).sum() / max(lay.sum(), 1))
    tmp = OUT / "_flip.png"; ImageOps.mirror(gen_img).save(tmp)
    s, base = cover(edges(attempt)), cover(edges(tmp)); tmp.unlink()
    a = Image.open(ROOT / "renders" / "panels" / f"{pid}-layout.png").convert("RGB"); b = gen_img.convert("RGB").resize(a.size)
    sheet = Image.new("RGB", (a.width, a.height * 2)); sheet.paste(a, (0, 0)); sheet.paste(b, (0, a.height))
    sheet.resize((a.width // 2, a.height)).save(Path(attempt).with_name(Path(attempt).stem + "-vs-layout.jpg"), quality=85)
    return round(s, 3), round(base, 3)

def main():
    cmd, pid = sys.argv[1], sys.argv[2]; OUT.mkdir(parents=True, exist_ok=True)
    if cmd in ("edit", "fix"):
        n = 1 + len(list(OUT.glob(f"{pid}-a*[0-9].jpg"))); dst = OUT / f"{pid}-a{n}.jpg"
        anchor = sys.argv[sys.argv.index("--anchor") + 1] if "--anchor" in sys.argv else None
        text, images, aspect = prompt_for(pid, anchor)
        if cmd == "fix":
            src, change = Path(sys.argv[3]), sys.argv[4]
            text = (f"Image 1 is a comic panel; image 2 is the 3D layout it was drawn from. Keep image 1's drawing, style and composition, and change only this: "
                    f"{change}\nKeep the layout of image 2 (camera, architecture) and the rest of image 1 unchanged. {CANON} No legible writing.")
            images = [src, ROOT / "renders" / "panels" / f"{pid}-layout.png"]
        dst.write_bytes(call(text, images, aspect)); dst.with_suffix(".txt").write_text(text + "\n\nIMAGES: " + ", ".join(str(Path(p).resolve().relative_to(ROOT)) for p in images))
        print(dst, "score (layout kept, flipped baseline):", score(pid, dst))
    elif cmd == "score":
        print(score(pid, sys.argv[3]))
    elif cmd == "accept":
        FINAL.mkdir(parents=True, exist_ok=True)
        Image.open(sys.argv[3]).convert("RGB").save(FINAL / f"{pid}.jpg", quality=88); print(FINAL / f"{pid}.jpg")

if __name__ == "__main__":
    main()
