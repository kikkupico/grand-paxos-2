"""Stage 3b: the key buildings, placed on the terrain.

  ~/.local/bin/blender -b -P tools/blender_buildings.py              build terrain + buildings, save blender/paxos.blend
  ~/.local/bin/blender -b -P tools/blender_buildings.py -- --render  also render renders/buildings-*.png

Starts from a fresh terrain scene (blender_terrain.build), levels the ground where a building needs it
(pads are edits to the Blender mesh only; the heightmap stays the spec), then builds pre-vis models at true
scale from the site list, the town layout and the canon: the Great Round and the banquet house (IV), the
lantern harbour (III), the merchant quays and harbour town (IV), the besieged headland city and its siege
camps (V), and the citadel with its walled harbour (VII). Checks go to blender/buildings-checks.json and
the page between <!-- BUILDINGS --> markers.
"""
import json, math, random, sys
from pathlib import Path
import bpy
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import blender_terrain as bt

from blender_kit import *                                                                          # noqa: F401,F403
import blender_sites as bs
import blender_nature as bn
import blender_round as br
import blender_arch as ba
import blender_props as bp

# ---------------------------------------------------------------- the buildings
def banquet_house(ground, M, coll, report, round_xy):
    """A garden dining house (hestiatorion) facing the Round's east gate: an entrance porch and vestibule on the side
    toward the Round, a peristyle garden court with a fountain, and the dining room (andron) behind it with eleven couches."""
    X, Y = site("banquet"); g0 = ground.z(X, Y)
    report["Banquet house"] = {"volume": "V", "radius_m": 17, "relief_before_m": ground.relief(X, Y, 16)[0]}
    ground.pad(X, Y, 18, g0, 25)
    ang = math.atan2(round_xy[1] - Y, round_xy[0] - X)                                             # local +x points at the Round
    c, s = math.cos(ang), math.sin(ang); P = lambda u, v: (X + u * c - v * s, Y + u * s + v * c)
    f = g0 + .8
    k = Kit("V · Banquet house")
    k.box(X, Y, g0 - 2, f, 32, 22, ang, M["limestone"])
    for i in range(2): k.box(*P(16.4 + i * .45, 0), g0 - .5, f - .4 * i - .4, .45, 6, ang, M["limestone"])   # entrance steps
    for v in (-4.5, -1.5, 1.5, 4.5): ba.column(k, *P(14.3, v), f, f + 3.8, .28, M["marble"])        # porch
    k.box(*P(12.8, 0), f + 3.8, f + 4.3, 3.8, 11, ang, M["marble"]); k.box(*P(12.9, 0), f + 4.3, f + 4.5, 4.2, 11.6, ang, M["roof"])   # flat porch roof
    vx, vy = P(8.5, 0)                                                                              # vestibule range
    k.box(vx, vy, f, f + 5.2, 5, 22, ang, M["plaster"]); k.gable(vx, vy, f + 5.2, 5.8, 22.8, 1.6, ang + math.pi / 2, M["roof"])
    ba.opening(k, vx, vy, ang, 5, 22, "+x", 0, 1.6, f, f + 2.7)
    for v in (-7, 7): ba.opening(k, vx, vy, ang, 5, 22, "+x", v, .7, f + 2.0, f + 2.9)
    ba.opening(k, vx, vy, ang, 5, 22, "-x", 0, 1.6, f, f + 2.7)
    k.box(*P(-.5, 0), f, f + .12, 11, 11, ang, M["garden"])                                          # garden court
    k.cyl(*P(-.5, 0), 1.2, f, f + .6, M["marble"], 16); k.cyl(*P(-.5, 0), .25, f + .6, f + 1.5, M["marble"], 8)
    for u, v in ((-4, -4), (-4, 4), (3, -4), (3, 4)): k.box(*P(u, v), f, f + .7, 1, 1, ang, M["limestone"])
    colonnade(k, *P(-.5, 0), f, f + 3.2, 13, 13, ang, 2.6, M["marble"], .24)
    for u, v, sx, sy in ((-.5, 7.9, 16, 2.8), (-.5, -7.9, 16, 2.8)):
        k.box(*P(u, v), f + 3.2, f + 3.6, sx, sy, ang, M["roof"])
    ax_, ay_ = P(-11.5, 0); ad, aw = 8, 20                                                         # the andron
    k.box(ax_, ay_, f, f + 6, ad, aw, ang, M["plaster"]); k.gable(ax_, ay_, f + 6, ad + .8, aw + .8, 2.2, ang + math.pi / 2, M["roof"])
    ba.opening(k, ax_, ay_, ang, ad, aw, "+x", 0, 1.8, f, f + 2.8)
    for v in (-6, 0, 6): ba.opening(k, ax_, ay_, ang, ad, aw, "-x", v, .8, f + 2.6, f + 3.6)
    couches = 0                                                                                      # eleven couches along the andron's inner walls
    for i in range(4): k.box(*P(-15.1 + .45, -7.5 + i * 2.0 + 1.0), f, f + .55, .9, 1.9, ang, M["timber"]); couches += 1
    for sd in (-1, 1):
        for i in range(3): k.box(*P(-14.6 + i * 2.0 + .6, sd * (aw / 2 - .75)), f, f + .55, 1.9, .9, ang, M["timber"]); couches += 1
    k.box(*P(-8.2, -6.5), f, f + .55, .9, 1.9, ang, M["timber"]); couches += 1
    return k, {"faces_round_deg": 0.0, "couches": couches, "door_h_m": 2.8, "porch_columns": 4}

