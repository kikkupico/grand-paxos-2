"""Panel layouts: posed mannequins, stand-in props and a camera per panel, rendered from the built island.

  ~/.local/bin/blender -b blender/paxos.blend -P tools/blender_panels.py -- V V-03 V-11 V-06

Needs blender/paxos.blend from tools/blender_buildings.py (the full, deterministic scene build). Reads
volumes/<vol>-shots.json: for each panel, the camera (loc, target, lens, clip_start), aspect and resolution, the objects to
hide, and the figures and stand-in props, all in Blender world coordinates. A z of "surface" (or "surface+1.6" for a
camera) stands on whatever is below the optional z_from height (default: from the sky); the resolved heights and each
figure's position in the frame are written back to the JSON, so a re-render reproduces the same frame.

Figures are the low-poly mannequin from tools/blender_mannequin.py, one colour per character, in a named pose
(POSES there), optionally carrying a scroll. Blocking lives in one collection per panel under "Panels", hidden from
renders and viewports; only the panel being rendered is shown, and blender/panels-<vol>.blend is saved with every
blocking collection hidden again (checked by reopening). Cameras sit in "Panel cameras", which renders nothing.

Output: renders/panels/<id>-layout.png, a plain Cycles render (path-traced light and shadow, no ink outlines). An
image model reads real lighting better than the earlier Eevee render with an outline pass, which looked like toon shading.
"""
import json, math, sys
from pathlib import Path
import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_terrain as bt
from blender_kit import Kit, mat, TAU                                                              # noqa: F401
import blender_props as bp
import blender_mannequin as mq

OUT = bt.ROOT / "renders" / "panels"
SAMPLES = 96

# ---------------------------------------------------------------- stand-in props (true scale, crude)
def scroll_closed(k, x, y, z, ang, m, knob):
    """Two rolls side by side on their rods, lying on a surface; the axis runs along `ang`."""
    c, s = math.cos(ang), math.sin(ang)
    for sd in (-1, 1):
        cx, cy = x - s * .05 * sd, y + c * .05 * sd
        bp.wheel(k, cx, cy, z + .045, ang, .045, .30, m, 10)
        for e in (-1, 1): bp.wheel(k, cx + c * .17 * e, cy + s * .17 * e, z + .045, ang, .018, .06, knob, 6)

def hourglass(k, x, y, z, m, frame):
    k.cyl(x, y, .07, z, z + .02, frame, 10); k.cyl(x, y, .07, z + .26, z + .28, frame, 10)
    k.frustum(x, y, .055, .008, z + .02, z + .14, m, 10); k.frustum(x, y, .008, .055, z + .14, z + .26, m, 10)
    for i in range(3):
        a = i * TAU / 3; k.cyl(x + .06 * math.cos(a), y + .06 * math.sin(a), .008, z + .02, z + .26, frame, 5)

def ink_pot(k, x, y, z, m): k.cyl(x, y, .035, z, z + .06, m, 10)
def pen(k, x, y, z, ang, m): k.beam((x - .09 * math.cos(ang), y - .09 * math.sin(ang), z + .01), (x + .09 * math.cos(ang), y + .09 * math.sin(ang), z + .01), .01, .01, m)
def slip(k, x, y, z, ang, m): k.beam((x, y, z), (x + .12 * math.cos(ang), y + .12 * math.sin(ang), z + .07), .14, .004, m)
def clay_slate(k, x, y, z, ang, m): k.box(x, y, z, z + .025, .20, .28, ang, m)
def table(k, x, y, z, ang, m):
    k.box(x, y, z + .70, z + .75, 1.2, .8, ang, m)
    c, s = math.cos(ang), math.sin(ang)
    for dx, dy in ((-.5, -.3), (-.5, .3), (.5, -.3), (.5, .3)):
        px, py = x + dx * c - dy * s, y + dx * s + dy * c
        k.box(px, py, z, z + .70, .08, .08, ang, m)
def crate(k, x, y, z, ang, m): k.box(x, y, z, z + .95, 1.3, 1.0, ang, m)
def abacus_prop(k, x, y, z, ang, m): k.box(x, y, z, z + .04, .45, .28, ang, m)
def water_clock(k, x, y, z, bronze):
    k.cyl(x, y, .14, z, z + .38, bronze, 12)
    k.cyl(x, y, .015, z + .38, z + .65, bronze, 6)
