"""The Great Round in detail (Volume IV). Replaces the blockout in blender_buildings.

The canon: an open-air circular assembly theatre about 50 m across, sunk into a windswept col; about 14 tiers of
limestone seats, 8 radial stairways, a walkway ring at mid-height, a sand orchestra with a marble kerb, a high
ashlar ring wall, four monumental gateways at the cardinal points with bronze-plated double doors and an oak
drop-bar, and statues of past legislators outside the wall.

The user's refinement (16 Sep 2026): the top tier is an inward-facing verandah, its floor about 15 ft above the
outside ground, with windows in the ring wall looking out over the island. The sills sit high enough to read as
windows, not entrances. The gates stay at ground level and open onto the mid-height walkway, below the verandah,
which bridges over the gate passages.

The user's fixes (16 Sep 2026): each stairway runs unbroken from the orchestra to the verandah, with a landing where it
crosses the walkway; the gate passages are open right through; and the bronze doors stand open unless a gate is
listed in GATES_BARRED.

Human scale is built in: 0.8 m seat treads with 0.5 m (lower) and 0.6 m (upper) rises, stair steps of 0.3 m or
less, 4 m doorways, drop-bars 1.3 m above the threshold, and 1.75 m scale figures. The views of the banquet house
and the merchant quays are checked by casting rays from a person standing at a verandah window, through the
Round's own geometry and the terrain.
"""
import math
import bpy
import numpy as np
from mathutils import Vector
from blender_kit import *                                                                          # noqa: F401,F403

LOWER_ROWS, UPPER_ROWS, TREAD = 7, 6, .80                      # 13 seat rows + the verandah = the canon's 14 tiers
LOWER_RISE, UPPER_RISE, PODIUM = .50, .60, 1.10               # the walkway sits at outside-ground level; the podium lifts the upper cavea
ORCH_R, KERB_R, WALK_W = 8.0, 8.6, 1.4
VERANDAH_UP, VERANDAH_D, VERANDAH_H = 4.6, 3.0, 3.3           # floor 15 ft above the outside ground, 3 m deep, 3.3 m to the eaves
WALL_IN, WALL_OUT = 23.4, 25.0
SILL_UP, WIN_H, WIN_W, WIN_STEP_DEG = 5.5, 1.9, 1.4, 5.0     # sills ~5.5 m above the outside ground read as windows, not doors
GATE_W, DOOR_H, BAR_Z = 4.0, 4.0, 1.3
STAIR_W, STAIRS = 1.2, 8
STAIR_UPPER_BREAKS = (3, 5)                                   # the upper flights land on the outer edges of these upper seat rows (1-based)
VER_STEP = .9                                                 # the top flight is let 0.9 m into the verandah floor
GATES_BARRED = ()                                             # e.g. ("N", "W"): these gates are shown shut and barred; the rest stand open
FIGURE_H = 1.75
TERRACE_R = 34.0                                              # paved terrace round the wall, out to here
PYLON_HALF_DEG = 13.5                                          # gate pylons and pediments occupy this much wall either side of a gate axis

# ---------------------------------------------------------------- textured materials
def _noise_mat(name, c1, c2, scale, rough=.85, metal=0.0):
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links; b = N["Principled BSDF"]
    tc = N.new("ShaderNodeTexCoord"); nz = N.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = scale
    L.new(tc.outputs["Object"], nz.inputs["Vector"])
    rp = N.new("ShaderNodeValToRGB"); L.new(nz.outputs["Fac"], rp.inputs["Fac"])
    rp.color_ramp.elements[0].position, rp.color_ramp.elements[0].color = .35, bt.hexrgb(c1)
    rp.color_ramp.elements[1].position, rp.color_ramp.elements[1].color = .7, bt.hexrgb(c2)
    L.new(rp.outputs["Color"], b.inputs["Base Color"])
    b.inputs["Roughness"].default_value = rough; b.inputs["Metallic"].default_value = metal
    MATS[name] = m
    return m