def lantern_harbour(ground, M, coll, report):
    info = SITES["built"]["cothon"]
    X, Y = B(*info["centre_m"])
    th_c = math.radians(-info["channel_bearing_deg_from_x_toward_y"])                             # map y points south
    R, RI = info["basin_radius_m"], info["islet_radius_m"]
    report["Lantern harbour"] = {"volume": "IV", "radius_m": 270}
    def level(d, dX, dY, g):
        along = dX * math.cos(th_c) + dY * math.sin(th_c); across = np.abs(-dX * math.sin(th_c) + dY * math.cos(th_c))
        channel = (along > 0) & (across < 24)
        quay = (d >= R - 1) & (d < 250) & ~channel                                                  # right up to the basin wall: no stray hill vertices
        w = 1 - smooth((d - 250) / 60)
        g = np.where(quay, 2.8, np.where((d >= 250) & ~channel & (g > 2.8), g * (1 - w) + 2.8 * w, g))
        return np.where(d < RI, 2.6, g)
    ground.edit(X, Y, 320, level)
    k = Kit("IV · Lantern harbour (cothon)")
    gap = math.radians(9)
    k.ring(X, Y, R, R + 6, -4, 2.8, M["limestone"], 128, th_c + gap, th_c + TAU - gap)
    k.ring(X, Y, RI, RI + 2, -4, 2.6, M["limestone"], 48)
    free = TAU - 2 * math.radians(25); posts = []
    for p in range(7):                                                                               # seven quays, one captain's post each
        th = th_c + math.radians(25) + (p + .5) * free / 7
        k.box(X + (R - 21) * math.cos(th), Y + (R - 21) * math.sin(th), -3, 2.6, 42, 8, th, M["limestone"])
        for j in range(4):                                                                           # bollards along the quay
            br_ = R - 38 + j * 11
            for sd in (-1, 1):
                bx_, by_ = X + br_ * math.cos(th) - sd * 3.4 * math.sin(th), Y + br_ * math.sin(th) + sd * 3.4 * math.cos(th)
                k.cyl(bx_, by_, .28, 2.6, 3.4, M["ashlar"], 10)
        px, py = X + (R + 14) * math.cos(th), Y + (R + 14) * math.sin(th)
        house(k, ground, px, py, 6, 6, 3.5, th, M["plaster"], M["roof"])
        lx, ly = X + (R + 5) * math.cos(th) - 3.2 * math.sin(th), Y + (R + 5) * math.sin(th) + 3.2 * math.cos(th)   # the captain's lamp post, beside the quay's head
        k.cyl(lx, ly, .18, 2.8, 7.2, M["timber"], 8); k.box(lx, ly, 7.2, 7.9, .7, .7, th, M["lantern"])
        posts.append(((X + (R + 8) * math.cos(th), Y + (R + 8) * math.sin(th), 2.8 + 1.6), p))
    # the lighthouse on the islet: podium, tapering shaft with string courses and slit windows, gallery, lantern room
    k.box(X, Y, 2.5, 5.5, 14, 14, th_c, M["ashlar"])
    k.box(X, Y, 5.5, 5.8, 14.8, 14.8, th_c, M["limestone"])
    k.frustum(X, Y, 6.2, 5.0, 5.8, 26, M["limestone"], 24)
    for zz in (11, 17, 23): k.ring(X, Y, 6.2 - (zz - 5.8) / 20.2 * 1.2 - .05, 6.4 - (zz - 5.8) / 20.2 * 1.2, zz, zz + .45, M["marble"], 24)
    for n_, zz in enumerate((8, 13.5, 19)):
        a_ = th_c + math.pi + n_ * 1.9; r_ = 6.2 - (zz + .6 - 5.8) / 20.2 * 1.2
        k.box(X + (r_ + .02) * math.cos(a_), Y + (r_ + .02) * math.sin(a_), zz, zz + 1.3, .12, .45, a_, ba.dark())
    dx_, dy_ = X + 7.05 * math.cos(th_c + math.pi), Y + 7.05 * math.sin(th_c + math.pi)
    k.box(dx_, dy_, 5.8, 8.2, .1, 1.3, th_c, ba.dark())                                               # door, reached up the podium steps
    for i_ in range(3): k.box(X + (7.6 + i_ * .45) * math.cos(th_c + math.pi), Y + (7.6 + i_ * .45) * math.sin(th_c + math.pi), 2.5, 5.5 - i_ * 1.0, .45, 2.2, th_c, M["limestone"])
    k.ring(X, Y, 4.6, 6.6, 26, 26.4, M["marble"], 32)                                                 # gallery floor
    k.ring(X, Y, 6.3, 6.6, 26.4, 27.5, M["marble"], 32)                                               # gallery parapet
    for i_ in range(8):
        a_ = i_ * TAU / 8; ba.column(k, X + 3.6 * math.cos(a_), Y + 3.6 * math.sin(a_), 26.4, 30.4, .28, M["marble"])
    k.cyl(X, Y, 2.4, 26.4, 28.0, M["bronze"], 16); k.cyl(X, Y, 1.9, 28.0, 29.6, M["lantern"], 16)     # the fire bowl, its flame clear of the parapet from the quays
    k.cyl(X, Y, 4.3, 30.4, 30.9, M["marble"], 24); k.cone(X, Y, 4.6, 30.9, 34.2, M["bronze"], 24)
    k.cyl(X, Y, .25, 34.2, 35.4, M["bronze"], 8)
    lantern_xyz = (X, Y, 28.2)
    tx, ty = -math.sin(th_c), math.cos(th_c)
    mid = (R + 265) / 2
    for side in (-1, 1):
        cx, cy = X + math.cos(th_c) * mid + tx * 23 * side, Y + math.sin(th_c) * mid + ty * 23 * side
        k.box(cx, cy, -4, 2.8, 265 - R, 3, th_c, M["limestone"])
        ex, ey = X + math.cos(th_c) * 268 + tx * 27 * side, Y + math.sin(th_c) * 268 + ty * 27 * side
        k.box(ex, ey, -4, 16, 9, 9, th_c, M["ashlar"])
    basin = [ground.z(X + 100 * math.cos(a), Y + 100 * math.sin(a)) for a in np.linspace(0, TAU, 16, endpoint=False)]
    report["Lantern harbour"]["basin_depth_m"] = round(float(np.median(basin)), 1)
    return k, {"posts": posts, "lantern": lantern_xyz, "quays": 7, "tower_top_m": 35.4}

def merchant_quays(ground, M, coll, report):
    X, Y = site("port"); s = ground.seaward(X, Y)
    SX, SY = ground.shore(X, Y, s)
    ang = math.atan2(s[1], s[0]); tx, ty = -s[1], s[0]
    report["Merchant quays"] = {"volume": "V", "radius_m": 110}
    k = Kit("V · Merchant quays")
    k.box(SX + s[0] * 2, SY + s[1] * 2, -4, 1.8, 14, 200, ang, M["limestone"])
    tips = []
    for off in (-70, 0, 70):
        cx, cy = SX + s[0] * 44.5 + tx * off, SY + s[1] * 44.5 + ty * off
        k.box(cx, cy, -4, 1.8, 75, 9, ang, M["limestone"])
        tips.append(ground.z(SX + s[0] * 80 + tx * off, SY + s[1] * 80 + ty * off))
    for off in (-40, 40):                                                                           # warehouses behind the quay
        house(k, ground, SX - s[0] * 26 + tx * off, SY - s[1] * 26 + ty * off, 13, 55, 7, ang, M["plaster"], M["roof"])
    report["Merchant quays"]["pier_tip_depths_m"] = [round(t, 1) for t in tips]
    return k, {"shore": (SX, SY), "s": (float(s[0]), float(s[1]))}

def harbour_town(ground, M, coll, report):
    town = SITES["built"]["town"]
    ax, ay = B(*town["agora_m_deg"][:2]); aang = math.radians(-town["agora_m_deg"][2])
    report["Harbour town"] = {"volume": "V", "insulae": len(town["insulae_m_deg"])}
    k = Kit("V · Harbour town and agora")
    ca_, sa_ = math.cos(aang), math.sin(aang)
    level = float(np.median([ground.z(ax + u * ca_ - v * sa_, ay + u * sa_ + v * ca_) for u in np.linspace(-20, 20, 5) for v in np.linspace(-15, 15, 4)]))
    ground.pad(ax, ay, 24, level, 30)                                                               # a levelled square, not a podium
    lo, hi = level - .6, level
    k.box(ax, ay, lo, hi + .25, 40, 30, aang, M["pave"])
    c, s = math.cos(aang), math.sin(aang)
    sx_, sy_ = ax - 19.5 * s * -1, ay + 19.5 * c                                                     # stoa along one long side
    sx_, sy_ = ax - (-19.5) * s, ay + (-19.5) * c
    sx_, sy_ = ax + 19.5 * -s, ay + 19.5 * c
    k.box(sx_, sy_, hi, hi + 7, 40, 9, aang, M["plaster"])
    k.gable(sx_, sy_, hi + 7, 41, 10, 2.2, aang, M["roof"])
    fx, fy = ax + 14.5 * -s, ay + 14.5 * c
    for i in range(13): ba.column(k, fx + (i - 6) * 3.2 * c, fy + (i - 6) * 3.2 * s, hi + .25, hi + 6, .35, M["marble"])
    for i in range(6): ba.opening(k, sx_, sy_, aang, 40, 9, "-y", -15 + i * 6, 1.4, hi, hi + 2.6)                # shop doors behind the colonnade
    k.cyl(ax, ay, 2.2, hi + .25, hi + 1, M["marble"], 16)                                           # fountain
    k.cyl(ax + 8 * c, ay + 8 * s, .4, hi + .25, hi + 3.2, M["marble"], 8)                           # sundial pillar
    for n, (x, y, deg) in enumerate(town["insulae_m_deg"]):
        X, Y = B(x, y); ang = math.radians(-deg); c, s = math.cos(ang), math.sin(ang)
        rnd = random.Random(n)
        for u, v, sx, sy in ((0, 10.5, 44, 9), (0, -10.5, 44, 9), (17, 0, 10, 12), (-17, 0, 10, 12)):
            if rnd.random() < .12: continue
            house(k, ground, X + u * c - v * s, Y + u * s + v * c, sx, sy, rnd.uniform(5, 8.5), ang if sx > sy else ang + math.pi / 2 * 0,
                  M["plaster"], M["roof"], rise=min(sx, sy) * .2)
    return k

