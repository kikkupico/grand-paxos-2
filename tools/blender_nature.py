"""Vegetation, fields and tracks on the terrain (called from blender_buildings.main after every site is built).

Per terrain vertex, density masks are computed from elevation, slope, distance to the sea and distance to
settlements, minus exclusions (buildings, tracks, water) and, for tall trees, the sightlines the story needs
(the Round to its quays and banquet house, the beacon fires, the drum platforms). The masks are stored as mesh
attributes. Geometry Nodes scatters low-poly olives, umbrella pines and maquis shrubs from them, and cypresses
are placed by hand at the sanctuaries. The terrain shader paints wheat parcels and tracks from the same
attributes, and the tracks from the map generator are also draped as ribbons for close shots.
"""
import math, random
import bpy, bmesh
import numpy as np
from mathutils import Matrix, Vector
from blender_kit import *                                                                          # noqa: F401,F403
import blender_sites as bs

# ---------------------------------------------------------------- fields over the vertex grid
def grid_xy(ground):
    rows, cols = np.mgrid[0:ground.ny, 0:ground.nx]
    return (cols + .5) * bt.CELL - bt.W / 2, bt.H / 2 - (rows + .5) * bt.CELL

def noise(shape, cells, seed):
    """Smooth value noise in [0, 1], `cells` metres between lattice points."""
    rng = np.random.default_rng(seed); ny, nx = shape; k = max(2, int(cells / bt.CELL))
    lat = rng.random((ny // k + 3, nx // k + 3))
    r, c = np.mgrid[0:ny, 0:nx] / k
    r0, c0 = r.astype(int), c.astype(int); fr, fc = r - r0, c - c0
    fr, fc = fr * fr * (3 - 2 * fr), fc * fc * (3 - 2 * fc)
    return (lat[r0, c0] * (1 - fr) * (1 - fc) + lat[r0, c0 + 1] * (1 - fr) * fc + lat[r0 + 1, c0] * fr * (1 - fc) + lat[r0 + 1, c0 + 1] * fr * fc)

def distance_to(mask, max_m=1200.0):
    """Approximate metres from each cell to the nearest True cell (chamfer passes)."""
    d = np.where(mask, 0.0, np.inf); s, dg = bt.CELL, bt.CELL * math.sqrt(2)
    for _ in range(int(max_m / bt.CELL)):
        n = d.copy()
        n[1:, :] = np.minimum(n[1:, :], d[:-1, :] + s); n[:-1, :] = np.minimum(n[:-1, :], d[1:, :] + s)
        n[:, 1:] = np.minimum(n[:, 1:], d[:, :-1] + s); n[:, :-1] = np.minimum(n[:, :-1], d[:, 1:] + s)
        n[1:, 1:] = np.minimum(n[1:, 1:], d[:-1, :-1] + dg); n[:-1, :-1] = np.minimum(n[:-1, :-1], d[1:, 1:] + dg)
        n[1:, :-1] = np.minimum(n[1:, :-1], d[:-1, 1:] + dg); n[:-1, 1:] = np.minimum(n[:-1, 1:], d[1:, :-1] + dg)
        if np.array_equal(n, d): break
        d = n
    return np.minimum(d, max_m)

def segment_distance(X, Y, pts):
    """Metres from every cell to a polyline (evaluated segment by segment)."""
    out = np.full(X.shape, np.inf)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy or 1.0
        t = np.clip(((X - x0) * dx + (Y - y0) * dy) / L2, 0, 1)
        out = np.minimum(out, np.hypot(X - (x0 + t * dx), Y - (y0 + t * dy)))
    return out

EXCLUDE_M = {"round": 45, "banquet": 26, "cothon": 285, "port": 120, "city": 135, "camps": 42, "citadel": 100, "seawall": 130,
             "granary": 48, "granary2": 40, "hall": 32, "locks": 16, "cliffs": 115, "monastery": 42, "hamA": 34, "hamK": 34, "hamM": 34,
             "press": 22, "beacons": 10, "watchtowers": 18, "drummers": 12}

def tracks(smooth):
    """The track network and the Statue Walk as Blender-space polylines."""
    out = [smooth([B(x, y) for x, y in t["path"]], rounds=2) for t in SITES["built"]["tracks_m"] if len(t["path"]) > 1]
    return out, bs.walk_route()[0]

def masks(ground, smooth, sightlines, prop_spots=()):
    X, Y = grid_xy(ground); z = ground.g.astype(np.float64)
    gy, gx = np.gradient(z, bt.CELL); slope = np.hypot(gx, gy)
    land = z > 2.0
    sea_d = distance_to(z < 0, 900)
    excl = np.zeros(z.shape, bool)
    for key, r in EXCLUDE_M.items():
        for x, y, _ in SITES["sites"][key]["points_m"]:
            bx, by = B(x, y); excl |= np.hypot(X - bx, Y - by) < r
    for x, y, _ in SITES["built"]["town"]["insulae_m_deg"]:
        bx, by = B(x, y); excl |= np.hypot(X - bx, Y - by) < 34
    ax, ay = B(*SITES["built"]["town"]["agora_m_deg"][:2]); excl |= np.hypot(X - ax, Y - ay) < 45
    for px, py, r in prop_spots: excl |= np.hypot(X - px, Y - py) < r + 12.5                          # carts, crane, amphorae: a cell wider, since density interpolates
    track_lines, walk = tracks(smooth)
    track_d = np.full(z.shape, np.inf)
    for line in track_lines + [walk]: track_d = np.minimum(track_d, segment_distance(X, Y, line))
    corridor = np.zeros(z.shape, bool)
    for p, q in sightlines: corridor |= segment_distance(X, Y, [p[:2], q[:2]]) < 30               # wider than a face, since density interpolates across 12.5 m cells
    settle_pts = [B(x, y) for key in ("hamA", "hamK", "hamM", "press", "town", "granary", "granary2", "city", "monastery", "hall")
                  for x, y, _ in SITES["sites"][key]["points_m"]]
    settle_d = np.min([np.hypot(X - sx, Y - sy) for sx, sy in settle_pts], axis=0)
    free = land & ~excl & (track_d > 7)
    free &= ~np.roll(~land, 1, 0) & ~np.roll(~land, -1, 0) & ~np.roll(~land, 1, 1) & ~np.roll(~land, -1, 1)   # one cell in from the coast
    groves = noise(z.shape, 180, 11) * .7 + noise(z.shape, 60, 12) * .3
    olive = free & (z > 12) & (z < 210) & (slope < .32) & (settle_d < 950) & (groves > .45)
    olive_w = np.where(olive, np.clip((groves - .45) * 3, .25, 1) * np.clip(1 - settle_d / 950, .2, 1), 0.0)
    scrub = noise(z.shape, 120, 21)
    maquis_w = np.where(free & ~olive & (z > 25), np.clip(.25 + scrub * .8 + slope * .6, 0, 1), 0.0)
    pinen = noise(z.shape, 240, 31)
    pine_w = np.where(free & (z > 3) & (z < 170) & (sea_d < 520) & (pinen > .55), np.clip((pinen - .55) * 4, .3, 1), 0.0)
    olive_w[corridor] = 0; pine_w[corridor] = 0                                                   # tall trees keep the story's sightlines open
    # wheat and fallow parcels on the south-east plain around the granaries
    gran = [B(x, y) for key in ("granary", "granary2") for x, y, _ in SITES["sites"][key]["points_m"]]
    gran_d = np.min([np.hypot(X - gx_, Y - gy_) for gx_, gy_ in gran], axis=0)
    plain = land & ~excl & (z > 3) & (z < 110) & (slope < .14) & (gran_d < 1100)
    field = plain.astype(np.float64)                                                               # the parcels themselves are drawn in the shader
    olive_w[field > 0] = 0; maquis_w[field > 0] *= .05; pine_w[field > 0] = 0
    track = np.clip(1 - (track_d - 2.5) / 5, 0, 1) * land
    return {"veg_olive": olive_w, "veg_maquis": maquis_w, "veg_pine": pine_w, "field": field, "track": track}, \
           {"wheat_km2": round(float((field > 0).sum()) * bt.CELL ** 2 / 1e6, 2), "track_lines": track_lines, "walk": walk,
            "corridor_cells": int(corridor.sum())}

def store(terrain, fields):
    me = terrain.data
    for name, arr in fields.items():
        a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
        a.data.foreach_set("value", arr.astype(np.float32).ravel())
    me.update()

# ---------------------------------------------------------------- materials, prototypes, scattering
PARCEL_M = (95.0, 62.0)
PARCEL_ANGLE = .6

def patch_terrain_material(terrain):
    """Farmland: crisp rectangular parcels (wheat, stubble, fodder, ploughed) with hedge lines, computed from surface
    position in the shader and masked by the `field` attribute. Tracks: a dirt tint from the `track` attribute."""
    m = terrain.data.materials[0]; nt = m.node_tree; N, L = nt.nodes, nt.links
    bsdf = N["Principled BSDF"]; src = bsdf.inputs["Base Color"].links[0].from_socket
    geo = N.new("ShaderNodeNewGeometry")
    rot = N.new("ShaderNodeVectorRotate"); rot.rotation_type = "Z_AXIS"; rot.inputs["Angle"].default_value = PARCEL_ANGLE
    L.new(geo.outputs["Position"], rot.inputs["Vector"])
    div = N.new("ShaderNodeVectorMath"); div.operation = "DIVIDE"; div.inputs[1].default_value = (*PARCEL_M, 1.0)
    L.new(rot.outputs["Vector"], div.inputs[0])
    flo = N.new("ShaderNodeVectorMath"); flo.operation = "FLOOR"; L.new(div.outputs["Vector"], flo.inputs[0])
    wn = N.new("ShaderNodeTexWhiteNoise"); wn.noise_dimensions = "2D"; L.new(flo.outputs["Vector"], wn.inputs["Vector"])
    ramp = N.new("ShaderNodeValToRGB"); L.new(wn.outputs["Value"], ramp.inputs["Fac"]); ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, bt.hexrgb("#d8b85c"); els[1].position, els[1].color = .4, bt.hexrgb("#c7b07a")
    for pos, col in ((.58, "#9a9b52"), (.76, "#a88d63"), (.88, "#d4b04f")): e = els.new(pos); e.color = bt.hexrgb(col)
    fr = N.new("ShaderNodeVectorMath"); fr.operation = "FRACTION"; L.new(div.outputs["Vector"], fr.inputs[0])
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(fr.outputs["Vector"], sep.inputs[0])
    ex = N.new("ShaderNodeMath"); ex.operation = "LESS_THAN"; ex.inputs[1].default_value = .05; L.new(sep.outputs["X"], ex.inputs[0])
    ey = N.new("ShaderNodeMath"); ey.operation = "LESS_THAN"; ey.inputs[1].default_value = .07; L.new(sep.outputs["Y"], ey.inputs[0])
    edge = N.new("ShaderNodeMath"); edge.operation = "MAXIMUM"; L.new(ex.outputs[0], edge.inputs[0]); L.new(ey.outputs[0], edge.inputs[1])
    hedge = N.new("ShaderNodeMix"); hedge.data_type = "RGBA"
    L.new(edge.outputs[0], hedge.inputs["Factor"]); L.new(ramp.outputs["Color"], hedge.inputs[6]); hedge.inputs[7].default_value = bt.hexrgb("#7f8452")
    fa = N.new("ShaderNodeAttribute"); fa.attribute_type = "GEOMETRY"; fa.attribute_name = "field"
    isf = N.new("ShaderNodeMath"); isf.operation = "GREATER_THAN"; isf.inputs[1].default_value = .5; L.new(fa.outputs["Fac"], isf.inputs[0])
    mix1 = N.new("ShaderNodeMix"); mix1.data_type = "RGBA"
    L.new(isf.outputs[0], mix1.inputs["Factor"]); L.new(src, mix1.inputs[6]); L.new(hedge.outputs[2], mix1.inputs[7])
    ta = N.new("ShaderNodeAttribute"); ta.attribute_type = "GEOMETRY"; ta.attribute_name = "track"
    mix2 = N.new("ShaderNodeMix"); mix2.data_type = "RGBA"
    L.new(ta.outputs["Fac"], mix2.inputs["Factor"]); L.new(mix1.outputs[2], mix2.inputs[6]); mix2.inputs[7].default_value = bt.hexrgb("#bfa77f")
    L.new(mix2.outputs[2], bsdf.inputs["Base Color"])

def blob(kit, X, Y, Z, rx, ry, rz, m, subdiv=1):
    res = bmesh.ops.create_icosphere(kit.bm, subdivisions=subdiv, radius=1.0,
                                     matrix=Matrix.Translation((X, Y, Z)) @ Matrix.Diagonal((rx, ry, rz, 1.0)))
    faces = {f for v in res["verts"] for f in v.link_faces}
    for f in faces: f.material_index = kit._mi(m)

def prototypes(coll):
    leaf = {"olive": mat("Olive leaves", "#7d8758"), "pine": mat("Pine needles", "#3d582d"), "cypress": mat("Cypress", "#2c4424"),
            "maquis": mat("Maquis", "#5a6a39"), "bark": mat("Bark", "#584432")}
    protos = {}
    k = Kit("proto · olive"); k.cyl(0, 0, .25, -.5, 1.7, leaf["bark"], 6)
    blob(k, 0, 0, 2.9, 2.4, 2.2, 1.5, leaf["olive"]); blob(k, .9, .4, 3.5, 1.4, 1.3, .9, leaf["olive"])
    protos["olive"] = k.finish(coll)
    k = Kit("proto · umbrella pine"); k.cyl(0, 0, .35, -.5, 9.5, leaf["bark"], 6)
    blob(k, 0, 0, 10.2, 5.2, 4.8, 1.6, leaf["pine"]); blob(k, 1.2, -.8, 11.0, 3.4, 3.2, 1.1, leaf["pine"])
    protos["pine"] = k.finish(coll)
    k = Kit("proto · maquis"); blob(k, 0, 0, .5, 1.3, 1.1, .8, leaf["maquis"]); blob(k, .8, .3, .4, .8, .7, .55, leaf["maquis"])
    protos["maquis"] = k.finish(coll)
    k = Kit("proto · cypress"); k.cyl(0, 0, .2, -.5, 1.2, leaf["bark"], 6); k.cone(0, 0, 1.3, .8, 11.5, leaf["cypress"], 10)
    protos["cypress"] = k.finish(coll)
    for ob in protos.values(): ob.location.z = -3000                                               # out of every shot; Object Info reads their geometry
    return protos

def scatter(name, terrain, proto, attribute, per_m2, seed, scale, coll):
    """A Geometry Nodes object that scatters `proto` over the terrain with density attribute × per_m2."""
    ng = bpy.data.node_groups.new(f"Scatter · {name}", "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    N, L = ng.nodes, ng.links
    N.new("NodeGroupInput"); out = N.new("NodeGroupOutput")
    ground = N.new("GeometryNodeObjectInfo"); ground.inputs["Object"].default_value = terrain; ground.transform_space = "RELATIVE"
    attr = N.new("GeometryNodeInputNamedAttribute"); attr.data_type = "FLOAT"; attr.inputs["Name"].default_value = attribute
    dens = N.new("ShaderNodeMath"); dens.operation = "MULTIPLY"; dens.inputs[1].default_value = per_m2
    L.new(attr.outputs["Attribute"], dens.inputs[0])
    dist = N.new("GeometryNodeDistributePointsOnFaces"); dist.distribute_method = "RANDOM"; dist.inputs["Seed"].default_value = seed
    L.new(ground.outputs["Geometry"], dist.inputs["Mesh"]); L.new(dens.outputs[0], dist.inputs["Density"])
    obj = N.new("GeometryNodeObjectInfo"); obj.inputs["Object"].default_value = proto
    inst = N.new("GeometryNodeInstanceOnPoints")
    rot = N.new("FunctionNodeRandomValue"); rot.data_type = "FLOAT_VECTOR"
    rot.inputs[1].default_value = (0, 0, math.tau); rot.inputs["Seed"].default_value = seed + 1
    scl = N.new("FunctionNodeRandomValue"); scl.data_type = "FLOAT"
    scl.inputs[2].default_value, scl.inputs[3].default_value = scale; scl.inputs["Seed"].default_value = seed + 2
    L.new(dist.outputs["Points"], inst.inputs["Points"]); L.new(obj.outputs["Geometry"], inst.inputs["Instance"])
    L.new(rot.outputs[0], inst.inputs["Rotation"]); L.new(scl.outputs[1], inst.inputs["Scale"])
    L.new(inst.outputs["Instances"], out.inputs[0])
    me = bpy.data.meshes.new(f"Vegetation · {name}"); ob = bpy.data.objects.new(f"Vegetation · {name}", me); coll.objects.link(ob)
    mod = ob.modifiers.new("Scatter", "NODES"); mod.node_group = ng
    return ob

def cypress_rings(proto, coll):
    """Hand-placed cypresses: around the watchtower headlands, the banquet house garden and the monastery."""
    placed = []
    def put(x, y, z, s=1.0):
        ob = bpy.data.objects.new("Cypress", proto.data); ob.location = (x, y, z); ob.scale = (s, s, s); coll.objects.link(ob); placed.append(ob)
    return put, placed

def ribbons(ground, lines, width, lift, material, name, coll):
    bm = bmesh.new(); total = 0.0
    for pts in lines:
        prev = None
        for i, (x, y) in enumerate(pts):
            j0, j1 = max(i - 1, 0), min(i + 1, len(pts) - 1)
            tx, ty = pts[j1][0] - pts[j0][0], pts[j1][1] - pts[j0][1]; n = math.hypot(tx, ty) or 1
            nx, ny = -ty / n * width / 2, tx / n * width / 2
            a = bm.verts.new((x + nx, y + ny, ground.z(x + nx, y + ny) + lift)); b = bm.verts.new((x - nx, y - ny, ground.z(x - nx, y - ny) + lift))
            if prev: bm.faces.new((prev[0], prev[1], b, a)); total += math.dist(pts[i - 1], (x, y))
            prev = (a, b)
    me = bpy.data.meshes.new(name); bm.to_mesh(me); bm.free(); me.materials.append(material)
    ob = bpy.data.objects.new(name, me); coll.objects.link(ob)
    return ob, round(total)

# ---------------------------------------------------------------- build + checks
def build(ctx, ground, smooth, sightlines, exclusions, prop_spots=()):
    terrain = ctx["terrain"]
    top = bt.collection("Vegetation and tracks")
    proto_c = bt.collection("Vegetation prototypes", top)
    fields, info = masks(ground, smooth, sightlines, prop_spots)
    store(terrain, fields)
    patch_terrain_material(terrain)
    protos = prototypes(proto_c)
    objs = {"olive groves": scatter("olive groves", terrain, protos["olive"], "veg_olive", 1 / 55, 7, (.75, 1.25), top),
            "maquis": scatter("maquis", terrain, protos["maquis"], "veg_maquis", 1 / 38, 8, (.6, 1.6), top),
            "umbrella pines": scatter("umbrella pines", terrain, protos["pine"], "veg_pine", 1 / 320, 9, (.7, 1.2), top)}
    put, cypresses = cypress_rings(protos["cypress"], top)
    for i in range(4):
        wx, wy = site("watchtowers", i)
        for dx, dy in ((-12, -8), (12, 8)):
            put(wx + dx, wy + dy, ground.z(wx + dx, wy + dy), .85)
    BX, BY = site("banquet")
    for dx, dy in ((-18, -14), (-18, 14), (18, -14), (18, 14)): put(BX + dx, BY + dy, ground.z(BX + dx, BY + dy), .8)
    MX, MY = site("monastery")
    for a in np.linspace(0, math.tau, 12, endpoint=False):
        x, y = MX + 36 * math.cos(a), MY + 36 * math.sin(a); put(x, y, ground.z(x, y), .9)
    tr_ob, track_len = ribbons(ground, info["track_lines"], 3.6, .22, mat("Dirt track", "#b8a07a"), "Tracks", top)

    deps = bpy.context.evaluated_depsgraph_get()
    counts = {k: 0 for k in objs}; wet, on_bld, in_corridor = 0, 0, 0
    names = {o.name: k for k, o in objs.items()}
    tall, allp = [], []
    for inst in deps.object_instances:
        if not inst.is_instance or inst.parent is None or inst.parent.name not in names: continue
        kind = names[inst.parent.name]; counts[kind] += 1
        p = inst.matrix_world.translation
        if p.z < 0.3: wet += 1
        allp.append((p.x, p.y))
        if kind != "maquis": tall.append((p.x, p.y))
    tall = np.array(tall) if tall else np.zeros((0, 2))
    allp = np.array(allp) if allp else np.zeros((0, 2))
    on_props = sum(int((np.hypot(allp[:, 0] - px, allp[:, 1] - py) < r).sum()) for px, py, r in prop_spots) if len(allp) else 0
    for (cx, cy, r) in exclusions:
        if len(tall): on_bld += int((np.hypot(tall[:, 0] - cx, tall[:, 1] - cy) < r * .75).sum())
    for p, q in sightlines:
        if not len(tall): break
        (x0, y0), (x1, y1) = p[:2], q[:2]; dx, dy = x1 - x0, y1 - y0; L2 = dx * dx + dy * dy
        t = np.clip(((tall[:, 0] - x0) * dx + (tall[:, 1] - y0) * dy) / L2, 0, 1)
        in_corridor += int((np.hypot(tall[:, 0] - (x0 + t * dx), tall[:, 1] - (y0 + t * dy)) < 8).sum())
    res = {"instances": counts, "cypresses": len(cypresses), "wheat_and_fallow_km2": info["wheat_km2"], "track_ribbons_m": track_len,
           "trees_standing_in_water": wet, "tall_trees_on_building_footprints": on_bld, "plants_on_props": on_props, "tall_trees_on_story_sightlines": in_corridor}
    res["ok"] = wet == 0 and on_bld == 0 and on_props == 0 and in_corridor == 0 and all(v > 0 for v in counts.values())
    return res