def basket(k, x, y, z, wicker): k.cyl(x, y, .24, z, z + .32, wicker, 12)

def brazier(k, x, y, z, ang, bronze, iron, fire_mat=None):
    for ba in (0, TAU / 3, 2 * TAU / 3):
        bx, by = math.cos(ang + ba), math.sin(ang + ba)
        k.box(x + 0.35 * bx, y + 0.35 * by, z, z + 0.85, 0.08, 0.08, ang + ba, iron)
    k.frustum(x, y, 0.25, 0.6, z + 0.75, z + 1.05, bronze, 12)
    k.ring(x, y, 0.55, 0.65, z + 1.02, z + 1.10, bronze, 12)
    if fire_mat:
        k.cone(x, y, 0.5, z + 1.05, z + 1.6, fire_mat, 8)

def oil_lamp_prop(k, x, y, z, ang, bronze, flame):
    k.cyl(x, y, 0.08, z, z + 0.05, bronze, 10)
    c, s = math.cos(ang), math.sin(ang)
    k.box(x + 0.08 * c, y + 0.08 * s, z + 0.02, z + 0.06, 0.08, 0.04, ang, bronze)
    k.cone(x + 0.12 * c, y + 0.12 * s, 0.025, z + 0.05, z + 0.11, flame, 6)

def horn_prop(k, x, y, z, ang, bronze):
    c, s = math.cos(ang), math.sin(ang)
    k.beam((x, y, z + 0.05), (x + 0.7 * c, y + 0.7 * s, z + 0.25), 0.035, 0.035, bronze)
    k.cone(x + 0.7 * c, y + 0.7 * s, 0.14, z + 0.2, z + 0.45, bronze, 8)

def perched_raven(k, x, y, z, ang, dark_mat, bronze):
    c, s = math.cos(ang), math.sin(ang)
    k.box(x, y, z + 0.05, z + 0.25, 0.16, 0.28, ang, dark_mat)
    k.cyl(x + 0.1 * c, y + 0.1 * s, 0.07, z + 0.20, z + 0.32, dark_mat, 8)
    k.cone(x + 0.16 * c, y + 0.16 * s, 0.03, z + 0.22, z + 0.30, dark_mat, 4)
    k.cyl(x - 0.04 * c, y - 0.04 * s, 0.022, z, z + 0.07, bronze, 6)

def flying_raven(k, x, y, z, ang, dark_mat):
    c, s = math.cos(ang), math.sin(ang)
    k.box(x, y, z, z + 0.12, 0.18, 0.40, ang, dark_mat)
    k.cone(x + 0.22 * c, y + 0.22 * s, 0.035, z + 0.02, z + 0.10, dark_mat, 4)
    k.box(x, y, z + 0.04, z + 0.07, 1.1, 0.25, ang + math.pi / 2, dark_mat)

def balance_beam(k, x, y, z, ang, wood, bronze, white_fire, smoke_mat):
    k.box(x, y, z, z + 1.8, 0.25, 0.25, ang, wood)
    k.cone(x, y, 0.18, z + 1.8, z + 2.05, bronze, 3)
    c, s = math.cos(ang), math.sin(ang)
    k.box(x, y, z + 2.05, z + 2.18, 0.12, 3.8, ang, wood)
    lx, ly = x - 1.7 * s, y + 1.7 * c
    k.cyl(lx, ly, 0.02, z + 1.4, z + 2.05, bronze, 4)
    k.frustum(lx, ly, 0.2, 0.45, z + 1.25, z + 1.48, bronze, 10)
    k.cone(lx, ly, 0.38, z + 1.48, z + 1.95, white_fire, 8)
    rx, ry = x + 1.7 * s, y - 1.7 * c
    k.cyl(rx, ry, 0.02, z + 1.4, z + 2.05, bronze, 4)
    k.frustum(rx, ry, 0.2, 0.45, z + 1.25, z + 1.48, bronze, 10)
    k.cone(rx, ry, 0.38, z + 1.48, z + 1.95, smoke_mat, 8)