def headland_city(ground, M, coll, report, toward):
    X, Y = site("city"); g0 = ground.z(X, Y)
    home = math.atan2(toward[1] - Y, toward[0] - X)
    walls = []
    for a in np.linspace(0, TAU, 28, endpoint=False):
        r = 115.0
        while r > 45 and ground.z(X + r * math.cos(a), Y + r * math.sin(a)) < 3: r -= 5
        walls.append((X + r * math.cos(a), Y + r * math.sin(a), a, r))
    gate = min(range(28), key=lambda i: abs((walls[i][2] - home + math.pi) % TAU - math.pi))
    report["Besieged headland city"] = {"volume": "III", "radius_m": max(w[3] for w in walls), "relief_before_m": ground.relief(X, Y, 80)[0]}
    k = Kit("III · Besieged headland city")
    for i in range(28):
        (x0, y0, _, _), (x1, y1, _, _) = walls[i], walls[(i + 1) % 28]
        if i == gate: continue
        L = math.hypot(x1 - x0, y1 - y0); za, zb = ground.z(x0, y0), ground.z(x1, y1)
        k.box((x0 + x1) / 2, (y0 + y1) / 2, min(za, zb) - 3, max(za, zb) + 9, L + 1.5, 3, math.atan2(y1 - y0, x1 - x0), M["ashlar"])
        mx_, my_ = (x0 + x1) / 2 - X, (y0 + y1) / 2 - Y; nn = math.hypot(mx_, my_)
        ba.crenellate(k, x0, y0, x1, y1, max(za, zb) + 9, (mx_ / nn, my_ / nn), 1.2, M["ashlar"])
    for i in range(0, 28, 2):
        x, y, a, _ = walls[i]; z = ground.z(x, y)
        k.box(x, y, z - 3, z + 14, 7, 7, a, M["ashlar"]); ba.crenellate_box(k, x, y, 7, 7, a, z + 14, M["ashlar"])
    for i in (gate, (gate + 1) % 28):
        x, y, a, _ = walls[i]; z = ground.z(x, y)
        k.box(x, y, z - 3, z + 16, 8, 8, a, M["ashlar"]); ba.crenellate_box(k, x, y, 8, 8, a, z + 16, M["ashlar"])
    rnd = random.Random(5); best = (g0, X, Y)
    c, s = math.cos(home), math.sin(home)
    for u in np.arange(-110, 111, 17):
        for v in np.arange(-110, 111, 17):
            x, y = X + u * c - v * s, Y + u * s + v * c
            a = math.atan2(y - Y, x - X); i = int(round(a / TAU * 28)) % 28
            if math.hypot(u, v) > walls[i][3] - 14 or ground.z(x, y) < 3: continue
            if ground.z(x, y) > best[0]: best = (ground.z(x, y), x, y)
            if rnd.random() < .3: continue
            house(k, ground, x, y, rnd.uniform(10, 13), rnd.uniform(8, 11), rnd.uniform(5, 7), home, M["plaster"], M["roof"])
    _, tx, ty = best                                                                                  # temple on the highest ground inside
    report["_city_temple"] = ba.temple(k, M, ground, tx, ty, home, 6, .9, n_side=11)
    camps = Kit("III · Siege camps")
    for n, (x, y, z) in enumerate(SITES["sites"]["camps"]["points_m"]):
        CX, CY = B(x, y); face = math.atan2(Y - CY, X - CX); gz = ground.z(CX, CY)
        camps.ring(CX, CY, 32, 32.4, gz - 2, gz + 2.6, M["timber"], 48, face + math.radians(8), face + TAU - math.radians(8))
        c2, s2 = math.cos(face), math.sin(face)
        for row in (-1, 1):
            for col in range(5):
                u, v = -16 + col * 8, row * 9
                px, py = CX + u * c2 - v * s2, CY + u * s2 + v * c2
                camps.gable(px, py, ground.z(px, py), 4.5, 3.5, 2.4, face, M["canvas"])
        camps.gable(CX - 18 * c2, CY - 18 * s2, ground.z(CX - 18 * c2, CY - 18 * s2), 9, 6, 3.5, face, M["canvas"])
    return k, camps

