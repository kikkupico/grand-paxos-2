"""Stage 3a: the island terrain in Blender, built from maps/island-height.png and maps/island-sites.json.

  ~/.local/bin/blender -b -P tools/blender_terrain.py              build and save blender/paxos.blend
  ~/.local/bin/blender -b -P tools/blender_terrain.py -- --render  also render renders/terrain-*.png

The mesh is made directly from the heightmap (one vertex per pixel centre, true 1:1 heights), not with a
Displace modifier, so heights are exact and nothing depends on image UV orientation. Blender X = x - 5500,
Y = 4000 - y (north is +Y), Z = elevation in metres. Buildings, vegetation and props go on top later;
every site is an empty in a per-volume collection. Checks are written to blender/terrain-checks.json.
"""
import json, sys
from pathlib import Path
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HEIGHT = ROOT / "maps" / "island-height.png"
SITES = ROOT / "maps" / "island-sites.json"
OUT = ROOT / "blender"
RENDERS = ROOT / "renders"
HMIN, HMAX, CELL = -120.0, 480.0, 12.5
W, H = 11000.0, 8000.0
VOLUMES = {"I": "Disordered Sundials", "II": "Sleeping Guard", "III": "Traitors Among Admirals", "IV": "Passable Season",
           "V": "Part-time Parliament", "VI": "Ledger of Many Decrees", "VII": "Citadel of Iron Quorums",
           "VIII": "Quarries of the Roman Guilds", "IX": "Raft Monks"}

def hexrgb(h, a=1.0):
    h = h.lstrip("#")
    srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= .04045 else ((c + .055) / 1.055) ** 2.4 for c in srgb]
    return (*lin, a)

def collection(name, parent=None):
    c = bpy.data.collections.new(name)
    (parent or bpy.context.scene.collection).children.link(c)
    return c

def heights():
    img = bpy.data.images.load(str(HEIGHT))
    img.colorspace_settings.name = "Non-Color"
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    grey = px.reshape(h, w, 4)[::-1, :, 0]                      # Blender stores rows bottom-up; flip to north-first
    bpy.data.images.remove(img)
    return grey.astype(np.float64) * (HMAX - HMIN) + HMIN      # rows = y south, cols = x east

SKIRT_M = 600.0

def skirt(z):
    """Ease the outermost 600 m of seabed down to -120 m so the terrain has no visible table edge.
    Only open sea is touched; the checks run against the unmodified heightmap."""
    ny, nx = z.shape
    d = np.minimum.reduce(np.meshgrid(np.minimum(np.arange(ny), ny - 1 - np.arange(ny)),
                                      np.minimum(np.arange(nx), nx - 1 - np.arange(nx)), indexing="ij")) * CELL
    w = np.clip(1 - d / SKIRT_M, 0, 1) ** 2
    return np.where(z < 0, z * (1 - w) + HMIN * w, z)

def terrain_mesh(z):
    ny, nx = z.shape
    cols, rows = np.meshgrid(np.arange(nx), np.arange(ny))
    co = np.stack([(cols + .5) * CELL - W / 2, H / 2 - (rows + .5) * CELL, z], -1).reshape(-1, 3)
    r, c = np.meshgrid(np.arange(ny - 1), np.arange(nx - 1), indexing="ij")
    v = lambda rr, cc: (rr * nx + cc).ravel()
    quads = np.stack([v(r, c), v(r + 1, c), v(r + 1, c + 1), v(r, c + 1)], -1)   # NW, SW, SE, NE: counter-clockwise from above
    me = bpy.data.meshes.new("Terrain")
    me.vertices.add(len(co)); me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.loops.add(quads.size); me.loops.foreach_set("vertex_index", quads.astype(np.int32).ravel())
    me.polygons.add(len(quads)); me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    uv = me.uv_layers.new(name="UVMap")
    uvco = np.stack([(cols + .5) / nx, 1 - (rows + .5) / ny], -1).reshape(-1, 2)
    uv.data.foreach_set("uv", uvco[quads.ravel()].astype(np.float32).ravel())
    me.update(calc_edges=True)
    me.validate()
    me.shade_smooth()
    return me