def mini_ship(k, x, y, z, ang, wood):
    k.box(x, y, z, z + 0.03, 0.045, 0.16, ang, wood)
    k.cyl(x, y, 0.006, z + 0.03, z + 0.09, wood, 4)

def purse_prop(k, x, y, z, leather, gold_mat):
    k.cyl(x, y, 0.10, z, z + 0.14, leather, 8)
    k.cyl(x, y, 0.05, z + 0.14, z + 0.18, leather, 6)
    for dx, dy in ((-0.12, 0.04), (-0.08, -0.08), (-0.16, -0.03), (-0.04, -0.13)):
        k.cyl(x + dx, y + dy, 0.025, z, z + 0.012, gold_mat, 8)

def signet_slate(k, x, y, z, ang, wood, wax, seal_wax):
    k.box(x, y, z, z + 0.022, 0.20, 0.30, ang, wood)
    k.box(x, y, z + 0.018, z + 0.026, 0.16, 0.25, ang, wax)
    c, s = math.cos(ang), math.sin(ang)
    k.cyl(x - 0.09 * s, y + 0.09 * c, 0.032, z + 0.025, z + 0.033, seal_wax, 8)

# ---------------------------------------------------------------- scene helpers
def collection(name, parent):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in parent.children: parent.children.link(c)
    return c

def surface(scene, x, y, below=3000.0, skip=()):
    dg = bpy.context.evaluated_depsgraph_get(); origin = Vector((x, y, below))
    for _ in range(8):
        hit, loc, _, _, ob, _ = scene.ray_cast(dg, origin, Vector((0, 0, -1)))
        if not hit: return None
        if ob is None or ob.name not in skip: return loc.z
        origin = loc - Vector((0, 0, .01))
    return None

def use_cycles(scene):
    """Path-traced layouts: on the GPU (Metal) when there is one, denoised."""
    scene.render.engine = "CYCLES"; scene.cycles.samples = SAMPLES; scene.cycles.use_denoising = True
    scene.view_settings.view_transform = "AgX"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences; prefs.compute_device_type = "METAL"; prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type != "CPU"]
        for d in prefs.devices: d.use = d.type != "CPU" or not gpus
        scene.cycles.device = "GPU" if gpus else "CPU"
    except (KeyError, TypeError, AttributeError):
        scene.cycles.device = "CPU"
    return scene.cycles.device