def _ashlar(name, cx, cy, radius):
    """Ashlar courses wrapped round the ring: brick texture on (angle x radius, height)."""
    if name in MATS: return MATS[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    N, L = m.node_tree.nodes, m.node_tree.links; b = N["Principled BSDF"]
    geo = N.new("ShaderNodeNewGeometry")
    sub = N.new("ShaderNodeVectorMath"); sub.operation = "SUBTRACT"; sub.inputs[1].default_value = (cx, cy, 0)
    L.new(geo.outputs["Position"], sub.inputs[0])
    sep = N.new("ShaderNodeSeparateXYZ"); L.new(sub.outputs["Vector"], sep.inputs[0])
    at = N.new("ShaderNodeMath"); at.operation = "ARCTAN2"; L.new(sep.outputs["Y"], at.inputs[0]); L.new(sep.outputs["X"], at.inputs[1])
    mul = N.new("ShaderNodeMath"); mul.operation = "MULTIPLY"; mul.inputs[1].default_value = radius; L.new(at.outputs[0], mul.inputs[0])
    cmb = N.new("ShaderNodeCombineXYZ"); L.new(mul.outputs[0], cmb.inputs["X"]); L.new(sep.outputs["Z"], cmb.inputs["Y"])
    br = N.new("ShaderNodeTexBrick"); L.new(cmb.outputs["Vector"], br.inputs["Vector"])
    br.inputs["Scale"].default_value = 1.0; br.inputs["Mortar Size"].default_value = .025
    br.offset = .5; br.squash = 1.0
    br.inputs["Brick Width"].default_value = 1.35; br.inputs["Row Height"].default_value = .62
    br.inputs["Color1"].default_value = bt.hexrgb("#cdbd97"); br.inputs["Color2"].default_value = bt.hexrgb("#bfae88")
    br.inputs["Mortar"].default_value = bt.hexrgb("#e2d6b8")
    L.new(br.outputs["Color"], b.inputs["Base Color"]); b.inputs["Roughness"].default_value = .9
    MATS[name] = m
    return m

def round_materials(X, Y):
    return {"ashlar": _ashlar("Round ashlar", X, Y, 24.2), "tier": _noise_mat("Tier limestone", "#d6caae", "#c8b996", 1.4),
            "marble": _noise_mat("Veined marble", "#efebe2", "#d8d2c4", 3.0, .45), "sand": _noise_mat("Orchestra sand (textured)", "#dcc590", "#cdb47c", 2.5, .95),
            "bronze": _noise_mat("Bronze with patina", "#8c6629", "#5e7c68", 2.2, .38, .8), "oak": _noise_mat("Oak", "#6c4c2f", "#56391f", 6.0, .7),
            "iron": mat("Iron", "#3a3a3a", .5, .9), "pave": _noise_mat("Gate paving", "#cfc2a4", "#bdae8d", 1.8),
            "inscription": mat("Inscription (cut letters)", "#8f8878", .9),
            "chiton": mat("Chiton linen", "#ddd3bd"), "himation_blue": mat("Himation blue", "#4f6f8a"),
            "himation_ochre": mat("Himation ochre", "#b98a3e"), "skin": mat("Skin", "#b98563", .6)}

# ---------------------------------------------------------------- figures
def figure(k, X, Y, z, facing, pose, body, drape=None, head=None, height=FIGURE_H):
    """A draped standing figure, `height` metres tall, facing `facing` (radians). pose: 'orator' raises the right arm;
    'scroll' holds a ledger open upright in both hands: rods across the top and bottom, parchment between; 'stand' has the arms down."""
    s = height / 1.75; c, sn = math.cos(facing), math.sin(facing)
    fwd = lambda d: (c * d, sn * d); side = lambda d: (-sn * d, c * d)
    P = lambda f, r, zz: (X + fwd(f)[0] + side(r)[0], Y + fwd(f)[1] + side(r)[1], z + zz * s)
    drape, head = drape or body, head or body
    k.frustum(X, Y, .30 * s, .24 * s, z, z + 1.0 * s, drape, 10)                                   # drapery to the knees and below
    k.frustum(X, Y, .23 * s, .20 * s, z + 1.0 * s, z + 1.42 * s, body, 10)
    k.box(X, Y, z + 1.36 * s, z + 1.47 * s, .22 * s, .48 * s, facing, body)                        # shoulders
    k.cyl(X, Y, .055 * s, z + 1.46 * s, z + 1.55 * s, head, 6)
    k.ellipsoid(X, Y, z + 1.64 * s, .10 * s, .09 * s, .12 * s, head)
    for sd in (-1, 1):
        sh = P(0, .22 * sd, 1.43)
        if pose == "orator" and sd == 1:
            k.beam(sh, P(.25, .30, 1.55), .08 * s, .08 * s, body); k.beam(P(.25, .30, 1.55), P(.45, .32, 1.85), .07 * s, .07 * s, head)
        elif pose == "scroll":
            k.beam(sh, P(.08, .20 * sd, 1.12), .08 * s, .08 * s, body); k.beam(P(.08, .20 * sd, 1.12), P(.30, .19 * sd, 1.34), .07 * s, .07 * s, head)
        else:
            k.beam(sh, P(.02, .27 * sd, .82), .08 * s, .08 * s, drape if sd < 0 else body)
    if pose == "scroll":                                                                             # the ledger held open upright: rods across the top and bottom, written top to bottom
        for zz in (1.02, 1.36): k.beam(P(.32, -.21, zz), P(.32, .21, zz), .05 * s, .05 * s, head)
        k.box(*P(.33, 0, 0)[:2], z + 1.04 * s, z + 1.34 * s, .02 * s, .34 * s, facing, drape)

def statue(k, M, X, Y, z, facing, pose):
    k.box(X, Y, z - .5, z + .35, 1.35, 1.35, facing, M["marble"])
    k.box(X, Y, z + .35, z + 1.35, 1.0, 1.0, facing, M["marble"])
    k.box(X + .51 * math.cos(facing), Y + .51 * math.sin(facing), z + .7, z + 1.0, .04, .62, facing, M["inscription"])
    k.box(X, Y, z + 1.35, z + 1.55, 1.2, 1.2, facing, M["marble"])
    figure(k, X, Y, z + 1.55, facing, pose, M["marble"], height=2.1)                               # heroic scale, 1.2x life

# ---------------------------------------------------------------- the Round
def build(ground, M0, report):
    X, Y = site("round"); rim = ground.z(X, Y)                                                    # rim = outside ground level at the Round
    report["The Great Round"] = {"volume": "V", "radius_m": 25, "relief_before_m": ground.relief(X, Y, 25)[0]}
    z_orch = rim - LOWER_ROWS * LOWER_RISE
    z_ver = rim + VERANDAH_UP
    ground.pad(X, Y, 31, rim, 45)
    ground.edit(X, Y, 25, lambda d, dX, dY, g: np.where(d < 24, np.minimum(g, z_orch - 2), g))
    M = {**M0, **round_materials(X, Y), "tile": _noise_mat("Verandah roof tiles", "#b3552f", "#98452a", 4.0, .8)}
    k = Kit("V · The Great Round")
    P = lambda r, a: (X + r * math.cos(a), Y + r * math.sin(a))
    gates = [0.0, TAU / 4, TAU / 2, 3 * TAU / 4]                                                   # east, north, west, south (Blender +X is east)
    stair_angles = [TAU / 16 + i * TAU / STAIRS for i in range(STAIRS)]                            # between the gates
    near_gate = lambda a, half: min(abs((a - g + math.pi) % TAU - math.pi) for g in gates) < half

    # orchestra and kerb
    k.cyl(X, Y, ORCH_R, z_orch - 1, z_orch, M["sand"], 64)
    k.ring(X, Y, ORCH_R, KERB_R, z_orch - 1, z_orch + .35, M["marble"], 64)
    # seat rows: lower cavea, walkway at outside-ground level, podium, upper cavea
    rows = []                                                                                       # (r_in, r_out, top, rise)
    r, zt = KERB_R, z_orch
    for i in range(LOWER_ROWS):
        zt += LOWER_RISE; rows.append((r, r + TREAD, zt, LOWER_RISE)); r += TREAD
    walk_r0, walk_r1 = r, r + WALK_W                                                                # the gates open onto this walkway
    rows[-1] = (rows[-1][0], walk_r1, rows[-1][2], rows[-1][3]); r = walk_r1
    for i in range(UPPER_ROWS):
        rise = PODIUM if i == 0 else UPPER_RISE
        zt += rise; rows.append((r, r + TREAD, zt, rise)); r += TREAD
    ver_r = r                                                                                       # verandah from here to the wall
    stair_half_at = lambda rr: (STAIR_W / 2) / rr                                                  # taken at a ring's outer radius, so no slit opens beside the steps
    passage_half_at = lambda rr: (GATE_W / 2 + .35) / rr
    def between(cuts):
        cuts = sorted(cuts)
        for j, (a, h) in enumerate(cuts):
            a2, h2 = cuts[(j + 1) % len(cuts)]
            yield a + h, a2 - h2 + (TAU if j == len(cuts) - 1 else 0)
    for i, (r_in, r_out, top, rise) in enumerate(rows):
        upper = i >= LOWER_ROWS
        cuts = [(a, stair_half_at(r_out)) for a in stair_angles] + ([(g, passage_half_at((r_in + r_out) / 2)) for g in gates] if upper else [])
        for a0, a1 in between(cuts):
            k.ring(X, Y, r_in, ver_r, z_orch - 1, top, M["tier"], 144, a0, a1)                        # 144 per turn: 10 left each span one straight chord, 1 m inside mid-span
            k.ring(X, Y, r_in, r_in + .09, top - .06, top + .02, M["marble"], 144, a0, a1)
    # stairs, orchestra to verandah: two steps to each lower seat row, a landing across the walkway, then flights through
    # the upper cavea that may span rows (the 1.1 m podium can't be climbed within one 0.8 m tread), the last let into
    # the verandah floor. Each flight's rise and going are derived together, so no riser exceeds 0.3 m.
    anchors = [(KERB_R, z_orch)] + [(r_in + TREAD, top) for (r_in, r_out, top, rise) in rows[:LOWER_ROWS]]
    anchors += [(walk_r1, rim)] + [(rows[LOWER_ROWS + b - 1][1], rows[LOWER_ROWS + b - 1][2]) for b in STAIR_UPPER_BREAKS] + [(ver_r + VER_STEP, z_ver)]
    steps = []                                                                                      # (r0, r1, top)
    for (r0, z0), (r1, z1) in zip(anchors, anchors[1:]):
        n = max(1, math.ceil((z1 - z0) / .3 - 1e-6)) if z1 > z0 + 1e-6 else 1
        steps += [(r0 + (r1 - r0) * j / n, r0 + (r1 - r0) * (j + 1) / n, z0 + (z1 - z0) * (j + 1) / n) for j in range(n)]
    for a in stair_angles:
        for r0, r1, zz in steps:
            k.box(*P((r0 + r1) / 2, a), z_orch - 1, zz, r1 - r0, STAIR_W, a, M["marble"])
    # gate passages through the upper cavea: floor at outside-ground level, retaining walls either side, bridged by the verandah
    for g in gates:
        tx, ty = -math.sin(g), math.cos(g)
        mid = (walk_r0 + WALL_OUT) / 2; length = WALL_OUT - walk_r0 + .5
        k.box(*P(mid, g), rim - .4, rim, length, GATE_W + .4, g, M["pave"])
        for sd in (-1, 1):
            k.box(P(mid + .6, g)[0] + tx * (GATE_W / 2 + .2) * sd, P(mid + .6, g)[1] + ty * (GATE_W / 2 + .2) * sd, z_orch - 1, z_ver,
                  length - 1.2, .4, g, M["ashlar"])
    # the verandah: floor, inward-facing colonnade, tiled roof sloping gently inward
    gate_cuts = [(g, (GATE_W / 2) / ver_r) for g in gates]                                          # within the passage walls at every radius
    for a0, a1 in between(gate_cuts + [(a, stair_half_at(ver_r + VER_STEP)) for a in stair_angles]):
        k.ring(X, Y, ver_r, ver_r + VER_STEP, z_orch - 1, z_ver, M["pave"], 64, a0, a1)
    for a0, a1 in between(gate_cuts):
        k.ring(X, Y, ver_r + VER_STEP, WALL_IN, z_orch - 1, z_ver, M["pave"], 64, a0, a1)
    for a0, a1 in between([(a, stair_half_at(ver_r + .12)) for a in stair_angles]):
        k.ring(X, Y, ver_r, ver_r + .12, z_ver - .08, z_ver + .02, M["marble"], 32, a0, a1)
    for g in gates:                                                                                 # the verandah bridges each passage above the doorway's height
        k.box(*P((ver_r + WALL_IN) / 2, g), rim + DOOR_H, z_ver, WALL_IN - ver_r + .1, GATE_W + .8, g, M["pave"])
    col_r = ver_r + .45; per_span = round(TAU / STAIRS * col_r / 2.6)                             # spaced within each span between stairways, so no column stands at a stair head
    col_angles = [sa + (c_ + .5) * (TAU / STAIRS) / per_span for sa in stair_angles for c_ in range(per_span)]
    for a in col_angles:
        cx, cy = P(col_r, a)
        k.cyl(cx, cy, .3, z_ver, z_ver + .25, M["marble"], 10)                                    # base
        k.frustum(cx, cy, .24, .20, z_ver + .25, z_ver + VERANDAH_H - .35, M["marble"], 10)
        k.box(cx, cy, z_ver + VERANDAH_H - .35, z_ver + VERANDAH_H, .62, .62, a, M["marble"])     # capital
    k.ring(X, Y, ver_r + .1, ver_r + .8, z_ver + VERANDAH_H, z_ver + VERANDAH_H + .55, M["marble"], 128)   # architrave
    k.ring(X, Y, ver_r - .35, WALL_IN, z_ver + VERANDAH_H + .55, z_ver + VERANDAH_H + .85, M["tile"], 128)   # roof
    # ring wall with a row of windows along the verandah, broken by the gate pylons
    sill, head, top_ = rim + SILL_UP, rim + SILL_UP + WIN_H, z_ver + VERANDAH_H + 1.4
    windows = []
    for g in range(4):
        a0 = gates[g] + math.radians(3.2) + math.asin((GATE_W / 2 + .1) / 24.2)
        a1 = gates[(g + 1) % 4] - math.radians(3.2) - math.asin((GATE_W / 2 + .1) / 24.2) + (TAU if g == 3 else 0)
        k.ring(X, Y, WALL_IN, WALL_OUT, z_orch - 1, sill, M["ashlar"], 96, a0, a1)
        k.ring(X, Y, WALL_IN, WALL_OUT, head, top_, M["ashlar"], 96, a0, a1)
        k.ring(X, Y, WALL_IN - .2, WALL_OUT + .45, top_ - .35, top_ + .15, M["marble"], 96, a0, a1)   # cornice
        k.ring(X, Y, WALL_IN - .05, WALL_OUT + .12, sill - .12, sill, M["marble"], 96, a0, a1)        # continuous sill course
        half_w = (WIN_W / 2) / 24.2
        wins = [a for a in np.arange(gates[g] + math.radians(PYLON_HALF_DEG + 2.5), gates[g] + TAU / 4 - math.radians(PYLON_HALF_DEG + 2.4), math.radians(WIN_STEP_DEG))]
        edges = [a0] + [w for a in wins for w in (a - half_w, a + half_w)] + [a1]
        for e0, e1 in zip(edges[0::2], edges[1::2]):
            k.ring(X, Y, WALL_IN, WALL_OUT, sill, head, M["ashlar"], 8, e0, e1)                     # piers between the windows
        windows += [a % TAU for a in wins]
        for pa in np.arange(a0 + math.radians(2.5), a1 - math.radians(1), math.radians(WIN_STEP_DEG)):
            k.box(*P(WALL_OUT + .3, pa), rim - 1, sill - .12, .6, 1.0, pa, M["ashlar"])           # pilasters below the window piers
    # gateways
    doors_open = {g: "ENWS"[g] not in GATES_BARRED for g in range(4)}                               # the east gate faces the banquet house
    rm = (WALL_IN + WALL_OUT) / 2
    for g, th in enumerate(gates):
        tx, ty = -math.sin(th), math.cos(th); rx_, ry_ = math.cos(th), math.sin(th); cx, cy = P(rm, th)
        for sd in (-1, 1):
            px, py = cx + tx * (GATE_W / 2 + 1.7) * sd, cy + ty * (GATE_W / 2 + 1.7) * sd
            k.box(px + rx_ * .75, py + ry_ * .75, z_orch - 1, top_ + 1.6, 4.6, 3.4, th, M["ashlar"])
            k.box(px + rx_ * .75, py + ry_ * .75, top_ + 1.6, top_ + 2.0, 5.0, 3.8, th, M["marble"])
            k.box(cx + tx * (GATE_W / 2 + .15) * sd + rx_ * 1.2, cy + ty * (GATE_W / 2 + .15) * sd + ry_ * 1.2, rim, rim + DOOR_H, .5, .3, th, M["marble"])
        k.box(cx + rx_ * .75, cy + ry_ * .75, rim + DOOR_H, rim + DOOR_H + .9, 4.6, GATE_W + .6, th, M["marble"])                 # lintel
        k.box(cx + rx_ * .75, cy + ry_ * .75, rim + DOOR_H + .9, top_ + 1.6, 4.6, GATE_W + 2.0, th, M["ashlar"])               # attic above
        k.gable(cx + rx_ * 3.1, cy + ry_ * 3.1, top_ + 2.0, 1.2, GATE_W + 6.8, 1.9, th, M["marble"])                           # pediment
        k.box(cx + rx_ * 2.1, cy + ry_ * 2.1, rim, rim + .22, .6, GATE_W, th, M["marble"])                                      # threshold
        leaf_w = GATE_W / 2 - .03
        for sd in (-1, 1):
            hx, hy = cx + tx * (GATE_W / 2) * sd, cy + ty * (GATE_W / 2) * sd
            phi = math.radians(80) if doors_open.get(g) else 0.0
            wx, wy = math.cos(phi) * -sd * tx + math.sin(phi) * -rx_, math.cos(phi) * -sd * ty + math.sin(phi) * -ry_
            ang = math.atan2(wy, wx) - math.pi / 2
            mx, my = hx + wx * leaf_w / 2, hy + wy * leaf_w / 2
            k.box(mx, my, rim + .22, rim + DOOR_H - .08, .18, leaf_w, ang, M["bronze"])
            for row in range(2):
                pz = rim + .55 + row * 1.7
                k.box(mx, my, pz, pz + 1.4, .26, leaf_w - .35, ang, M["bronze"])
                for col in range(3):
                    f = ((col + .5) / 3 - .5) * (leaf_w - .55)
                    k.box(mx + wx * f, my + wy * f, pz + .64, pz + .77, .32, .13, ang, M["bronze"])
        if not doors_open.get(g):
            ix, iy = cx - rx_ * .35, cy - ry_ * .35
            k.box(ix, iy, rim + BAR_Z - .14, rim + BAR_Z + .14, .28, GATE_W + 1.0, th, M["oak"])
            for sd in (-1, 1):
                k.box(ix + tx * (GATE_W / 2 + .2) * sd, iy + ty * (GATE_W / 2 + .2) * sd, rim + BAR_Z - .2, rim + BAR_Z + .2, .45, .12, th, M["iron"])
        else:                                                                                       # the bar stands against the passage wall, clear of the open leaf
            bx, by = cx + tx * (GATE_W / 2 - .15), cy + ty * (GATE_W / 2 - .15)
            k.beam((bx - rx_ * 5.3, by - ry_ * 5.3, rim), (bx - rx_ * 2.3, by - ry_ * 2.3, rim + DOOR_H - .15), .26, .26, M["oak"])
    # a paved terrace round the wall, level with the gate thresholds: the 12.5 m terrain cells either side of the bowl's
    # edge otherwise slope down outside the wall, leaving a ditch up to 4.8 m deep (found staging panel IV-03)
    k.ring(X, Y, WALL_OUT - .2, TERRACE_R, z_orch - 1, rim, M["pave"], 128)
    k.ring(X, Y, TERRACE_R, TERRACE_R + .5, z_orch - 1, rim + .15, M["marble"], 128)
    statues = 0
    for sidx in range(24):
        th = sidx * TAU / 24
        if near_gate(th, math.radians(12)): continue
        sx, sy = P(29.5, th)
        statue(k, M, sx, sy, rim, th, "orator" if sidx % 3 == 0 else ("scroll" if sidx % 3 == 1 else "stand")); statues += 1

    people = Kit("V · Scale figures (1.75 m)")
    cloth = [M["himation_blue"], M["himation_ochre"], M["chiton"]]
    for n, (r_, a_, face) in enumerate(((31, .12, math.pi), (31.8, -.1, math.pi), (33, .02, math.pi + .3))):
        fx, fy = P(r_, a_); figure(people, fx, fy, max(ground.z(fx, fy), rim), a_ + face, "stand", M["chiton"], cloth[n], M["skin"])   # on the terrace
    for n, a_ in enumerate((1.2, 2.3)):
        fx, fy = P(3.0, a_); figure(people, fx, fy, z_orch, a_ + math.pi, "orator" if n == 0 else "scroll", M["chiton"], cloth[n], M["skin"])
    east_win = min(windows, key=lambda a: abs((a + math.pi) % TAU - math.pi))
    for dr, dd in ((22.3, 0.0), (21.6, .03)):
        fx, fy = P(dr, east_win + dd); figure(people, fx, fy, z_ver, east_win, "stand", M["chiton"], cloth[1], M["skin"])

    info = {"rim": rim, "z_orch": z_orch, "z_verandah": z_ver, "seat_rows": len(rows), "tiers_incl_verandah": len(rows) + 1,
            "stairs": len(stair_angles), "gates_deg": [round(math.degrees(g) % 360) for g in gates], "windows": len(windows),
            "outer_diameter_m": round(2 * WALL_OUT, 1), "tread_m": TREAD, "seat_risers_m": [LOWER_RISE, UPPER_RISE],
            "door_height_m": DOOR_H, "doors_open": ["ENWS"[g] for g in range(4) if doors_open[g]], "drop_bar_height_m": BAR_Z, "statues": statues, "figure_m": FIGURE_H,
            "verandah_floor_above_ground_m": VERANDAH_UP, "window_sill_above_ground_m": SILL_UP, "walkway_z": rim,
            "gate_floor_z": rim, "sunk_m": round(rim - z_orch, 2), "windows_rad": windows, "centre": (X, Y),
            "stair_rad": stair_angles, "stair_span_r": (KERB_R, ver_r + VER_STEP), "walkway_r": (walk_r0, walk_r1), "columns": len(col_angles)}
    return k, people, info

def window_eye(info, target):
    """Standing on the verandah at the window nearest the bearing to `target`."""
    X, Y = info["centre"]; bearing = math.atan2(target[1] - Y, target[0] - X)
    a = min(info["windows_rad"], key=lambda w: abs((w - bearing + math.pi) % TAU - math.pi))
    return (X + 23.2 * math.cos(a), Y + 23.2 * math.sin(a), info["z_verandah"] + 1.6), math.degrees(a)   # standing at the sill

def sight(p, q, obs):
    p, q = Vector(p), Vector(q); d = q - p; L = d.length; d.normalize()
    return [name for name, ob, pad in obs if ob.ray_cast(p + d * .3, d, distance=L - pad)[0]]

def checks(info, round_ob, terrain, banquet_xyz, port_xyz, extra=()):
    """Canon and human-scale checks, and the views from the verandah through its windows (also through `extra` (name, object, pad), e.g. props)."""
    obs = [("the Round", round_ob, .5), ("terrain", terrain, 3.0), *extra]
    eye_b, win_b = window_eye(info, banquet_xyz); eye_p, win_p = window_eye(info, port_xyz)
    block_b, block_p = sight(eye_b, banquet_xyz, obs), sight(eye_p, port_xyz, obs)
    res = {k_: v for k_, v in info.items() if k_ not in ("windows_rad", "centre", "stair_rad", "stair_span_r", "walkway_r")}
    X, Y = info["centre"]; gate_ground, edge_step = {}, {}
    down = lambda x, y, z: (lambda h: h[1].z + round_ob.location.z if h[0] else None)(round_ob.ray_cast(Vector((x, y, z)) - round_ob.location, Vector((0, 0, -1))))
    # each stairway, sampled every 5 cm down its centreline from the kerb to the verandah: every riser, every going, no hole
    r0, r1 = info["stair_span_r"]; rs = np.arange(r0 + .02, r1 - .02, .05); risers, goings, drops, holes, top_gap = [], [], [], 0, 0.0
    for a, off in ((a, off) for a in info["stair_rad"] for off in (0, -.5, .5)):                # the centreline and 0.5 m either side, which would meet a column at the stair head
        zs = [down(X + r * math.cos(a) - off * math.sin(a), Y + r * math.sin(a) + off * math.cos(a), info["z_verandah"] + 1) for r in rs]
        holes += sum(z is None or z < info["z_orch"] - .05 for z in zs)
        zs = [info["z_orch"] - 1 if z is None else z for z in zs]
        dz = np.diff(zs); rise_at = [rs[i + 1] for i in np.nonzero(dz > .02)[0]]
        risers.append(float(dz.max())); drops.append(max(0.0, -float(dz.min()))); goings.append(float(np.diff(rise_at).min()))
        top_gap = max(top_gap, abs(zs[-1] - info["z_verandah"]))
    res.update({"stair_riser_max_m": round(max(risers), 3), "stair_going_min_m": round(min(goings), 3), "stair_drop_max_m": round(max(drops), 3),
                "stair_hole_samples": holes, "stair_top_to_verandah_m": round(top_gap, 3)})
    # each open gate's passage, by horizontal rays from the terrace to the walkway at knee and head height and beside the axis
    walk_mid = sum(info["walkway_r"]) / 2; gates_blocked = {}
    for name, a in (("E", 0.0), ("N", TAU / 4), ("W", TAU / 2), ("S", 3 * TAU / 4)):
        if name not in info["doors_open"]: continue
        c, s_, hit = math.cos(a), math.sin(a), []
        for off, zz in ((0, 1.0), (0, 3.6), (-1.2, 1.0), (1.2, 1.0)):
            p = (X + 33 * c - off * s_, Y + 33 * s_ + off * c, info["rim"] + zz); q = (X + walk_mid * c - off * s_, Y + walk_mid * s_ + off * c, info["rim"] + zz)
            if sight(p, q, [("the Round", round_ob, 0.0)]): hit.append(f"{off:+.1f} m at {zz} m")
        if hit: gates_blocked[name] = hit
    res["gates_blocked"] = gates_blocked                                          # the forecourt outside each gate must meet its threshold
    for name, a in (("E", 0.0), ("N", TAU / 4), ("W", TAU / 2), ("S", 3 * TAU / 4)):
        offs = []
        for rr in (26, 28, 30, 33, 35.5):                                                           # the walking surface: the higher of the Round's terrace and the terrain
            zs = []
            for ob in (terrain, round_ob):
                hit, loc, *_ = ob.ray_cast(Vector((X + rr * math.cos(a) - .9 * math.sin(a), Y + rr * math.sin(a) + .9 * math.cos(a), info["rim"] + 2)) - ob.location, Vector((0, 0, -1)))
                if hit: zs.append(loc.z + ob.location.z)
            offs.append(max(zs) - info["rim"] if zs else -99)
        gate_ground[name] = round(max(offs[:4], key=abs), 2); edge_step[name] = round(offs[4], 2)
    res["gate_ground_offset_m"] = gate_ground; res["terrace_edge_step_m"] = edge_step
    res["gates_meet_the_ground"] = all(abs(v) <= .6 for v in gate_ground.values()) and all(abs(v) <= 1.2 for v in edge_step.values())
    res.update({"banquet_window_bearing_deg": round(win_b, 1), "quays_window_bearing_deg": round(win_p, 1),
                "canon_14_tiers": info["tiers_incl_verandah"] == 14, "canon_stairways_8": info["stairs"] == 8,
                "canon_gates_cardinal": sorted(info["gates_deg"]) == [0, 90, 180, 270],
                "canon_about_50m_across": abs(info["outer_diameter_m"] - 50) <= 2,
                "seat_risers_comfortable": all(.35 <= r_ <= .65 for r_ in info["seat_risers_m"]),
                "stair_riser_climbable": res["stair_riser_max_m"] <= .31 and res["stair_going_min_m"] >= .28,
                "stairs_continuous_orchestra_to_verandah": res["stair_hole_samples"] == 0 and res["stair_drop_max_m"] <= .02 and res["stair_top_to_verandah_m"] <= .05,
                "gates_open_right_through": not gates_blocked and len(info["doors_open"]) + len(GATES_BARRED) == 4,
                "verandah_about_15ft_up": abs(info["verandah_floor_above_ground_m"] - 4.57) <= .3,
                "window_sills_read_as_windows": info["window_sill_above_ground_m"] >= 4.5,
                "gates_join_below_the_verandah": info["gate_floor_z"] == info["walkway_z"] and info["gate_floor_z"] < info["z_verandah"] - 3,
                "doorway_at_least_2_2_figures": info["door_height_m"] >= 2.2 * info["figure_m"],
                "drop_bar_liftable_0_9_to_1_6m": .9 <= info["drop_bar_height_m"] <= 1.6,
                "banquet_house_seen_from_verandah_window": not block_b, "banquet_view_blocked_by": block_b,
                "quays_seen_from_verandah_window": not block_p, "quays_view_blocked_by": block_p})
    res["ok"] = all(v for k_, v in res.items() if k_.startswith(("canon_", "seat_risers_", "stair_riser_c", "stairs_continuous", "verandah_about", "window_sills",
                                                               "gates_join", "gates_meet", "gates_open", "doorway_", "drop_bar_l")) or k_ in ("banquet_house_seen_from_verandah_window", "quays_seen_from_verandah_window"))
    return res