def terrain_material():
    m = bpy.data.materials.new("Terrain · elevation and slope")
    m.use_nodes = True
    nt = m.node_tree; N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]; bsdf.inputs["Roughness"].default_value = .92
    geo = N.new("ShaderNodeNewGeometry")
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Position"], sep.inputs[0])
    rng = N.new("ShaderNodeMapRange"); rng.inputs["From Min"].default_value = -60; rng.inputs["From Max"].default_value = 400
    L.new(sep.outputs["Z"], rng.inputs["Value"])
    ramp = N.new("ShaderNodeValToRGB"); L.new(rng.outputs["Result"], ramp.inputs["Fac"])
    stops = [(0.0, "#4d6360"), (.115, "#cbbd92"), (.131, "#e8d9aa"), (.17, "#c9c08a"), (.32, "#8f9555"),
             (.55, "#66722c"), (.76, "#76715a"), (.9, "#aea593")]         # seabed, sand, beach, dry grass, olive, maquis, scrub, limestone
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], hexrgb(stops[0][1]); els[1].position, els[1].color = stops[1][0], hexrgb(stops[1][1])
    for pos, col in stops[2:]:
        e = els.new(pos); e.color = hexrgb(col)
    nrm = N.new("ShaderNodeSeparateXYZ"); L.new(geo.outputs["Normal"], nrm.inputs[0])
    steep = N.new("ShaderNodeMapRange"); steep.inputs["From Min"].default_value = .86; steep.inputs["From Max"].default_value = .72
    L.new(nrm.outputs["Z"], steep.inputs["Value"])                                  # 0 below ~30°, 1 on slopes over ~44°
    land = N.new("ShaderNodeMath"); land.operation = "GREATER_THAN"; land.inputs[1].default_value = 2.0
    L.new(sep.outputs["Z"], land.inputs[0])
    fac = N.new("ShaderNodeMath"); fac.operation = "MULTIPLY"
    L.new(steep.outputs["Result"], fac.inputs[0]); L.new(land.outputs[0], fac.inputs[1])
    mix = N.new("ShaderNodeMix"); mix.data_type = "RGBA"
    L.new(fac.outputs[0], mix.inputs["Factor"]); L.new(ramp.outputs["Color"], mix.inputs[6])
    mix.inputs[7].default_value = hexrgb("#a79a86")                                  # exposed rock on steep ground
    L.new(mix.outputs[2], bsdf.inputs["Base Color"])
    return m

def sea(coll):
    bpy.ops.mesh.primitive_plane_add(size=400000, location=(0, 0, 0))
    ob = bpy.context.active_object; ob.name = "Sea level"
    for c in ob.users_collection: c.objects.unlink(ob)
    coll.objects.link(ob)
    m = bpy.data.materials.new("Sea")
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = hexrgb("#136f9e")
    b.inputs["Roughness"].default_value = .3
    b.inputs["Alpha"].default_value = .88
    ob.data.materials.append(m)
    bpy.ops.mesh.primitive_plane_add(size=400000, location=(0, 0, HMIN - 1))    # open-sea floor beyond the terrain's edge
    bed = bpy.context.active_object; bed.name = "Sea floor"
    for c in bed.users_collection: c.objects.unlink(bed)
    coll.objects.link(bed)
    mb = bpy.data.materials.new("Sea floor"); mb.use_nodes = True
    mb.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = hexrgb("#4d6360")
    bed.data.materials.append(mb)
    return ob

def site_empties(parent):
    data = json.loads(SITES.read_text())
    colls, made = {}, []
    for key, s in data["sites"].items():
        vol = s["volumes"][0]
        if vol not in colls: colls[vol] = collection(f"{vol} · {VOLUMES[vol]}", parent)
        for k, (x, y, z) in enumerate(s["points_m"]):
            name = f"{s['num']:02d} {s['name']}" + (f" ·{k + 1}" if len(s["points_m"]) > 1 else "")
            ob = bpy.data.objects.new(name, None)
            ob.empty_display_type = "SINGLE_ARROW"; ob.empty_display_size = 80
            ob.location = (x - W / 2, H / 2 - y, z)
            ob["site_num"], ob["site_key"], ob["volume"], ob["elevation_m"] = s["num"], key, vol, z
            colls[vol].objects.link(ob)
            made.append((ob, s, (x, y, z)))
    return made

def camera(name, loc, target, coll, ortho=None, lens=35):
    cam = bpy.data.cameras.new(name); cam.clip_start, cam.clip_end = 5, 500000; cam.lens = lens
    if ortho: cam.type, cam.ortho_scale = "ORTHO", ortho
    ob = bpy.data.objects.new(name, cam); ob.location = loc; coll.objects.link(ob)
    aim = bpy.data.objects.new(name + " target", None); aim.location = target; coll.objects.link(aim)
    con = ob.constraints.new("TRACK_TO"); con.target = aim; con.track_axis, con.up_axis = "TRACK_NEGATIVE_Z", "UP_Y"
    return ob

def checks(terrain, z, sites):
    deps = bpy.context.evaluated_depsgraph_get()
    ev = terrain.evaluated_get(deps)
    errs = []
    for ob, s, (x, y, zj) in sites:
        hit, loc, *_ = ev.ray_cast((x - W / 2, H / 2 - y, 2000), (0, 0, -1))
        errs.append(abs(loc.z - zj) if hit else float("inf"))                    # sites are all on land, clear of the skirt
    pos = {s["num"]: ob.location for ob, s, _ in sites}
    res = {"vertices": len(terrain.data.vertices), "grid": [z.shape[1], z.shape[0]], "cell_m": CELL,
           "summit_m": round(float(z.max()), 1), "land_km2": round(float((z > 0).sum()) * CELL * CELL / 1e6, 2),
           "site_points": len(sites), "site_height_err_max_m": round(max(errs), 2), "site_height_err_mean_m": round(sum(errs) / len(errs), 2),
           "north_is_plus_y": bool(pos[1].x < 0 and pos[1].y > 0 and pos[23].x > 0 and pos[23].y < 0),
           "all_sites_on_terrain": all(e != float("inf") for e in errs)}
    res["ok"] = res["north_is_plus_y"] and res["all_sites_on_terrain"] and res["site_height_err_max_m"] < 6
    return res