# ---------------------------------------------------------------- one panel
def build_panel(scene, pid, spec, colors, top, cams):
    coll = collection(f"{pid} · blocking", top)
    for ob in list(coll.objects): bpy.data.objects.remove(ob, do_unlink=True)
    for f in spec["figures"]:                                                                       # every height first, before any figure can be hit
        x, y = f["xy"]
        f["z_resolved"] = round(surface(scene, x, y, below=f.get("z_from", 3000.0)) if f["z"] == "surface" else f["z"], 3)
    coll.hide_render = coll.hide_viewport = False                                                   # posing reads evaluated bones, so build in view
    for f in spec["figures"]:
        mq.place(scene, coll, *f["xy"], f["z_resolved"], f["facing_deg"], f.get("pose", "stand"), colors[f["color"]], f"{pid} · {f['id']}", f.get("carry"))
    wood, parchment, glass, ink = mat("Blocking · rod", "#6a4a2e"), mat("Blocking · parchment", "#efe3c2"), mat("Blocking · glass", "#bcd8d4", .2), mat("Blocking · ink", "#1c1512")
    terracotta, bronze, wicker = mat("Blocking · terracotta", "#bf7a50"), mat("Blocking · bronze", "#a57a3e"), mat("Blocking · wicker", "#b89e6c")
    iron, gold_mat = mat("Blocking · iron", "#36383e"), mat("Blocking · gold", "#d4af37")
    flame, white_fire = mat("Blocking · flame", "#ffaa33"), mat("Blocking · white_fire", "#ffffff")
    smoke_mat, raven_mat = mat("Blocking · smoke", "#2b2b2b"), mat("Blocking · raven", "#18181c")
    wax, seal_wax, leather = mat("Blocking · wax", "#d6c59b"), mat("Blocking · seal_wax", "#8a1c14"), mat("Blocking · leather", "#4a2e1b")
    k = Kit(f"{pid} · blocking props")
    for p in spec.get("props", []):
        x, y = p["xy"]
        z = surface(scene, x, y, below=p.get("z_from", 3000.0)) if p["z"] == "surface" else p["z"]
        p["z_resolved"] = round(z, 3)
        a = math.radians(p.get("angle_deg", 0))
        {"scroll_closed": lambda: scroll_closed(k, x, y, z, a, parchment, wood), "hourglass": lambda: hourglass(k, x, y, z, glass, wood),
         "ink_pot": lambda: ink_pot(k, x, y, z, ink), "pen": lambda: pen(k, x, y, z, a, wood), "slip": lambda: slip(k, x, y, z, a, parchment),
         "clay_slate": lambda: clay_slate(k, x, y, z, a, terracotta), "table": lambda: table(k, x, y, z, a, wood),
         "crate": lambda: crate(k, x, y, z, a, wood), "abacus": lambda: abacus_prop(k, x, y, z, a, wood),
         "water_clock": lambda: water_clock(k, x, y, z, bronze), "basket": lambda: basket(k, x, y, z, wicker),
         "brazier": lambda: brazier(k, x, y, z, a, bronze, iron, flame),
         "brazier_white": lambda: brazier(k, x, y, z, a, bronze, iron, white_fire),
         "brazier_smoke": lambda: brazier(k, x, y, z, a, bronze, iron, smoke_mat),
         "brazier_dark": lambda: brazier(k, x, y, z, a, bronze, iron, None),
         "oil_lamp": lambda: oil_lamp_prop(k, x, y, z, a, bronze, flame),
         "horn": lambda: horn_prop(k, x, y, z, a, bronze),
         "perched_raven": lambda: perched_raven(k, x, y, z, a, raven_mat, bronze),
         "flying_raven": lambda: flying_raven(k, x, y, z, a, raven_mat),
         "balance_beam": lambda: balance_beam(k, x, y, z, a, wood, bronze, white_fire, smoke_mat),
         "mini_ship": lambda: mini_ship(k, x, y, z, a, wood),
         "purse": lambda: purse_prop(k, x, y, z, leather, gold_mat),
         "signet_slate": lambda: signet_slate(k, x, y, z, a, wood, wax, seal_wax),
        }.get(p["kind"], lambda: None)()
    ob = k.finish(coll)
    c = spec["camera"]; lx, ly, lz = c["loc"]
    if isinstance(lz, str):                                                                         # "surface+1.6"
        lz = surface(scene, lx, ly, below=c.get("z_from", 3000.0), skip={ob.name}) + float(lz.split("+")[1]); c["z_resolved"] = round(lz, 3)
    old = bpy.data.objects.get(f"Cam · panel {pid}")
    if old:
        tgt = bpy.data.objects.get(old.name + " target"); bpy.data.objects.remove(old, do_unlink=True)
        if tgt: bpy.data.objects.remove(tgt, do_unlink=True)
    cam = bt.camera(f"Cam · panel {pid}", (lx, ly, lz), tuple(c["target"]), cams, lens=c["lens"])
    cam.data.clip_start = c.get("clip_start", .1)
    coll.hide_render = coll.hide_viewport = True
    return coll, cam