def citadel(ground, M, coll, report):
    X, Y = site("citadel"); HX, HY = site("seawall"); g0 = ground.z(X, Y)
    ang = math.atan2(HY - Y, HX - X); c, s = math.cos(ang), math.sin(ang)
    report["Citadel of Iron Quorums"] = {"volume": "VII", "radius_m": 82, "relief_before_m": ground.relief(X, Y, 70)[0]}
    samples = [ground.z(X + r * math.cos(q), Y + r * math.sin(q)) for r in (0, 30, 60) for q in np.linspace(0, TAU, 8, endpoint=False)]
    g0 = float(np.median(samples))                                                                  # level at the hilltop's median, not its centre
    ground.pad(X, Y, 50, g0, 85)
    k = Kit("VII · Citadel of Iron Quorums")
    L2, W2 = 65, 47.5
    corners = [(-L2, -W2), (L2, -W2), (L2, W2), (-L2, W2)]
    P = lambda u, v: (X + u * c - v * s, Y + u * s + v * c)
    for i in range(4):
        (u0, v0), (u1, v1) = corners[i], corners[(i + 1) % 4]
        for j in range(5):
            if i == 1 and j == 2: continue                                                          # gatehouse gap, facing the harbour
            f0, f1 = j / 5, (j + 1) / 5
            a, b = P(u0 + (u1 - u0) * f0, v0 + (v1 - v0) * f0), P(u0 + (u1 - u0) * f1, v0 + (v1 - v0) * f1)
            za, zb = ground.z(*a), ground.z(*b); top_ = max(za, zb) + 13
            k.box((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, min(za, zb) - 3, top_, math.hypot(b[0] - a[0], b[1] - a[1]) + 2, 4,
                  math.atan2(b[1] - a[1], b[0] - a[0]), M["wall_dark"])
            mu, mv = (u0 + u1) / 2, (v0 + v1) / 2; nn = math.hypot(mu, mv)
            wall_merlons = ba.crenellate(k, *a, *b, top_, ((mu * c - mv * s) / nn, (mu * s + mv * c) / nn), 1.7, M["wall_dark"])
        cx, cy = P(u0, v0); z = ground.z(cx, cy)
        k.cyl(cx, cy, 7.5, z - 3, z + 20, M["wall_dark"], 20); ba.crenellate_ring(k, cx, cy, 7.5, z + 20, M["wall_dark"])
        for zz in (z + 8, z + 14): k.box(cx + 7.52 * math.cos(ang + i * TAU / 4 + TAU / 8), cy + 7.52 * math.sin(ang + i * TAU / 4 + TAU / 8), zz, zz + 1.3, .12, .35, ang + i * TAU / 4 + TAU / 8, ba.dark())
        mx, my = P((u0 + u1) / 2, (v0 + v1) / 2)
        if i != 1:
            k.box(mx, my, ground.z(mx, my) - 3, ground.z(mx, my) + 17, 9, 9, ang, M["wall_dark"]); ba.crenellate_box(k, mx, my, 9, 9, ang, ground.z(mx, my) + 17, M["wall_dark"])
    gz = ground.z(*P(L2, 0))
    for side in (-1, 1):
        gx, gy = P(L2, side * 8.5); z = ground.z(gx, gy)
        k.box(gx, gy, z - 3, z + 19, 10, 10, ang, M["wall_dark"]); ba.crenellate_box(k, gx, gy, 10, 10, ang, z + 19, M["wall_dark"])
        k.box(*P(L2, side * 2.75), gz - 1, gz + 5.5, 4, 1.5, ang, M["wall_dark"])                       # gate jambs narrow the passage to 4 m
    k.box(*P(L2, 0), gz + 5.5, gz + 13, 4, 7, ang, M["wall_dark"])                                     # masonry over the gate passage
    ba.crenellate(k, *P(L2, -3.5), *P(L2, 3.5), gz + 13, (c, s), 1.7, M["wall_dark"])
    ba.portcullis(k, *P(L2 + 1.9, 0), ang, 4.0, gz + 3.2, 2.3, M["iron"])                              # portcullis, raised
    kx, ky = P(-10, 0)
    k.box(kx, ky, g0 - 2, g0 + 24, 26, 26, ang, M["wall_dark"]); ba.crenellate_box(k, kx, ky, 26, 26, ang, g0 + 24, M["wall_dark"])
    for face_ in ("+x", "-x", "+y", "-y"):
        for zz in (g0 + 8, g0 + 14, g0 + 19):
            for al in (-6, 0, 6): ba.opening(k, kx, ky, ang, 26, 26, face_, al, .35, zz, zz + 1.3)
    ba.opening(k, kx, ky, ang, 26, 26, "+x", 0, 2.0, g0 - .5, g0 + 3.0)
    hall = ba.temple(k, M, ground, *P(-42, 0), ang, 6, .9, n_side=9)                                   # the quorum hall, facing the courtyard
    report["_citadel_detail"] = {"merlon_h_m": wall_merlons["merlon_h_m"], "crenel_w_m": wall_merlons["crenel_w_m"], "wall_walk_w_m": 4 - .6,
                                 "gate_w_m": 4.0, "gate_h_m": 5.5, "hall": hall}
    for side in (-1, 1):
        bx, by = P(20, side * 30)
        k.box(bx, by, g0 - 1, g0 + 7, 45, 10, ang, M["plaster"]); k.gable(bx, by, g0 + 7, 46, 11, 2.4, ang, M["roof"])
    # the walled harbour below
    sw = ground.seaward(HX, HY); SX, SY = ground.shore(HX, HY, sw)
    th = math.atan2(sw[1], sw[0]); tx, ty = -sw[1], sw[0]
    h = Kit("VII · Citadel harbour and sea wall")
    a0, a1 = th - math.radians(75), th + math.radians(75)
    h.ring(SX, SY, 104, 116, -8, 3, M["ashlar"], 64, a0, a1)
    for a in (a0, a1): h.cyl(SX + 110 * math.cos(a), SY + 110 * math.sin(a), 5, -8, 12, M["ashlar"], 16)
    wall = []
    for d in np.arange(-150, 151, 25):
        px, py = SX + tx * d, SY + ty * d
        for e in np.arange(-150, 150, 2.5):
            if ground.z(px + sw[0] * e, py + sw[1] * e) < 1: wall.append((px + sw[0] * e, py + sw[1] * e)); break
    for (x0, y0), (x1, y1) in zip(wall, wall[1:]):
        h.box((x0 + x1) / 2, (y0 + y1) / 2, -2, 7, math.hypot(x1 - x0, y1 - y0) + 2, 3, math.atan2(y1 - y0, x1 - x0), M["ashlar"])
    h.box(SX + sw[0] * 6, SY + sw[1] * 6, -3, 2, 10, 60, th, M["limestone"])
    arc = [ground.z(SX + 110 * math.cos(a), SY + 110 * math.sin(a)) for a in np.linspace(a0, a1, 16)]
    report["Citadel harbour and sea wall"] = {"volume": "VII", "radius_m": 116, "breakwater_over_water_pct": round(100 * float(np.mean(np.array(arc) < 0)), 1)}
    return k, h, (SX, SY, th)

# ---------------------------------------------------------------- checks, cameras, main
def bearing_diff(a, b):
    return abs((a - b + math.pi) % TAU - math.pi)

def main():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    ctx = bt.build(); scene = ctx["scene"]
    ground = Ground(ctx["terrain"]); M = palette()
    top = bt.collection("Buildings")
    colls = {v: bt.collection(f"{v} · {bt.VOLUMES[v]}", top) for v in ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")}
    report = {}
    rk, round_people, round_info = br.build(ground, M, report)
    RX, RY = site("round"); rim = round_info["rim"]
    bk, banquet_info = banquet_house(ground, M, colls["V"], report, (RX, RY))
    ck, lantern_info = lantern_harbour(ground, M, colls["IV"], report)
    ground.commit()                                                                                  # later builders sample the levelled ground
    ck_city, ck_camps = headland_city(ground, M, colls["III"], report, (RX, RY))
    cit, harb, (HSX, HSY, HTH) = citadel(ground, M, colls["VII"], report)
    ground.commit()
    mq, port_geom = merchant_quays(ground, M, colls["V"], report)
    tw = harbour_town(ground, M, colls["V"], report)
    citadel_detail, city_temple = report.pop("_citadel_detail"), report.pop("_city_temple")
    round_ob = rk.finish(colls["V"]); round_people.finish(colls["V"])
    objs = [round_ob, bk.finish(colls["V"]), ck.finish(colls["IV"]), mq.finish(colls["V"]), tw.finish(colls["V"]),
            ck_city.finish(colls["III"]), ck_camps.finish(colls["III"]), cit.finish(colls["VII"]), harb.finish(colls["VII"])]

    # the remaining sites (tools/blender_sites.py)
    M.update(bs.extra_mats())
    hamlets = [bs.hamlet(ground, M, key, f"Hamlet {key[-1]}", n) for n, key in enumerate(("hamA", "hamK", "hamM"))]
    press = bs.olive_press(ground, M)
    beacons, fires = bs.beacon_towers(ground, M)
    watchtowers_k = bs.watchtowers(ground, M)
    drums, decks = bs.drummers(ground, M)
    markers, n_markers = bs.causeway_markers(ground, M)
    agora = B(*SITES["built"]["town"]["agora_m_deg"][:2])
    walk, walk_info = bs.statue_walk(ground, M, agora, gate_z=rim)
    grans, gran_gap = bs.granaries(ground, M)
    guild, guild_info = bs.guild_quarter(ground, M, None)
    monk, jetty_tip, jetty_geom = bs.monastery(ground, M, (RX, RY))
    guild_quay = guild_info.pop("quay")
    ground.commit()
    site_objs = [hk.finish(colls["I"]) for hk, _ in hamlets] + [press.finish(colls["I"]), beacons.finish(colls["I"]), watchtowers_k.finish(colls["II"]),
                 drums.finish(colls["IV"]), markers.finish(colls["IV"]), walk.finish(colls["V"]), grans.finish(colls["VI"]),
                 guild.finish(colls["VIII"]), monk.finish(colls["IX"])]
    terrain = ctx["terrain"]

    # the large props (tools/blender_props.py): ships, the Raft, market, carts, amphorae, crane
    cinfo = SITES["built"]["cothon"]; cth = math.radians(-cinfo["channel_bearing_deg_from_x_toward_y"])
    ax_, ay_ = B(*SITES["built"]["town"]["agora_m_deg"][:2])
    geo = {"cothon": {"X": B(*cinfo["centre_m"])[0], "Y": B(*cinfo["centre_m"])[1], "R": cinfo["basin_radius_m"], "ob": objs[2],
                      "quay_angles": [cth + math.radians(25) + (p + .5) * (TAU - 2 * math.radians(25)) / 7 for p in range(7)]},
           "port": {**port_geom, "ob": objs[3]}, "seawall": {"shore": (HSX, HSY), "th": HTH, "ob": objs[8]},
           "guild": {"shore": guild_quay[:2], "th": guild_quay[2], "ob": site_objs[-2]}, "monastery": {**jetty_geom, "ob": site_objs[-1]},
           "agora": {"X": ax_, "Y": ay_, "ang": math.radians(-SITES["built"]["town"]["agora_m_deg"][2]), "z": ground.z(ax_, ay_) + .25}, "terrain": terrain}
    track_lines = [bs.smooth_path([B(x, y) for x, y in t_["path"]], rounds=2) for t_ in SITES["built"]["tracks_m"] if len(t_["path"]) > 1]
    props, pres, pviews = bp.build(ground, M, colls, geo, track_lines, objs + site_objs)
    prop_obs = [o for o in props if len(o.data.polygons)]
    tops = [t for _, t in hamlets]
    ham_seen = [f"{'AKM'[i]}–{'AKM'[j]}" for i in range(3) for j in range(i + 1, 3) if bs.clear_sight(terrain, tops[i], tops[j])]
    summit_xy = B(2570, 1690); sz = ground.z(*summit_xy)
    lift = lambda p: (p[0], p[1], p[2] + 500)
    rays_work = all(bs.clear_sight(terrain, lift(tops[i]), lift(tops[j])) for i in range(3) for j in range(i + 1, 3)) \
        and not bs.clear_sight(terrain, (summit_xy[0] - 900, summit_xy[1], sz - 60), (summit_xy[0] + 900, summit_xy[1], sz - 60))       # self-test: clear 500 m up, blocked through the summit
    wt_pts = [site("watchtowers", i) for i in range(4)]
    wt_on_headlands = all(ground.z(*p) >= 20 for p in wt_pts)
    sres = {"sightline_self_test": rays_work, "hamlet_rooftops_in_sight": ham_seen, "beacon_fires_in_sight": bs.clear_sight(terrain, *fires, extra=prop_obs),
            "drum_decks_in_sight": bs.clear_sight(terrain, *decks, extra=prop_obs), "granary_min_gap_m": gran_gap,
            "watchtowers_on_coastal_headlands": wt_on_headlands, "watchtowers_count": len(wt_pts),
            "lock_houses": guild_info, "statue_walk": walk_info, "causeway_markers": n_markers, "monastery_jetty_tip_m": jetty_tip,
            "objects": len(site_objs), "faces": sum(len(o.data.polygons) for o in site_objs)}
    walk_outside = walk_info["closest_to_round_m"] - .75 >= br.TERRACE_R + .5 and walk_info["ends_before_gate_deg"] in (0, 90, 180, 270)   # slabs overrun each point by 0.75 m
    sres["statue_walk_stops_outside_the_round"] = walk_outside
    sres["ok"] = (walk_outside and rays_work and not ham_seen and sres["beacon_fires_in_sight"] and sres["drum_decks_in_sight"] and gran_gap >= 300
                  and wt_on_headlands and len(wt_pts) == 4 and guild_info["lock_ground_min_m"] > 1 and jetty_tip < -1)
    (bt.OUT / "sites-checks.json").write_text(json.dumps(sres, indent=1))
    print("SITES CHECKS", json.dumps(sres))
    bt.page_block("SITES",
                  [("Models", f"{sres['objects']} objects, {sres['faces']:,} faces"),
                   ("Statue Walk", f"{walk_info['length_m']} m, {walk_info['statues']} statues"),
                   ("…grade on its levelled bed", f"mean {walk_info['mean_grade_pct']}%, steepest {walk_info['max_grade_pct']}% (ground alone: {walk_info['max_grade_ungraded_pct']}%)"),
                   ("Granary storehouses, closest pair", f"{gran_gap} m apart"),
                   ("Lock-house spacing", ", ".join(f"{v} m" for v in guild_info["lock_spacing_m"])),
                   ("Causeway marker posts", str(n_markers)), ("Monastery jetty tip", f"{jetty_tip} m")],
                  [(f"Statue Walk stops outside the Round, at the terrace kerb before a gate (closest paving {walk_info['closest_to_round_m'] - .75:.2f} m from the centre; kerb {br.TERRACE_R + .5} m)", walk_outside),
                   ("Sightline test works (clear 500 m up, blocked through the summit)", rays_work),
                   ("Hamlet rooftops hidden from each other (rays through the terrain)", not ham_seen),
                   ("Beacon fires in sight of each other", sres["beacon_fires_in_sight"]),
                   ("Drum platforms in sight across the strait", sres["drum_decks_in_sight"]),
                   ("Granary storehouses at least 300 m apart", gran_gap >= 300),
                   ("Four coastal watchtowers on high headlands overlooking the sea", wt_on_headlands),
                   ("Lock-houses all on land", guild_info["lock_ground_min_m"] > 1),
                   ("Monastery jetty reaches water", jetty_tip < -1)])

    BX, BY = site("banquet")
    land = {n: site(k_) for n, k_ in (("The Great Round", "round"), ("Banquet house", "banquet"), ("Besieged headland city", "city"),
                                      ("Citadel of Iron Quorums", "citadel"))}
    circles = {"The Great Round": (RX, RY, 32), "Banquet house": (BX, BY, 17), "Besieged headland city": (*site("city"), report["Besieged headland city"]["radius_m"]),
               "Citadel of Iron Quorums": (*site("citadel"), 82), "Lantern harbour": (*B(*SITES["built"]["cothon"]["centre_m"]), 270),
               "Citadel harbour and sea wall": (HSX, HSY, 116)}
    names = list(circles)
    overlaps = [f"{a} / {b}" for i, a in enumerate(names) for b in names[i + 1:]
                if math.hypot(circles[a][0] - circles[b][0], circles[a][1] - circles[b][1]) < circles[a][2] + circles[b][2]]
    res = {"buildings": report, "objects": len(objs), "faces": sum(len(o.data.polygons) for o in objs),
           "round_east_gate_to_banquet_deg": round(math.degrees(bearing_diff(math.atan2(BY - RY, BX - RX), 0.0)), 1),
           "land_buildings_on_land": all(ground.z(x, y, before=True) > 1 for x, y in land.values()),
           "pier_tips_in_water": all(t < -1 for t in report["Merchant quays"]["pier_tip_depths_m"]),
           "cothon_basin_water": report["Lantern harbour"]["basin_depth_m"] < -3,
           "breakwater_mostly_over_water": report["Citadel harbour and sea wall"]["breakwater_over_water_pct"] >= 70,
           "footprint_overlaps": overlaps}
    res["ok"] = (res["round_east_gate_to_banquet_deg"] <= 30 and res["land_buildings_on_land"] and res["pier_tips_in_water"]
                 and res["cothon_basin_water"] and res["breakwater_mostly_over_water"] and not overlaps)
    (bt.OUT / "buildings-checks.json").write_text(json.dumps(res, indent=1))
    print("BUILDINGS CHECKS", json.dumps(res))
    rel = report
    bt.page_block("BUILDINGS",
                  [("Models", f"{res['objects']} objects, {res['faces']:,} faces"),
                   ("Ground relief levelled under the Round", f"{rel['The Great Round']['relief_before_m']} m"),
                   ("…under the citadel", f"{rel['Citadel of Iron Quorums']['relief_before_m']} m"),
                   ("Lantern harbour basin depth", f"{rel['Lantern harbour']['basin_depth_m']} m"),
                   ("Merchant pier tips", ", ".join(f"{t} m" for t in rel["Merchant quays"]["pier_tip_depths_m"])),
                   ("Breakwater over water", f"{rel['Citadel harbour and sea wall']['breakwater_over_water_pct']}%"),
                   ("Town insulae", str(rel["Harbour town"]["insulae"]))],
                  [(f"The Round's east gate faces the banquet house (within 30°: {res['round_east_gate_to_banquet_deg']}°)", res["round_east_gate_to_banquet_deg"] <= 30),
                   ("Land buildings stand on land", res["land_buildings_on_land"]),
                   ("Merchant pier tips reach water", res["pier_tips_in_water"]),
                   ("The cothon basin holds water (deeper than 3 m)", res["cothon_basin_water"]),
                   ("The breakwater stands mostly in the sea (≥70%)", res["breakwater_mostly_over_water"]),
                   ("No hero footprints overlap", not overlaps)])

    # the Great Round in detail: canon and human-scale checks (tools/blender_round.py)
    PXr, PYr = site("port")
    rres = br.checks(round_info, round_ob, ctx["terrain"], (BX, BY, ground.z(BX, BY) + 4), (PXr, PYr, ground.z(PXr, PYr) + 2),
                     extra=[(f"prop {o.name}", o, .5) for o in prop_obs])
    (bt.OUT / "round-checks.json").write_text(json.dumps(rres, indent=1))
    print("ROUND CHECKS", json.dumps(rres))
    bt.page_block("ROUND",
                  [("Across the ring wall", f"{rres['outer_diameter_m']} m"), ("Orchestra below the outside ground", f"{rres['sunk_m']} m"),
                   ("Seat rows · verandah · stairways · gates", f"{rres['seat_rows']} · 1 · {rres['stairs']} · {len(rres['gates_deg'])}"),
                   ("Verandah columns", str(rres["columns"])),
                   ("Seat rows", f"{rres['tread_m']} m treads, {rres['seat_risers_m'][0]} m rise below the walkway, {rres['seat_risers_m'][1]} m above"),
                   ("Verandah floor above the outside ground", f"{rres['verandah_floor_above_ground_m']} m (15 ft)"),
                   ("Window sills above the outside ground", f"{rres['window_sill_above_ground_m']} m; {rres['windows']} windows"),
                   ("Doorway · drop-bar", f"{rres['door_height_m']} m · {rres['drop_bar_height_m']} m above the threshold"),
                   ("Stair steps, measured down each stairway", f"risers up to {rres['stair_riser_max_m']} m, goings from {rres['stair_going_min_m']} m; a landing across the walkway"),
                   ("Doors standing open", ", ".join(rres["doors_open"]) or "none"),
                   ("Statues of legislators", str(rres["statues"]))],
                  [("14 tiers (13 seat rows and the verandah), 8 stairways, 4 cardinal gates, ~50 m across (canon)",
                    rres["canon_14_tiers"] and rres["canon_stairways_8"] and rres["canon_gates_cardinal"] and rres["canon_about_50m_across"]),
                   ("Seat rows and stair steps at human scale (risers ≤ 0.3 m, goings ≥ 0.28 m)", rres["seat_risers_comfortable"] and rres["stair_riser_climbable"]),
                   ("Every stairway unbroken from the orchestra to the verandah floor (no hole, no step down, no column at its head; sampled on the centreline and 0.5 m either side)", rres["stairs_continuous_orchestra_to_verandah"]),
                   ("Every open gate clear right through to the walkway (rays at 1 m and 3.6 m, and 1.2 m either side)", rres["gates_open_right_through"]),
                   ("Verandah about 15 ft above the outside ground", rres["verandah_about_15ft_up"]),
                   ("Window sills high enough to read as windows, not entrances", rres["window_sills_read_as_windows"]),
                   ("Gates open onto the walkway, below the verandah", rres["gates_join_below_the_verandah"]),
                   (f"Every gate's forecourt meets its threshold (±0.6 m; worst {max(rres['gate_ground_offset_m'].values(), key=abs)} m) and the terrace edge is a step, not a drop (≤1.2 m; worst {max(rres['terrace_edge_step_m'].values(), key=abs)} m)", rres["gates_meet_the_ground"]),
                   ("Drop-bar within a person's reach (0.9–1.6 m)", rres["drop_bar_liftable_0_9_to_1_6m"]),
                   (f"Banquet house seen from a verandah window ({rres['banquet_window_bearing_deg']}°)", rres["banquet_house_seen_from_verandah_window"]),
                   (f"Merchant quays seen from a verandah window ({rres['quays_window_bearing_deg']}°)", rres["quays_seen_from_verandah_window"])])

    # detailing the other hero buildings: human-scale and story checks (tools/blender_arch.py)
    from mathutils import Vector
    harbour_ob = objs[2]
    def blocked(p, q, stop):
        p, q = Vector(p), Vector(q); d = q - p; L = d.length; d.normalize()
        return any(ob.ray_cast(p + d * .3, d, distance=max(L - stop, 0))[0] for ob in (harbour_ob, ctx["terrain"], *prop_obs))
    lx, ly, _ = lantern_info["lantern"]
    seen = [n for eye, n in lantern_info["posts"] if not blocked(eye, (lx, ly, 29.3), 4.2)]
    neighbours = all(not blocked(lantern_info["posts"][i][0], lantern_info["posts"][i + 1][0], .5) for i in range(6))
    temples = {"headland city": city_temple, "citadel quorum hall": citadel_detail["hall"]}
    wt_detail = bs.WATCHTOWER_DETAIL
    hs = HOUSE_STATS
    dres = {"lantern_quays": lantern_info["quays"], "lantern_seen_from_posts": seen, "captains_see_neighbours": neighbours,
            "banquet": banquet_info, "houses": dict(hs), "house_door_h_m": DOOR_H, "house_window_sill_m": WINDOW_SILL,
            "temples": {k_: {kk: v for kk, v in t_.items() if kk not in ("front", "floor_z")} for k_, t_ in temples.items()},
            "citadel": {k_: v for k_, v in citadel_detail.items() if k_ != "hall"}, "watchtowers": wt_detail}
    dres["checks"] = {
        "seven_quays_each_see_the_lantern": lantern_info["quays"] == 7 and len(seen) == 7,
        "each_captains_post_sees_its_neighbour": neighbours,
        "banquet_andron_seats_eleven": banquet_info["couches"] == 11,
        "house_doors_and_windows_at_human_scale": DOOR_H >= 1.2 * ba.FIGURE and WINDOW_SILL >= 1.8 and hs["with_door"] >= .8 * hs["houses"],
        "temple_columns_doric_proportions": all(4.5 <= t_["column_h_over_d"] <= 6.5 and 2.0 <= t_["axial_over_d"] <= 2.8 for t_ in temples.values()),
        "temple_steps_and_doors_at_human_scale": all(t_["step_riser_m"] <= .4 and t_["door_h_m"] >= 2.2 for t_ in temples.values()),
        "citadel_merlons_cover_a_standing_soldier": citadel_detail["merlon_h_m"] >= 1.8 and .6 <= citadel_detail["crenel_w_m"] <= 1.0 and citadel_detail["wall_walk_w_m"] >= 2,
        "citadel_gate_takes_a_cart": citadel_detail["gate_w_m"] >= 3 and citadel_detail["gate_h_m"] >= 4,
        "watchtower_parapets_cover_standing_guard": wt_detail["towers"] == 4 and wt_detail["merlon_h_m"] >= 1.8 and wt_detail["door_h_m"] >= 2.0}
    dres["ok"] = all(dres["checks"].values())
    (bt.OUT / "detail-checks.json").write_text(json.dumps(dres, indent=1, default=list))
    print("DETAIL CHECKS", json.dumps(dres["checks"]), "ok", dres["ok"])
    ck_ = dres["checks"]
    bt.page_block("DETAIL",
                  [("Houses with doors and windows", f"{hs['with_door']:,} of {hs['houses']:,} ({hs['windows']:,} windows)"),
                   ("House doors · window sills", f"{DOOR_H} m · {WINDOW_SILL} m up"),
                   ("Temples (column height ÷ diameter)", ", ".join(f"{k_} {t_['column_h_over_d']}" for k_, t_ in temples.items())),
                   ("Banquet house couches", str(banquet_info["couches"])), ("Lighthouse", f"{lantern_info['tower_top_m']} m, seen from {len(seen)} of 7 captains' posts"),
                   ("Citadel merlons · crenels · wall-walk", f"{citadel_detail['merlon_h_m']} m · {citadel_detail['crenel_w_m']} m · {citadel_detail['wall_walk_w_m']} m"),
                   ("Citadel gate", f"{citadel_detail['gate_w_m']} × {citadel_detail['gate_h_m']} m")],
                  [("All seven quays see the lantern (rays through the harbour and terrain)", ck_["seven_quays_each_see_the_lantern"]),
                   ("Each captain's post sees its neighbour", ck_["each_captains_post_sees_its_neighbour"]),
                   ("The banquet house's dining room seats eleven couches", ck_["banquet_andron_seats_eleven"]),
                   ("House doors and high windows at human scale", ck_["house_doors_and_windows_at_human_scale"]),
                   ("Temple columns in Doric proportion", ck_["temple_columns_doric_proportions"]),
                   ("Temple steps and doors at human scale", ck_["temple_steps_and_doors_at_human_scale"]),
                   ("Citadel merlons cover a standing soldier; wall-walk ≥ 2 m", ck_["citadel_merlons_cover_a_standing_soldier"]),
                   ("Citadel gate takes a cart (≥ 3 × 4 m)", ck_["citadel_gate_takes_a_cart"]),
                   ("Watchtower parapets cover standing guard (merlons ≥ 1.8 m, door ≥ 2.0 m)", ck_["watchtower_parapets_cover_standing_guard"])])

    # the large props (tools/blender_props.py): their own checks, plus the outbound merchantman seen from the Round
    out_ob = next(o for o in prop_obs if o.name == "V · The outbound merchantman")
    oeye, owin = br.window_eye(round_info, pviews["outbound"])
    oblock = br.sight(oeye, pviews["outbound"], [("the Round", round_ob, .5), ("terrain", ctx["terrain"], 3.0), ("town", objs[4], .5),
                                                 *[(o.name, o, .5) for o in prop_obs if o is not out_ob]])
    pres["outbound"]["seen_from_verandah_window"], pres["outbound"]["blocked_by"] = not oblock, oblock
    pres["checks"]["outbound_merchantman_seen_from_a_verandah_window"] = not oblock
    pres["checks"]["props_block_no_story_sightline"] = (ck_["seven_quays_each_see_the_lantern"] and ck_["each_captains_post_sees_its_neighbour"]
                                                         and rres["banquet_house_seen_from_verandah_window"] and rres["quays_seen_from_verandah_window"]
                                                         and sres["beacon_fires_in_sight"] and sres["drum_decks_in_sight"])
    pres["objects"], pres["faces"] = len(prop_obs), sum(len(o.data.polygons) for o in prop_obs)
    pres["ok"] = all(pres["checks"].values())
    (bt.OUT / "props-checks.json").write_text(json.dumps(pres, indent=1, default=lambda o: o.item() if hasattr(o, "item") else list(o)))
    print("PROPS CHECKS", json.dumps({k_: bool(v) for k_, v in pres["checks"].items()}), "ok", pres["ok"])
    pk = pres["checks"]; placed_carts = [c_ for c_ in pres["carts"] if c_["placed"]]
    bt.page_block("PROPS",
                  [("Models", f"{pres['objects']} objects, {pres['faces']:,} faces"),
                   ("Ships", f"{pres['ships']} ({pres['navigators_ships']} navigators' ships, {pres['moored'] - pres['navigators_ships']} others moored, 2 under sail or at anchor)"),
                   ("Least water under a keel", f"{min(pres['keel_clearance_m'].values())} m"),
                   ("Gap to the quay, alongside (measured to the quay mesh)", f"{min(pres['alongside_gap_m'].values())}–{max(pres['alongside_gap_m'].values())} m"
                    if min(pres['alongside_gap_m'].values()) != max(pres['alongside_gap_m'].values()) else f"{min(pres['alongside_gap_m'].values())} m"),
                   ("Steepest gangplank", f"{max(pres['gangplank_deg'].values())}°"),
                   ("Deck above the water", ", ".join(f"{k_} {v} m" for k_, v in pres["scale"]["deck_freeboard_m"].items())),
                   ("Amphorae", str(pres["amphorae"])), ("Ox carts", f"{len(placed_carts)}, steepest grade {max(c_['grade_pct'] for c_ in placed_carts)}%"),
                   ("Agora", f"{pres['agora']['stalls']} cheese stalls; goat pen {pres['agora']['goat_pen_to_fountain_m']} m from the fountain"),
                   ("The Raft", f"deck {pres['raft']['deck_z_m']} m above the water, {pres['raft']['jetty_gap_m']} m off the jetty")],
                  [("Every ship floats (the seabed lies below its keel)", pk["every_ship_floats"]),
                   ("Moored ships lie alongside their quays (0.3–2 m)", pk["moored_ships_lie_alongside_their_quays"]),
                   ("No ship cuts into a quay or another ship", pk["no_ship_cuts_a_quay_or_another_ship"]),
                   ("Gangplanks walkable (30° or less)", pk["gangplanks_walkable_30deg"]),
                   ("A navigators' ship at each of the seven quays", pk["a_navigators_ship_at_each_of_the_seven_quays"]),
                   ("The outbound merchantman is in open water, heading out", pk["outbound_merchantman_in_open_water_heading_out"]),
                   ("…and seen from a verandah window of the Round", pk["outbound_merchantman_seen_from_a_verandah_window"]),
                   ("The Raft floats alongside the monastery jetty", pk["raft_floats_alongside_the_jetty"]),
                   ("Cheese stalls and goat pen on the paving, by the fountain, clear of it (canon)", pk["cheese_stalls_and_goat_pen_on_the_agora"]),
                   ("Ox carts on the tracks, on grades of 10% or less, clear of buildings", pk["carts_on_tracks_at_grades_oxen_can_hold"]),
                   ("Props at human scale (decks, cart beds and wheels, stall counters and awnings)", pk["props_at_human_scale"]),
                   ("No prop blocks a story sightline (lantern, Round windows, beacons, drums)", pk["props_block_no_story_sightline"])])

    # vegetation, fields and tracks (tools/blender_nature.py)
    PX_, PY_ = site("port"); BX_, BY_ = site("banquet")
    sightlines = [((RX, RY, rim + 8), (PX_, PY_, ground.z(PX_, PY_) + 2)), ((RX, RY, rim + 8), (BX_, BY_, ground.z(BX_, BY_) + 4)),
                  tuple(fires), tuple(decks)]
    exclusions = [(*B(x, y), r) for key, r in bn.EXCLUDE_M.items() for x, y, _ in SITES["sites"][key]["points_m"]]
    vres = bn.build(ctx, ground, bs.smooth_path, sightlines, exclusions, pviews["spots"])
    (bt.OUT / "vegetation-checks.json").write_text(json.dumps(vres, indent=1))
    print("VEGETATION CHECKS", json.dumps(vres))
    ic = vres["instances"]
    bt.page_block("VEGETATION",
                  [("Olive trees", f"{ic['olive groves']:,}"), ("Maquis shrubs", f"{ic['maquis']:,}"), ("Umbrella pines", f"{ic['umbrella pines']:,}"),
                   ("Cypresses (placed by hand)", str(vres["cypresses"])), ("Wheat and fallow parcels", f"{vres['wheat_and_fallow_km2']} km²"),
                   ("Track ribbons", f"{vres['track_ribbons_m']:,} m")],
                  [("No trees standing in water", vres["trees_standing_in_water"] == 0),
                   ("No plants growing through the props (carts, crane, amphora stacks)", vres["plants_on_props"] == 0),
                   ("No tall trees on building footprints", vres["tall_trees_on_building_footprints"] == 0),
                   ("No tall trees on the story's sightlines (Round to quays and banquet house, beacons, drums)", vres["tall_trees_on_story_sightlines"] == 0)])

    look = ctx["look"]
    def cam_at(name, target, frm, height, lens=35):
        return bt.camera(name, (target[0] + frm[0], target[1] + frm[1], target[2] + height), target, look, lens=lens)
    CX, CY = B(*SITES["built"]["cothon"]["centre_m"]); th_c = math.radians(-SITES["built"]["cothon"]["channel_bearing_deg_from_x_toward_y"])
    PX, PY = site("port"); s_port = ground.seaward(PX, PY)
    CitX, CitY = site("citadel"); cityX, cityY = site("city")
    cams = {"round": cam_at("Cam · the Great Round", (RX, RY, rim - 4), (-95, -95), 70),
            "cothon": cam_at("Cam · the lantern harbour", (CX, CY, 0), (math.cos(th_c) * 520, math.sin(th_c) * 520), 330),
            "port": cam_at("Cam · merchant quays and town", (PX - s_port[0] * 180, PY - s_port[1] * 180, 20), (s_port[0] * 800, s_port[1] * 800), 360),
            "city": cam_at("Cam · the headland city", (cityX, cityY, ground.z(cityX, cityY)), (-420, -420), 330),
            "citadel": cam_at("Cam · citadel and walled harbour", ((CitX + HSX) / 2, (CitY + HSY) / 2, 40), (650, -250), 380),
            "parliament": cam_at("Cam · the Parliament's lobe", (RX + 300, RY + 100, 120), (-1400, -1500), 900, lens=40)}
    hAX, hAY = site("hamA"); WT2X, WT2Y = site("watchtowers", 2); stX, stY = site("strait"); HLX, HLY = site("hall"); MOX, MOY = site("monastery")
    gpts = [site("granary", i) for i in range(3)] + [site("granary2")]
    gcx, gcy = sum(p[0] for p in gpts) / 4, sum(p[1] for p in gpts) / 4
    cliffX, cliffY = site("cliffs"); s_cl = ground.seaward(cliffX, cliffY)
    walk_pts = [B(x, y) for x, y in SITES["built"]["statue_walk_m"]]; wmx, wmy = walk_pts[len(walk_pts) // 2]
    to_round = (RX - agora[0], RY - agora[1]); tr = math.hypot(*to_round)
    zo = round_info["z_orch"]
    (p0x, p0y, p0z), _ = lantern_info["posts"][0]
    bdir = ((RX - BX) / math.hypot(RX - BX, RY - BY), (RY - BY) / math.hypot(RX - BX, RY - BY)); bz = ground.z(BX, BY)
    WTd2X, WTd2Y = site("watchtowers", 2); wtz2 = ground.z(WTd2X, WTd2Y)
    CiX, CiY = site("citadel"); SwX, SwY = site("seawall"); cang = math.atan2(SwY - CiY, SwX - CiX)
    cP = lambda u, v: (CiX + u * math.cos(cang) - v * math.sin(cang), CiY + u * math.sin(cang) + v * math.cos(cang)); gzc = ground.z(*cP(65, 0))
    aX, aY = agora; adeg = math.radians(-SITES["built"]["town"]["agora_m_deg"][2])
    tP = lambda u, v: (aX + u * math.cos(adeg) - v * math.sin(adeg), aY + u * math.sin(adeg) + v * math.cos(adeg))
    ctf = city_temple["front"]
    cams.update({
        "detail_lighthouse": bt.camera("Cam · the lighthouse from a captain's post", (p0x, p0y, p0z + 1), (lx, ly, 20), look, lens=35),
        "detail_banquet": bt.camera("Cam · the banquet house from the Round's side", (BX + bdir[0] * 34 - bdir[1] * 14, BY + bdir[1] * 34 + bdir[0] * 14, bz + 7), (BX, BY, bz + 3), look, lens=32),
        "detail_watchtower": bt.camera("Cam · South Crag watchtower", (WTd2X + 26, WTd2Y - 18, wtz2 + 16), (WTd2X, WTd2Y, wtz2 + 9), look, lens=35),
        "detail_citadel": bt.camera("Cam · the citadel gate", (*cP(112, 22), gzc + 6), (*cP(65, 0), gzc + 8), look, lens=35),
        "detail_town": bt.camera("Cam · the agora and its stoa", (*tP(-55, -45), ground.z(aX, aY) + 16), (*tP(0, 12), ground.z(aX, aY) + 3), look, lens=30),
        "detail_city": bt.camera("Cam · the headland city's temple", (ctf[0] + 45, ctf[1] - 38, ground.z(*ctf) + 26), (ctf[0] - 8, ctf[1], ground.z(*ctf) + 6), look, lens=35),
        "round_gate": bt.camera("Cam · the Round's east gate", (RX + 50, RY - 12, rim + 3.2), (RX + 24.2, RY, rim + 4.2), look, lens=32),
        "round_interior": bt.camera("Cam · across the Round from the west verandah", (RX - 22.0, RY + 1.5, round_info["z_verandah"] + 1.6), (RX + 12, RY, round_info["z_orch"] + 2.5), look, lens=20),
        "round_window": bt.camera("Cam · out of an east verandah window", br.window_eye(round_info, (BX, BY))[0], (BX, BY, ground.z(BX, BY) + 3), look, lens=35),
        "round_aerial": bt.camera("Cam · the Round from above", (RX - 58, RY - 46, rim + 48), (RX, RY, zo + 2), look, lens=35),
        "round_statue": bt.camera("Cam · a legislator's statue", (RX + 36 * math.cos(.12), RY + 36 * math.sin(.12), rim + 2.6),
                                  (RX + 29.5 * math.cos(TAU / 24), RY + 29.5 * math.sin(TAU / 24), rim + 3.0), look, lens=50),
        "hamlet": cam_at("Cam · hamlet A", (hAX, hAY, ground.z(hAX, hAY)), (-150, -150), 95),
        "watchtowers": cam_at("Cam · coastal watchtowers along the bluffs", (WT2X, WT2Y, ground.z(WT2X, WT2Y) - 10), (-260, -260), 190),
        "neck": cam_at("Cam · the neck: causeway and drummers", ((site("drummers", 0)[0] + site("drummers", 1)[0]) / 2, (site("drummers", 0)[1] + site("drummers", 1)[1]) / 2, 5), (-760, -700), 460, lens=28),
        "granaries": cam_at("Cam · the granary plain", (gcx, gcy, 40), (-900, -420), 620, lens=32),
        "guild": cam_at("Cam · the guild quarter and quarry", ((HLX + cliffX) / 2, (HLY + cliffY) / 2, 60), (s_cl[0] * 650 - 250, s_cl[1] * 650 - 150), 420, lens=28),
        "monastery": cam_at("Cam · the Raft monastery", (MOX, MOY, ground.z(MOX, MOY)), ((RX - MOX) / math.hypot(RX - MOX, RY - MOY) * 210 + 60, (RY - MOY) / math.hypot(RX - MOX, RY - MOY) * 210 - 60), 110),
        "walk": bt.camera("Cam · up the Statue Walk", (agora[0] - to_round[0] / tr * 150, agora[1] - to_round[1] / tr * 150, ground.z(*agora) + 160), (wmx, wmy, ground.z(wmx, wmy)), look, lens=35)})
    oX, oY, oZ = pviews["outbound"]; qx_, qy_ = pviews["crane"]; mkx, mky = pviews["market"]; ra = pviews["agora_ang"]
    gX, gY, gA = pviews["galley"]; bX, bY, bA = pviews["barge_xy"]; rfx, rfy = pviews["raft"]; rf = pviews["raft_face"]
    nX, nY = pviews["cothon_ship"]
    AP = pviews["agora_P"]; gsea = pviews["galley_sea"]; rpp = pviews["raft_perp"]; pc = pviews["cothon"]
    qa = (pc[3][2] + pc[3][3]) / 2
    cams.update({
        "props_cothon": bt.camera("Cam · navigators' ships at their quays", (pc[0] + (pc[2] + 25) * math.cos(qa), pc[1] + (pc[2] + 25) * math.sin(qa), 26), (pc[0], pc[1], 8), look, lens=30),
        "props_port": bt.camera("Cam · ships at the merchant quays", (qx_ + s_port[0] * 70 - s_port[1] * 60, qy_ + s_port[1] * 70 + s_port[0] * 60, 22), (qx_ - s_port[0] * 10, qy_ - s_port[1] * 10, 3), look, lens=30),
        "props_outbound": bt.camera("Cam · the outbound merchantman", (oX + 40, oY - 35, 9), (oX, oY, 5), look, lens=35),
        "props_market": bt.camera("Cam · cheese stalls and the goat pen", (*AP(-6, -30), ground.z(mkx, mky) + 14), (*AP(-5, 3), ground.z(mkx, mky) + 1), look, lens=30),
        "props_galley": bt.camera("Cam · the inquisitors' galley at the citadel quay", (gX + gsea[0] * 34 + math.cos(gA) * 22, gY + gsea[1] * 34 + math.sin(gA) * 22, 10), (gX, gY, 2.5), look, lens=35),
        "props_barge": bt.camera("Cam · the stone barge at the quarry quay", (bX + 30 * math.cos(bA - .8), bY + 30 * math.sin(bA - .8), 11), (bX, bY, 2), look, lens=35),
        "props_raft": bt.camera("Cam · the Raft at the monastery jetty", (rfx + rpp[0] * 16 - math.cos(rf) * 9, rfy + rpp[1] * 16 - math.sin(rf) * 9, 5), (rfx, rfy, 1.2), look, lens=35)})
    cxyz = pviews["cart"]
    if cxyz: cams["props_cart"] = bt.camera("Cam · an ox cart on the granary track", (cxyz[0] + 16 * math.cos(cxyz[3] - 1.2) + 3 * math.cos(cxyz[3]), cxyz[1] + 16 * math.sin(cxyz[3] - 1.2) + 3 * math.sin(cxyz[3]), cxyz[2] + 6),
                                    (cxyz[0] + 3 * math.cos(cxyz[3]), cxyz[1] + 3 * math.sin(cxyz[3]), cxyz[2] + 1), look, lens=35)
    scene.camera = ctx["cams"]["overview"]
    bpy.ops.wm.save_as_mainfile(filepath=str(bt.OUT / "paxos.blend"), compress=True)
    if "--render" in args:
        bt.RENDERS.mkdir(exist_ok=True); bt.use_eevee(scene)
        for key, cam in cams.items():
            bt.render(scene, cam, bt.RENDERS / f"buildings-{key}.png", (1600, 900))
        hAX_, hAY_ = site("hamA")
        close = cam_at("Cam · olive groves above hamlet A", (hAX_, hAY_, ground.z(hAX_, hAY_)), (-230, -150), 55, lens=30)
        for key, cam in (("overview", ctx["cams"]["overview"]), ("parliament", cams["parliament"]), ("plain", cams["granaries"]), ("groves", close)):
            bt.render(scene, cam, bt.RENDERS / f"nature-{key}.png", (1600, 900))
        top_cam = ctx["cams"]["top"]
        top_cam.data.ortho_scale = 11000
        bt.render(scene, top_cam, bt.RENDERS / "island-ortho.png", (2200, 1600))
        scene.camera = ctx["cams"]["overview"]
        bpy.ops.wm.save_as_mainfile(filepath=str(bt.OUT / "paxos.blend"), compress=True)

if __name__ == "__main__":
    main()