def render(scene, cam, path, size):
    scene.camera = cam
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)

PAGE = ROOT / "art-direction-grand-island-shape.html"

def page_block(marker, rows, checks_):
    """Write measured rows and pass/fail checks into the page between <!-- marker --> comments."""
    if not PAGE.exists(): return
    block = ('<dl class="stats">' + "".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in rows)
             + "".join(f'<div class="ck {"pass" if ok else "fail"}"><dt>{k}</dt><dd>{"✓ yes" if ok else "✗ no"}</dd></div>' for k, ok in checks_) + "</dl>")
    html = PAGE.read_text()
    a0, a1 = html.find(f"<!-- {marker} -->"), html.find(f"<!-- /{marker} -->")
    if a0 >= 0 and a1 > a0:
        PAGE.write_text(html[:a0] + f"<!-- {marker} -->\n" + block + "\n" + html[a1:])

def use_eevee(scene):
    engines = {e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = "BLENDER_EEVEE" if "BLENDER_EEVEE" in engines else "BLENDER_EEVEE_NEXT"
    scene.view_settings.view_transform = "AgX"

def build():
    """A fresh scene: terrain, sea, site empties, sun and cameras, with the terrain checks run and recorded."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system, scene.unit_settings.length_unit = "METRIC", "METERS"
    world = bpy.data.worlds.new("Sky"); world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = hexrgb("#bcd6e4")
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = .7
    scene.world = world

    land_c, sites_c, look_c = collection("Terrain"), collection("Sites"), collection("Cameras & light")
    z = heights()
    terrain = bpy.data.objects.new("Terrain", terrain_mesh(skirt(z))); land_c.objects.link(terrain)
    terrain.data.materials.append(terrain_material())
    sea(land_c)
    sites = site_empties(sites_c)

    sun = bpy.data.objects.new("Sun · afternoon", bpy.data.lights.new("Sun", "SUN"))
    sun.data.energy, sun.data.angle = 2.6, .02
    sun.rotation_euler = (0.95, 0.0, -1.17)                                     # ~35° high, from the west-south-west
    look_c.objects.link(sun)
    cams = {"overview": camera("Cam · overview from the south-west", (-7500, -9500, 5200), (400, 300, 0), look_c, lens=30),
            "top": camera("Cam · top", (0, 0, 15000), (0, 0.01, 0), look_c, ortho=11000),
            "col": camera("Cam · the Round's col from over the harbour", (1900, 1700, 520), (-130, -140, 150), look_c, lens=32)}
    scene.camera = cams["overview"]
    for scr in bpy.data.screens:
        for area in scr.areas:
            if area.type == "VIEW_3D":
                area.spaces[0].clip_start, area.spaces[0].clip_end = 1, 500000

    res = checks(terrain, z, sites)
    OUT.mkdir(exist_ok=True)
    (OUT / "terrain-checks.json").write_text(json.dumps(res, indent=1))
    print("TERRAIN CHECKS", json.dumps(res))
    page_block("TERRAIN",
               [("Terrain vertices", f"{res['vertices']:,} ({res['grid'][0]} × {res['grid'][1]}, {CELL} m apart)"),
                ("Summit", f"{res['summit_m']} m"), ("Land", f"{res['land_km2']} km²"),
                ("Site heights vs the site list", f"max {res['site_height_err_max_m']} m, mean {res['site_height_err_mean_m']} m over {res['site_points']} points")],
               [("North is +Y (site 1 north-west, site 23 south-east)", res["north_is_plus_y"]),
                ("Every site lands on the terrain", res["all_sites_on_terrain"]),
                ("Site heights within 6 m", res["site_height_err_max_m"] < 6)])
    return {"scene": scene, "terrain": terrain, "z": z, "sites": sites, "cams": cams, "look": look_c}

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ctx = build(); scene, cams = ctx["scene"], ctx["cams"]
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "paxos.blend"), compress=True)
    if "--render" in args:
        RENDERS.mkdir(exist_ok=True)
        use_eevee(scene)
        render(scene, cams["overview"], RENDERS / "terrain-overview.png", (1920, 1080))
        render(scene, cams["top"], RENDERS / "terrain-top.png", (1540, 1120))
        render(scene, cams["col"], RENDERS / "terrain-col.png", (1920, 1080))
        scene.camera = cams["overview"]
        bpy.ops.wm.save_as_mainfile(filepath=str(OUT / "paxos.blend"), compress=True)

if __name__ == "__main__":
    main()