def render_panel(scene, pid, spec, coll, cam):
    OUT.mkdir(parents=True, exist_ok=True)
    hidden = [o for o in (bpy.data.objects.get(n) for n in spec.get("hide", [])) if o]
    for o in hidden: o.hide_render = True
    coll.hide_render = coll.hide_viewport = False
    scene.camera = cam; scene.render.resolution_x, scene.render.resolution_y = spec["resolution"]
    scene.render.image_settings.file_format = "PNG"; scene.render.image_settings.color_depth = "8"                 # 8-bit loads as display-space bytes
    bpy.context.view_layer.update()
    for f in spec["figures"]:                                                                       # where each figure's head lands in the frame
        v = world_to_camera_view(scene, cam, Vector((f["xy"][0], f["xy"][1], f["z_resolved"] + (.8 if f.get("pose") in mq.SEATED else 1.6))))
        f["screen"] = [round(v.x, 3), round(1 - v.y, 3)]; f["in_frame"] = bool(0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0)
        foot = world_to_camera_view(scene, cam, Vector((f["xy"][0], f["xy"][1], f["z_resolved"])))
        f["screen_h"] = round(abs(foot.y - world_to_camera_view(scene, cam, Vector((f["xy"][0], f["xy"][1], f["z_resolved"] + 1.75))).y), 4)   # a standing person's height, as a share of the frame
    dg = bpy.context.evaluated_depsgraph_get(); eye = cam.matrix_world.translation
    blocking = {o.name for o in coll.objects}
    def seen(pt, pad=.35):
        d = Vector(pt) - eye; L = d.length
        hit, loc, _, _, ob, _ = scene.ray_cast(dg, eye, d.normalized(), distance=L)
        return (not hit) or (ob is not None and ob.name in blocking) or (loc - eye).length >= L - pad
    for f in spec["figures"]:
        f["visible"] = bool(seen((f["xy"][0], f["xy"][1], f["z_resolved"] + (.7 if f.get("pose") in mq.SEATED else 1.45))))
    frame = cam.data.view_frame(scene=scene); m_ = cam.matrix_world
    near = []
    for u, v in ((.5, .5), (.1, .1), (.9, .1), (.1, .9), (.9, .9)):
        pt = m_ @ (frame[2] + (frame[1] - frame[2]) * u + (frame[3] - frame[2]) * v)
        hit, loc, _, _, ob, _ = scene.ray_cast(dg, eye, (pt - eye).normalized(), distance=spec["camera"].get("clear_m", 1.0))
        near.append(bool(hit) and not (ob is not None and ob.name in blocking))
    spec["lens_clear"] = not any(near)
    hit, loc, *_ = scene.ray_cast(dg, eye, (m_ @ (frame[2] + (frame[1] - frame[2]) * .5 + (frame[3] - frame[2]) * .5) - eye).normalized())
    spec["centre_clear_m"] = round((loc - eye).length, 1) if hit else None                          # nothing big right in front of the lens
    for p in spec.get("props", []):
        pz = p.get("z_resolved", p["z"])
        v = world_to_camera_view(scene, cam, Vector((p["xy"][0], p["xy"][1], pz + .05)))
        p["screen"] = [round(v.x, 3), round(1 - v.y, 3)]; p["in_frame"] = bool(0 <= v.x <= 1 and 0 <= v.y <= 1 and v.z > 0)
    spec["device"] = use_cycles(scene); out = OUT / f"{pid}-layout.png"
    scene.render.filepath = str(out); bpy.ops.render.render(write_still=True)
    coll.hide_render = coll.hide_viewport = True
    for o in hidden: o.hide_render = False
    return out

def main():
    args = sys.argv[sys.argv.index("--") + 1:]
    vol, ids = args[0], args[1:]
    path = bt.ROOT / "volumes" / f"{vol}-shots.json"; shots = json.loads(path.read_text())
    scene = bpy.context.scene
    top = collection("Panels", scene.collection); cams = collection("Panel cameras", scene.collection)
    for pid in ids or list(shots["panels"]):
        spec = shots["panels"][pid]
        coll, cam = build_panel(scene, pid, spec, shots["colors"], top, cams)
        out = render_panel(scene, pid, spec, coll, cam)
        print("PANEL", pid, out, "lens clear:", spec["lens_clear"], "centre clear to", spec["centre_clear_m"], "m;", "figures in frame:", sum(f["in_frame"] for f in spec["figures"]), "/", len(spec["figures"]),
              "visible:", sum(f["visible"] for f in spec["figures"]),
              "props in frame:", sum(p["in_frame"] for p in spec.get("props", [])), "/", len(spec.get("props", [])), "on", spec["device"])
    path.write_text(json.dumps(shots, ensure_ascii=False, indent=1))
    blend = bt.OUT / f"panels-{vol}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend), compress=True)
    bpy.ops.wm.open_mainfile(filepath=str(blend))                                                   # check the saved file keeps every blocking collection hidden
    shown = [c.name for c in bpy.data.collections.get("Panels").children if not (c.hide_render and c.hide_viewport)]
    print("SAVED", blend, "blocking collections hidden:", not shown, shown)

if __name__ == "__main__":
    main()
