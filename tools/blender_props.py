"""The large props, crude on purpose: ships and skiffs in the three harbours and at the quarry's loading quay, the
Raft at the monastery jetty, amphorae and a treadwheel crane on the merchant quays, the agora's cheese stalls and
goat pen (canon), and ox carts on the tracks by the olive press, the granaries and the quarry.

The small props (the hourglass, the ledger scroll on two rods, ink, the statues' detail) come later, from Tripo.

Every ship is its own object so the checks can test it: it floats (the seabed under its hull lies below its keel), a
moored ship lies alongside its quay without cutting into it, its gangplank is walkable, and it blocks none of the
story's sightlines (the main build casts those rays through the props too). Nothing here edits the ground.
"""
import math, random
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from blender_kit import *                                                                          # noqa: F401,F403
import blender_arch as ba
import blender_round as br

def extra_mats():
    return {"pitch": mat("Ship hull (pitch)", "#2f2621"), "hull": mat("Ship timber", "#7a5634"), "sail": mat("Sail", "#e9dfc6"),
            "clay": mat("Amphora clay", "#b9683f"), "cheese": mat("Cheese", "#e6cf8c"), "goat": mat("Goat", "#d9d2c3"),
            "ox": mat("Ox", "#8a6a4a"), "sack": mat("Grain sack", "#c9b58a"), "rope": mat("Rope", "#9b8558"), "wicker": mat("Wicker", "#a47d4a"),
            "chiton": mat("Chiton linen", "#ddd3bd"), "cloak": mat("Himation blue", "#4f6f8a"), "skin": mat("Skin", "#b98563", .6)}

# ---------------------------------------------------------------- ships
# L length, beam, draught, freeboard (gunwale above water, midships), sheer (rise of the gunwale at the ends), deck drop below the gunwale
SHIPS = {"merchantman": dict(L=18, beam=6.0, draught=1.6, freeboard=1.5, sheer=.9, drop=.35, mast=11.0, yard=12.0),
         "galley":      dict(L=30, beam=4.4, draught=1.1, freeboard=1.6, sheer=.7, drop=.35, mast=9.0, yard=10.0),
         "navigator":   dict(L=22, beam=3.8, draught=1.0, freeboard=1.5, sheer=.7, drop=.35, mast=8.0, yard=8.0),
         "barge":       dict(L=16, beam=6.0, draught=1.3, freeboard=1.2, sheer=.2, drop=.35, mast=0, yard=0),
         "skiff":       dict(L=6, beam=1.8, draught=.35, freeboard=.55, sheer=.25, drop=.25, mast=0, yard=0)}
KEEL_MARGIN = {"skiff": .3}                                                                        # water under the keel, metres; .5 otherwise

def shape(T):
    W, D, F, S = T["beam"] / 2, T["draught"], T["freeboard"], T["sheer"]
    half = lambda t: W * max(.03, 1 - abs(t) ** 2.4) ** .55
    keel = lambda t: -D * max(0.0, 1 - abs(t) ** 3) ** .5
    top = lambda t: F + S * t * t
    return half, keel, top

def keel_samples(X, Y, ang, T):
    """(x, y, underside z) across the hull's footprint."""
    half, keel, top = shape(T); c, s = math.cos(ang), math.sin(ang); out = []
    for t in np.linspace(-.85, .85, 9):
        w, zk, zt = half(t), keel(t), top(t)
        for f in (-.7, 0, .7):
            ph = math.asin(f); u, v = t * T["L"] / 2, w * f
            out.append((X + u * c - v * s, Y + u * s + v * c, zt - (zt - zk) * abs(math.cos(ph)) ** .8))
    return out

def keel_clearance(ground, X, Y, ang, T):
    return min(z - ground.z(x, y) for x, y, z in keel_samples(X, Y, ang, T))

def ship(name, M, kind, X, Y, ang, sail="furled", oars=False, crew=0):
    """One ship as its own Kit: a lofted hull (pitch below the waterline), deck, posts, mast and sail, oars."""
    T = SHIPS[kind]; k = Kit(name); half, keel, top = shape(T)
    L, n_st, n_sec = T["L"], 15, 9
    c, s = math.cos(ang), math.sin(ang); P = lambda u, v, z: (X + u * c - v * s, Y + u * s + v * c, z)
    rings = []
    for i in range(n_st):
        t = -1 + 2 * i / (n_st - 1); w, zk, zt = half(t), keel(t), top(t)
        rings.append([k.bm.verts.new(P(t * L / 2, w * math.sin(ph), zt - (zt - zk) * abs(math.cos(ph)) ** .8))
                      for ph in np.linspace(-math.pi / 2, math.pi / 2, n_sec)])
    for i in range(n_st - 1):
        for j in range(n_sec - 1):
            q = [rings[i][j], rings[i + 1][j], rings[i + 1][j + 1], rings[i][j + 1]]
            k._face(q, M["pitch"] if sum(v.co.z for v in q) / 4 < .3 else M["hull"])
    k._face(rings[0], M["hull"]); k._face(rings[-1][::-1], M["hull"])
    zd = T["freeboard"] - T["drop"]
    for i in range(n_st - 1):                                                                       # deck
        t0, t1 = -1 + 2 * i / (n_st - 1), -1 + 2 * (i + 1) / (n_st - 1)
        vs = [k.bm.verts.new(P(t0 * L / 2, -half(t0) * .96, zd)), k.bm.verts.new(P(t1 * L / 2, -half(t1) * .96, zd)),
              k.bm.verts.new(P(t1 * L / 2, half(t1) * .96, zd)), k.bm.verts.new(P(t0 * L / 2, half(t0) * .96, zd))]
        k._face(vs, M["timber"])
    tb, tf = top(-1), top(1)
    if kind == "merchantman":
        k.beam(P(-L / 2 + .3, 0, tb - .3), P(-L / 2 - .8, 0, tb + 1.8), .35, .35, M["hull"])      # goose-neck stern post
        k.beam(P(-L / 2 - .8, 0, tb + 1.8), P(-L / 2 - .2, 0, tb + 2.8), .3, .3, M["hull"])
        k.beam(P(L / 2 - .3, 0, keel(.9)), P(L / 2 + .5, 0, tf + .5), .35, .35, M["hull"])          # stem
        k.box(*P(-L * .32, 0, 0)[:2], zd, zd + 1.8, 3.2, T["beam"] * .55, ang, M["plaster"])       # deckhouse
        k.box(*P(-L * .32, 0, 0)[:2], zd + 1.8, zd + 2.0, 3.6, T["beam"] * .62, ang, M["roof"])
    if kind in ("galley", "navigator"):
        k.beam(P(L / 2 - 1.2, 0, -.3), P(L / 2 + 2.2, 0, -.45), .5, .6, M["bronze"])               # the ram
        k.beam(P(L / 2 - .2, 0, tf - .4), P(L / 2 + .7, 0, tf + 1.0), .3, .3, M["hull"])            # stem post
        prev = P(-L / 2 + .3, 0, tb - .3)
        for du, dz in ((-1.1, 2.0), (-.7, 3.4), (.2, 4.0)):                                          # the stern's upswept curl
            nxt = P(-L / 2 + du, 0, tb + dz); k.beam(prev, nxt, .3, .3, M["hull"]); prev = nxt
        for sd in (-1, 1):
            k.beam(P(-L * .3, sd * (half(0) + .25), T["freeboard"] - .1), P(L * .32, sd * (half(0) + .25), T["freeboard"] - .1), .5, .3, M["hull"])   # outrigger
            k.box(*P(L / 2 - 1.8, sd * (half(.88) + .03), 0)[:2], .35, .75, .1, .4, ang, M["marble"])                                          # eye
        if oars:
            n = int(L * .55 / 1.0)
            for sd in (-1, 1):
                for i in range(n):
                    u = -L * .28 + i * 1.0
                    k.beam(P(u, sd * (half(0) + .3), T["freeboard"] - .1), P(u - 1.2, sd * (half(0) + 5.5), -.1), .09, .09, M["timber"])
    if kind in ("merchantman", "galley"):
        for sd in (-1, 1):                                                                           # steering oars
            k.beam(P(-L * .38, sd * (half(-.76) + .2), T["freeboard"] + .6), P(-L * .47, sd * (half(-.76) + .9), -1.0), .18, .18, M["timber"])
    if kind == "skiff":
        for u in (-1, .6): k.box(*P(u, 0, 0)[:2], zd - .05, zd + .05, .25, T["beam"] * .8, ang, M["timber"])   # thwarts
        for sd in (-1, 1): k.beam(P(-2, sd * .35, zd + .12), P(2.2, sd * .45, zd + .12), .07, .07, M["timber"])  # oars laid in
    if kind == "barge":
        rnd = random.Random(int(abs(X * 7 + Y)))
        for u in (-4.5, -1.5, 1.5, 4.5):
            for v in (-1.3, 1.3): k.box(*P(u, v, 0)[:2], zd, zd + rnd.choice((.9, 1.0, 1.1)), 2.2, 1.1, ang + rnd.uniform(-.05, .05), M["limestone"])
    if T["mast"]:
        um = L * .1 if kind == "merchantman" else 0.0; mx, my, _ = P(um, 0, 0); zt_ = zd + T["mast"]
        k.cyl(mx, my, .2, zd, zt_, M["timber"], 8)
        k.beam(P(um, -T["yard"] / 2, zt_ - .6), P(um, T["yard"] / 2, zt_ - .6), .18, .18, M["timber"])
        if sail == "set":
            k.box(*P(um + .35, 0, 0)[:2], zd + 2.4, zt_ - .7, .12, T["yard"] * .94, ang, M["sail"])
        elif sail == "furled":
            k.beam(P(um + .05, -T["yard"] * .46, zt_ - .95), P(um + .05, T["yard"] * .46, zt_ - .95), .45, .45, M["sail"])
        for sd in (-1, 1): k.beam(P(um, 0, zt_), P(L * .45 * sd, 0, T["freeboard"] + .3), .05, .05, M["rope"])     # stays
    rnd = random.Random(int(abs(X * 13 + Y * 3)))
    for i in range(crew):
        u = rnd.uniform(-L * .3, L * .3); v = rnd.uniform(-half(0) * .5, half(0) * .5)
        br.figure(k, *P(u, v, 0)[:2], zd, ang + rnd.uniform(0, TAU), "stand", M["chiton"], M["cloak"] if i % 2 else M["chiton"], M["skin"])
    return k, {"kind": kind, "X": X, "Y": Y, "ang": ang, "deck_z": zd, "T": T}

def berth(ground, Q, n, t_, face_len, kind, gap=.7, steps=9):
    """Along a quay face (point Q at its middle, outward normal n, tangent t_), the berth with the most water under the keel."""
    T = SHIPS[kind]; span = max(0.0, (face_len - T["L"]) / 2 - 1); ang = math.atan2(t_[1], t_[0]); best = None
    for a in np.linspace(-span, span, steps):
        X = Q[0] + t_[0] * a + n[0] * (gap + T["beam"] / 2); Y = Q[1] + t_[1] * a + n[1] * (gap + T["beam"] / 2)
        clr = keel_clearance(ground, X, Y, ang, T)
        if best is None or clr > best[0]: best = (clr, X, Y, a)
    return best[1], best[2], ang, best[3]

def side_points(info, toward_n):
    """Points on the gunwale on the side facing the quay (for the alongside gap)."""
    T = info["T"]; half, _, top = shape(T); c, s = math.cos(info["ang"]), math.sin(info["ang"])
    sd = 1 if (-s * toward_n[0] + c * toward_n[1]) > 0 else -1
    return [(info["X"] + t * T["L"] / 2 * c - sd * half(t) * s, info["Y"] + t * T["L"] / 2 * s + sd * half(t) * c, top(t)) for t in (-.4, 0, .4)]

# ---------------------------------------------------------------- small pieces
def amphora(k, M, X, Y, z):
    k.cone(X, Y, .07, z + .14, z, M["clay"], 8)
    k.ellipsoid(X, Y, z + .5, .2, .2, .38, M["clay"])
    k.cyl(X, Y, .06, z + .84, z + 1.0, M["clay"], 8)
    return 1.0

def amphora_grid(k, M, X, Y, z, ang, nu, nv, step=.5):
    c, s = math.cos(ang), math.sin(ang); n = 0
    for i in range(nu):
        for j in range(nv):
            u, v = (i - (nu - 1) / 2) * step, (j - (nv - 1) / 2) * step
            amphora(k, M, X + u * c - v * s, Y + u * s + v * c, z); n += 1
    return n

def wheel(k, cx, cy, cz, axle_ang, r, th, m, segs=14):
    """A disc wheel whose axle runs along the horizontal direction axle_ang."""
    ax, ay = math.cos(axle_ang), math.sin(axle_ang); px, py = -ay, ax
    sides = []
    for o in (-th / 2, th / 2):
        sides.append([k.bm.verts.new((cx + ax * o + px * r * math.cos(a), cy + ay * o + py * r * math.cos(a), cz + r * math.sin(a)))
                      for a in np.linspace(0, TAU, segs, endpoint=False)])
    k._face(sides[0][::-1], m); k._face(sides[1], m)
    for i in range(segs): k._face([sides[0][i], sides[0][(i + 1) % segs], sides[1][(i + 1) % segs], sides[1][i]], m)

CART = {"wheel_d_m": 1.4, "bed_top_m": 1.05}

def ox_cart(k, M, ground, X, Y, ang, load):
    c, s = math.cos(ang), math.sin(ang); P = lambda u, v: (X + u * c - v * s, Y + u * s + v * c)
    z0 = ground.z(X, Y); r = CART["wheel_d_m"] / 2; bt_ = z0 + CART["bed_top_m"]
    for sd in (-1, 1):
        wx, wy = P(0, sd * 1.0); wheel(k, wx, wy, ground.z(wx, wy) + r, ang + math.pi / 2, r, .14, M["timber"])
    k.beam((*P(0, -1.1), z0 + r), (*P(0, 1.1), z0 + r), .12, .12, M["timber"])                    # axle
    k.box(X, Y, bt_ - .15, bt_, 2.8, 1.6, ang, M["timber"])                                         # bed
    for sd in (-1, 1): k.box(*P(0, sd * .78), bt_, bt_ + .4, 2.8, .06, ang, M["timber"])
    k.beam((*P(1.3, 0), bt_ - .1), (*P(4.3, 0), ground.z(*P(4.3, 0)) + 1.15), .14, .14, M["timber"])   # pole
    k.box(*P(4.2, 0), ground.z(*P(4.2, 0)) + 1.15, ground.z(*P(4.2, 0)) + 1.3, .15, 2.2, ang, M["timber"])   # yoke
    for sd in (-1, 1):                                                                              # a yoke of oxen
        g = ground.z(*P(5.1, sd * .7))
        k.beam((*P(4.3, sd * .7), g + 1.05), (*P(6.1, sd * .7), g + 1.1), .75, .9, M["ox"])
        k.beam((*P(6.1, sd * .7), g + 1.25), (*P(6.7, sd * .7), g + 1.0), .38, .45, M["ox"])
        for du in (4.5, 5.9):
            for dv in (-.25, .25): k.box(*P(du, sd * .7 + dv), g, g + .65, .16, .16, ang, M["ox"])
    rnd = random.Random(int(abs(X + Y * 5)))
    if load == "sacks":
        for u in (-.8, 0, .8):
            for v in (-.35, .35): k.ellipsoid(*P(u, v), bt_ + .25, .38, .28, .25, M["sack"])
    elif load == "blocks":
        k.box(X, Y, bt_, bt_ + .9, 2.2, 1.1, ang + rnd.uniform(-.05, .05), M["limestone"])
    elif load == "olives":
        for u in (-.8, 0, .8):
            for v in (-.35, .35): k.cyl(*P(u, v), .28, bt_, bt_ + .45, M["wicker"], 10)
    elif load == "amphorae":
        for u in (-.9, -.3, .3, .9):
            for v in (-.35, .35): amphora(k, M, *P(u, v), bt_)

STALL = {"counter_m": .9, "awning_m": 2.3, "size_m": (3.0, 2.0)}

def stall(k, M, X, Y, z, ang):
    """A cheese stall: counter, posts and a canvas awning sloping down toward the customers (local -y)."""
    c, s = math.cos(ang), math.sin(ang); P = lambda u, v: (X + u * c - v * s, Y + u * s + v * c)
    su, sv = STALL["size_m"]
    k.box(*P(0, -.4), z, z + STALL["counter_m"], su - .2, .7, ang, M["timber"])
    for u in (-su / 2 + .1, su / 2 - .1):
        for v in (-sv / 2 + .1, sv / 2 - .1): k.box(*P(u, v), z, z + STALL["awning_m"] + (.35 if v > 0 else 0), .1, .1, ang, M["timber"])
    k.beam((*P(0, sv / 2), z + STALL["awning_m"] + .4), (*P(0, -sv / 2 - .2), z + STALL["awning_m"]), su + .2, .05, M["canvas"])
    for i in range(5): k.cyl(*P(-1.1 + i * .55, -.4), .2, z + STALL["counter_m"], z + STALL["counter_m"] + .14, M["cheese"], 10)

def goat_pen(k, M, X, Y, z, ang, su=5.0, sv=3.5, goats=5):
    c, s = math.cos(ang), math.sin(ang); P = lambda u, v: (X + u * c - v * s, Y + u * s + v * c)
    corners = [(-su / 2, -sv / 2), (su / 2, -sv / 2), (su / 2, sv / 2), (-su / 2, sv / 2)]
    for i in range(4):
        (u0, v0), (u1, v1) = corners[i], corners[(i + 1) % 4]
        k.beam((*P(u0, v0), z + .9), (*P(u1, v1), z + .9), .08, .08, M["wicker"]); k.beam((*P(u0, v0), z + .45), (*P(u1, v1), z + .45), .08, .08, M["wicker"])
        n = max(2, int(math.hypot(u1 - u0, v1 - v0) / 1.2))
        for j in range(n): k.box(*P(u0 + (u1 - u0) * j / n, v0 + (v1 - v0) * j / n), z, z + 1.0, .1, .1, ang, M["timber"])
    rnd = random.Random(3)
    for _ in range(goats):
        gx, gy = P(rnd.uniform(-su / 2 + .8, su / 2 - .8), rnd.uniform(-sv / 2 + .6, sv / 2 - .6)); ga = rnd.uniform(0, TAU); d = (math.cos(ga), math.sin(ga))
        k.beam((gx - d[0] * .45, gy - d[1] * .45, z + .55), (gx + d[0] * .45, gy + d[1] * .45, z + .6), .32, .36, M["goat"])
        k.beam((gx + d[0] * .45, gy + d[1] * .45, z + .7), (gx + d[0] * .72, gy + d[1] * .72, z + .78), .16, .2, M["goat"])
        for a, b in ((-.3, -.1), (-.3, .1), (.3, -.1), (.3, .1)):
            k.box(gx + d[0] * a - d[1] * b, gy + d[1] * a + d[0] * b, z, z + .4, .06, .06, ga, M["goat"])

def treadwheel_crane(k, M, X, Y, z, ang, reach=6.0):
    """Two raking legs, a jib over the water (local +x), a rope and a net of amphorae, and a treadwheel at the foot."""
    c, s = math.cos(ang), math.sin(ang); P = lambda u, v, zz: (X + u * c - v * s, Y + u * s + v * c, zz)
    apex = P(reach * .45, 0, z + 11)
    for sd in (-1, 1): k.beam(P(-1.5, sd * 1.8, z), apex, .35, .35, M["timber"])
    k.beam(P(-2.5, 0, z), apex, .3, .3, M["rope"])                                                   # back stay
    tip = P(reach, 0, z + 12.2); k.beam(P(-.5, 0, z + 9.5), tip, .3, .3, M["timber"])
    k.beam(tip, P(reach, 0, z + 3.5), .05, .05, M["rope"])
    k.box(*P(reach, 0, 0)[:2], z + 2.3, z + 3.5, 1.2, 1.2, ang, M["rope"])
    wx, wy, _ = P(-1.2, 0, 0); r = 2.1
    for sd in (-.6, .6):
        pts = [P(-1.2 + r * math.cos(a), sd, z + r + .1 + r * math.sin(a)) for a in np.linspace(0, TAU, 17)]
        for p0, p1 in zip(pts, pts[1:]): k.beam(p0, p1, .12, .2, M["timber"])
    k.beam(P(-1.2, -.9, z + r + .1), P(-1.2, .9, z + r + .1), .15, .15, M["timber"])

# ---------------------------------------------------------------- placing everything
def rect_clearance(u, v, su, sv, pu, pv):
    """Distance from point (pu, pv) to an axis-aligned rectangle centred (u, v) of size su x sv (0 if inside)."""
    return math.hypot(max(abs(pu - u) - su / 2, 0), max(abs(pv - v) - sv / 2, 0))

def build(ground, M, colls, geo, tracks, buildings):
    """geo: harbour and site geometry from the builders. tracks: smoothed track polylines (Blender XY).
    buildings: finished building and site objects, for the overlap tests. Returns (props objects, checks)."""
    M.update(extra_mats())
    ships, fittings = [], {v: Kit(f"{v} · Harbour fittings (gangplanks, mooring lines, cargo)") for v in ("IV", "V", "VII", "VIII")}
    moored = []                                                                                     # (ship info, quay object, quay face normal, quay top z, volume)
    amph = 0

    def moor(vol, name, kind, Q, n, t_, face_len, top_z, quay_ob, bow_dir=1, crew=2, **kw):
        X, Y, ang, a = berth(ground, Q, n, t_, face_len, kind)
        if bow_dir < 0: ang += math.pi
        k, info = ship(f"{vol} · {name}", M, kind, X, Y, ang, crew=crew, **kw)
        ships.append((vol, k, info)); moored.append((info, quay_ob, n, top_z, vol))
        f = fittings[vol]                                                                            # gangplank from the quay edge to the deck's centreline
        qx, qy = Q[0] + t_[0] * a, Q[1] + t_[1] * a
        p0 = (qx - n[0] * .4, qy - n[1] * .4, top_z + .05); p1 = (X, Y, info["deck_z"] + .05)
        f.beam(p0, p1, .8, .08, M["timber"])
        info["gangplank_deg"] = round(math.degrees(math.atan2(abs(p0[2] - p1[2]), math.hypot(p1[0] - p0[0], p1[1] - p0[1]))), 1)
        for e in (-1, 1):                                                                            # mooring lines to the quay
            ex, ey = X + t_[0] * e * info["T"]["L"] * .42, Y + t_[1] * e * info["T"]["L"] * .42
            f.beam((ex, ey, info["T"]["freeboard"] + .2), (qx + t_[0] * e * (info["T"]["L"] * .5 + 2) - n[0] * .6, qy + t_[1] * e * (info["T"]["L"] * .5 + 2) - n[1] * .6, top_z + .3), .06, .06, M["rope"])
        return info, (qx, qy)

    # IV · the lantern harbour: a navigators' ship at each of the seven quays, bow toward the lantern
    cx, cy, R = geo["cothon"]["X"], geo["cothon"]["Y"], geo["cothon"]["R"]
    for p, th in enumerate(geo["cothon"]["quay_angles"]):
        t_ = (math.cos(th), math.sin(th)); n = (-t_[1], t_[0])
        Q = (cx + (R - 21) * t_[0] + 4 * n[0], cy + (R - 21) * t_[1] + 4 * n[1])
        moor("IV", f"Navigators' ship at quay {p + 1}", "navigator", Q, n, t_, 42, 2.6, geo["cothon"]["ob"], bow_dir=-1, crew=1)

    # V · the merchant quays: three merchantmen and a galley alongside, skiffs at the shore quay, an outbound merchantman
    SX, SY = geo["port"]["shore"]; s = geo["port"]["s"]; tq = (-s[1], s[0]); port_ob = geo["port"]["ob"]
    pier = lambda off: (SX + s[0] * 44.5 + tq[0] * off, SY + s[1] * 44.5 + tq[1] * off)
    for off, side, kind, name in ((-70, -1, "merchantman", "Merchantman loading wine"), (0, -1, "merchantman", "Merchantman under the crane"),
                                  (0, 1, "galley", "The galley"), (70, 1, "merchantman", "Merchantman unloading grain")):
        px, py = pier(off); n = (tq[0] * side, tq[1] * side)
        info, (qx, qy) = moor("V", name, kind, (px + n[0] * 4.5, py + n[1] * 4.5), n, (s[0], s[1]), 75, 1.8, port_ob, crew=3)
        if kind == "merchantman":
            amph += amphora_grid(fittings["V"], M, qx - n[0] * 2.2, qy - n[1] * 2.2, 1.8, math.atan2(s[1], s[0]), 8, 2)
    px, py = pier(0)
    treadwheel_crane(fittings["V"], M, px + s[0] * 12 - tq[0] * 1.2, py + s[1] * 12 - tq[1] * 1.2, 1.8, math.atan2(-tq[1], -tq[0]), 6.5)
    for toff in (-40, 40, 110):                                                                      # amphorae stacked in front of the warehouses
        amph += amphora_grid(fittings["V"], M, SX + tq[0] * toff - s[0] * 1, SY + tq[1] * toff - s[1] * 1, 1.8, math.atan2(tq[1], tq[0]), 10, 4)
    for n_, (toff, flen) in enumerate(((-58, 12), (-45, 12), (-28, 14))):                            # skiffs in the western gap between the piers: east of the centre pier the shore quay stands on dry ground
        moor("V", f"Skiff {n_ + 1}", "skiff", (SX + s[0] * 9 + tq[0] * toff, SY + s[1] * 9 + tq[1] * toff), (s[0], s[1]), tq, flen, 1.8, port_ob, crew=0)
    oang = math.atan2(s[1], s[0]) + .25
    OX, OY = SX + s[0] * 300 + tq[0] * -90, SY + s[1] * 300 + tq[1] * -90
    ok_, oinfo = ship("V · The outbound merchantman", M, "merchantman", OX, OY, oang, sail="set", crew=4)
    ships.append(("V", ok_, oinfo))

    # VII · the citadel harbour: the inquisitors' galley at the quay, a merchantman at anchor inside the breakwater
    HX, HY, hth = geo["seawall"]["shore"][0], geo["seawall"]["shore"][1], geo["seawall"]["th"]
    sw = (math.cos(hth), math.sin(hth)); ts = (-sw[1], sw[0])
    moor("VII", "The inquisitors' galley", "galley", (HX + sw[0] * 11, HY + sw[1] * 11), sw, ts, 60, 2.0, geo["seawall"]["ob"], crew=4)
    AX, AY = HX + sw[0] * 62 + ts[0] * 28, HY + sw[1] * 62 + ts[1] * 28
    ak, ainfo = ship("VII · Merchantman at anchor", M, "merchantman", AX, AY, hth + 1.2, crew=1)
    ships.append(("VII", ak, ainfo))
    fittings["VII"].beam((AX + math.cos(hth + 1.2) * 8.5, AY + math.sin(hth + 1.2) * 8.5, 1.8), (AX + math.cos(hth + 1.2) * 16, AY + math.sin(hth + 1.2) * 16, -.2), .06, .06, M["rope"])

    # VIII · the quarry's loading quay: a stone barge
    GX, GY, gth = geo["guild"]["shore"][0], geo["guild"]["shore"][1], geo["guild"]["th"]
    gs = (math.cos(gth), math.sin(gth)); gt = (-gs[1], gs[0])
    moor("VIII", "Stone barge", "barge", (GX + gs[0] * 16, GY + gs[1] * 16), gs, gt, 30, 1.8, geo["guild"]["ob"], crew=2)

    # IX · the Raft at the monastery jetty (logs, battens, a shelter, a furled sail and a steering sweep)
    MX, MY, mface = geo["monastery"]["shore"][0], geo["monastery"]["shore"][1], geo["monastery"]["face"]
    mc, ms = math.cos(mface), math.sin(mface); RLX, RLY = MX + mc * 36 - ms * 4.7, MY + ms * 36 + mc * 4.7
    raft = Kit("IX · The Raft"); RP = lambda u, v, z: (RLX + u * mc - v * ms, RLY + u * ms + v * mc, z)
    LOG_R, LOG_Z = .25, .05
    for i in range(9):                                                                               # nine logs, ends staggered
        e = (.3 if i % 2 else 0)
        wheel(raft, *RP(0, -2.0 + i * .5, 0)[:2], LOG_Z, mface, LOG_R, 9.0 - e, M["timber"], 8)
    for u in (-3.6, 0, 3.6): raft.beam(RP(u, -2.3, LOG_Z + .32), RP(u, 2.3, LOG_Z + .32), .25, .15, M["hull"])
    for v in (-1.0, 1.0): raft.box(*RP(-2.3, v, 0)[:2], LOG_Z + .4, LOG_Z + 1.0, 2.0, .15, mface, M["hull"])
    raft.gable(*RP(-2.3, 0, 0)[:2], LOG_Z + 1.0, 2.4, 2.5, 1.1, mface, M["thatch"] if "thatch" in M else M["canvas"])    # a reed shelter
    raft.cyl(*RP(1.2, 0, 0)[:2], .12, LOG_Z + .4, LOG_Z + 6.0, M["timber"], 8)
    raft.beam(RP(1.2, -2.2, LOG_Z + 5.5), RP(1.2, 2.2, LOG_Z + 5.5), .1, .1, M["timber"]); raft.beam(RP(1.25, -2.0, LOG_Z + 5.25), RP(1.25, 2.0, LOG_Z + 5.25), .3, .3, M["sail"])
    raft.beam(RP(-4.2, 0, LOG_Z + 1.0), RP(-7.5, .6, -.3), .12, .12, M["timber"])                    # steering sweep
    br.figure(raft, *RP(-3.8, .5, 0)[:2], LOG_Z + .4, mface + math.pi, "stand", M["cloak"], M["cloak"], M["skin"])
    raft_info = {"deck_z_m": round(LOG_Z + LOG_R + .1, 2), "underside_z_m": LOG_Z - LOG_R,
                 "clearance_m": round(min(LOG_Z - LOG_R - ground.z(*RP(u, v, 0)[:2]) for u in (-4.5, 0, 4.5) for v in (-2.2, 0, 2.2)), 2)}

    # V · the agora: cheese stalls in front of the stoa, a goat pen by the fountain, stallholders
    ax, ay, aang, az = geo["agora"]["X"], geo["agora"]["Y"], geo["agora"]["ang"], geo["agora"]["z"]
    ac, as_ = math.cos(aang), math.sin(aang); AP = lambda u, v: (ax + u * ac - v * as_, ay + u * as_ + v * ac)
    market = Kit("V · Agora market: cheese stalls and goat pen")
    stalls = [(-14.0, 10.5), (-8.5, 10.5), (-3.0, 10.5), (6.0, 10.5), (11.5, 10.5)]
    for u, v in stalls:
        stall(market, M, *AP(u, v), az, aang + math.pi)                                              # awnings slope toward the square
        br.figure(market, *AP(u, v + .6), az, aang - math.pi / 2, "stand", M["chiton"], M["cloak"], M["skin"])
    pen = (-7.0, -4.0, 5.0, 3.5)
    goat_pen(market, M, *AP(pen[0], pen[1]), az, aang, pen[2], pen[3])
    br.figure(market, *AP(pen[0] + 3.3, pen[1] - 1.0), az, aang + math.pi, "stand", M["chiton"], M["chiton"], M["skin"])
    footprints = [(u, v, *STALL["size_m"]) for u, v in stalls] + [pen]
    inside = all(abs(u) + su / 2 <= 19.5 and abs(v) + sv / 2 <= 13.0 for u, v, su, sv in footprints)     # on the paving, clear of the colonnade (v 14.5)
    fountain_gap = min(rect_clearance(u, v, su, sv, 0, 0) for u, v, su, sv in footprints) - 2.2
    sundial_gap = min(rect_clearance(u, v, su, sv, 8, 0) for u, v, su, sv in footprints) - .4
    overlap = any(abs(a[0] - b[0]) < (a[2] + b[2]) / 2 and abs(a[1] - b[1]) < (a[3] + b[3]) / 2 for i, a in enumerate(footprints) for b in footprints[i + 1:])
    agora_info = {"stalls": len(stalls), "goat_pen_to_fountain_m": round(math.hypot(pen[0], pen[1]), 1), "clear_of_fountain_m": round(fountain_gap, 1),
                  "clear_of_sundial_m": round(sundial_gap, 1), "all_on_the_paving": inside, "overlapping": overlap}

    # I, V, VI, VIII · ox carts on the tracks near the press, the port, the granaries and the quarry
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get()
    bvh = {}
    def tree(ob):
        if ob.name not in bvh: bvh[ob.name] = BVHTree.FromObject(ob, dg)
        return bvh[ob.name]
    def cart_hits(X, Y, ang, load):
        tmp = Kit("tmp"); ox_cart(tmp, M, ground, X, Y, ang, load); t_ = BVHTree.FromBMesh(tmp.bm); tmp.bm.free()
        return [b.name for b in buildings if t_.overlap(tree(b))]
    carts = {v: Kit(f"{v} · Ox carts") for v in ("I", "V", "VI", "VIII")}
    cart_info = []
    wanted = [("press", "olives", "I"), ("port", "amphorae", "V"), ("granary:0", "sacks", "VI"), ("granary:1", "sacks", "VI"), ("granary:2", "sacks", "VI"),
              ("granary2", "sacks", "VI"), ("cliffs", "blocks", "VIII"), ("hall", "blocks", "VIII")]
    placed = []
    for key, load, vol in wanted:
        sx_, sy_ = site(*key.split(":")) if ":" not in key else site(key.split(":")[0], int(key.split(":")[1]))
        best = None
        for line in tracks:
            pts = np.array(line)
            d0 = np.hypot(pts[:, 0] - sx_, pts[:, 1] - sy_)
            if d0.min() > 30: continue
            order = range(len(pts)) if d0[0] < d0[-1] else range(len(pts) - 1, -1, -1)
            for i in order:
                if not 2 <= i <= len(pts) - 3: continue
                if not 40 <= d0[i] <= 320 or any(math.hypot(pts[i][0] - q[0], pts[i][1] - q[1]) < 40 for q in placed): continue
                dx, dy = pts[i + 2] - pts[i - 2]; L = math.hypot(dx, dy)
                if L < 1: continue
                ux, uy = dx / L, dy / L; X, Y = pts[i]
                grade = abs(ground.z(X + ux * 4, Y + uy * 4) - ground.z(X - ux * 4, Y - uy * 4)) / 8
                cross = abs(ground.z(X - uy * 1.2, Y + ux * 1.2) - ground.z(X + uy * 1.2, Y - ux * 1.2)) / 2.4
                if ground.z(X, Y) < 1.5: continue
                if max(grade, cross) <= .10 and not cart_hits(X, Y, math.atan2(uy, ux), load):
                    best = (X, Y, math.atan2(uy, ux), grade, cross); break
            if best: break
        if not best: cart_info.append({"near": key, "placed": False}); continue
        X, Y, ang, grade, cross = best; placed.append((X, Y))
        ox_cart(carts[vol], M, ground, X, Y, ang, load)
        seg_d = min(float(np.min(np.hypot(np.array(l)[:, 0] - X, np.array(l)[:, 1] - Y))) for l in tracks)
        cart_info.append({"near": key, "placed": True, "grade_pct": round(100 * grade, 1), "cross_slope_pct": round(100 * cross, 1), "off_track_m": round(seg_d, 1),
                          "_xyz": (X, Y, ground.z(X, Y), ang)})

    # finish objects
    objs = []
    for vol, k, info in ships:
        ob = k.finish(colls[vol]); info["ob"] = ob; objs.append(ob)
    for vol, f in fittings.items(): objs.append(f.finish(colls[vol]))
    raft_ob = raft.finish(colls["IX"]); objs.append(raft_ob)
    market_ob = market.finish(colls["V"]); objs.append(market_ob)
    cart_obs = [c_.finish(colls[v]) for v, c_ in carts.items()]; objs += cart_obs
    bpy.context.view_layer.update(); dg = bpy.context.evaluated_depsgraph_get(); bvh.clear()

    # checks
    floats = []
    for vol, k, info in ships:
        clr = keel_clearance(ground, info["X"], info["Y"], info["ang"], info["T"])
        floats.append((info["ob"].name, round(clr, 2), clr >= KEEL_MARGIN.get(info["kind"], .5)))
    raft_floats = raft_info["clearance_m"] >= .3 and .2 <= raft_info["deck_z_m"] <= .8
    alongside, cuts = [], []
    for info, quay_ob, n, top_z, vol in moored:
        gaps = []
        for x, y, z in side_points(info, (-n[0], -n[1])):
            loc, _, _, dist = tree(quay_ob).find_nearest(Vector((x, y, min(z, top_z - .3))))
            gaps.append(dist if loc is not None else 99)
        alongside.append((info["ob"].name, round(min(gaps), 2), .3 <= min(gaps) <= 2.0))
        if tree(info["ob"]).overlap(tree(quay_ob)): cuts.append(f"{info['ob'].name} / {quay_ob.name}")
    for i, (_, _, a) in enumerate(ships):
        for _, _, b in ships[i + 1:]:
            if math.hypot(a["X"] - b["X"], a["Y"] - b["Y"]) < (a["T"]["L"] + b["T"]["L"]) / 2 + 8 and tree(a["ob"]).overlap(tree(b["ob"])):
                cuts.append(f"{a['ob'].name} / {b['ob'].name}")
    jetty_gap = min(tree(geo["monastery"]["ob"]).find_nearest(Vector(RP(u, -2.25, LOG_Z)))[3] for u in (-3, 0, 3))
    raft_alongside = .2 <= jetty_gap <= 1.5 and not tree(raft_ob).overlap(tree(geo["monastery"]["ob"]))
    planks = [(info["ob"].name, info["gangplank_deg"]) for info, *_ in moored if info["kind"] != "skiff"]
    navigators = sum(1 for info, *_ in moored if info["kind"] == "navigator")
    # the outbound merchantman: open water ahead (a ray at keel depth along its heading meets no seabed for 1 km) and clear of the piers
    fwd = Vector((math.cos(oang), math.sin(oang), 0))
    ahead_hit = geo["terrain"].ray_cast(Vector((OX, OY, -oinfo["T"]["draught"] - .5)), fwd, distance=1000)[0]
    tips = [pier(off) for off in (-70, 0, 70)]; tips = [(x + s[0] * 37.5, y + s[1] * 37.5) for x, y in tips]
    beyond = min(math.hypot(OX - x, OY - y) for x, y in tips)
    heading_off = math.degrees(abs((oang - math.atan2(s[1], s[0]) + math.pi) % TAU - math.pi))
    cart_cuts = []
    for ob in cart_obs:
        if not len(ob.data.polygons): continue
        for b in buildings:
            if tree(ob).overlap(tree(b)): cart_cuts.append(f"{ob.name} / {b.name}")
    carts_ok = all(c_["placed"] and c_["grade_pct"] <= 10 and c_["cross_slope_pct"] <= 10 and c_["off_track_m"] <= 3 for c_ in cart_info) and not cart_cuts
    res = {"ships": len(ships), "moored": len(moored), "navigators_ships": navigators, "amphorae": amph,
           "keel_clearance_m": {n_: c_ for n_, c_, _ in floats}, "alongside_gap_m": {n_: g for n_, g, _ in alongside},
           "gangplank_deg": dict(planks), "cuts": cuts, "raft": {**raft_info, "jetty_gap_m": round(jetty_gap, 2)},
           "outbound": {"open_water_ahead_1km": not ahead_hit, "beyond_pier_tips_m": round(beyond), "heading_off_seaward_deg": round(heading_off, 1),
                        "keel_clearance_m": round(keel_clearance(ground, OX, OY, oang, oinfo["T"]), 1)},
           "agora": agora_info, "carts": [{k_: v for k_, v in c_.items() if not k_.startswith("_")} for c_ in cart_info], "cart_cuts": cart_cuts,
           "scale": {"deck_freeboard_m": {k_: round(T["freeboard"] - T["drop"], 2) for k_, T in SHIPS.items() if k_ != "skiff"},
                     "cart_wheel_d_m": CART["wheel_d_m"], "cart_bed_top_m": CART["bed_top_m"], "stall_counter_m": STALL["counter_m"], "stall_awning_m": STALL["awning_m"], "amphora_h_m": 1.0}}
    sc = res["scale"]
    res["checks"] = {
        "every_ship_floats": all(ok for *_, ok in floats),
        "moored_ships_lie_alongside_their_quays": all(ok for *_, ok in alongside),
        "no_ship_cuts_a_quay_or_another_ship": not cuts,
        "gangplanks_walkable_30deg": all(d <= 30 for _, d in planks),
        "a_navigators_ship_at_each_of_the_seven_quays": navigators == 7,
        "outbound_merchantman_in_open_water_heading_out": (not ahead_hit) and beyond >= 150 and heading_off <= 30 and res["outbound"]["keel_clearance_m"] >= .5,
        "raft_floats_alongside_the_jetty": raft_floats and raft_alongside,
        "cheese_stalls_and_goat_pen_on_the_agora": inside and not overlap and fountain_gap >= 1.2 and sundial_gap >= 1.0 and math.hypot(pen[0], pen[1]) <= 12,
        "carts_on_tracks_at_grades_oxen_can_hold": carts_ok,
        "props_at_human_scale": all(.8 <= v <= 1.6 for v in sc["deck_freeboard_m"].values()) and 1.2 <= sc["cart_wheel_d_m"] <= 1.6
                                and .9 <= sc["cart_bed_top_m"] <= 1.2 and .8 <= sc["stall_counter_m"] <= 1.0 and sc["stall_awning_m"] >= 1.2 * ba.FIGURE}
    spots = [(c_["_xyz"][0] + 3 * math.cos(c_["_xyz"][3]), c_["_xyz"][1] + 3 * math.sin(c_["_xyz"][3]), 6.0) for c_ in cart_info if c_.get("placed")]   # carts with their oxen
    spots += [(px + s[0] * 12, py + s[1] * 12, 8.0)] + [(SX + tq[0] * toff, SY + tq[1] * toff, 9.0) for toff in (-40, 40, 110)]   # crane, amphora stacks
    views = {"outbound": (OX, OY, oinfo["deck_z"] + 6), "spots": spots, "galley_sea": sw, "barge_sea": gs, "raft_perp": (-ms, mc), "agora_P": AP,
             "cothon": (cx, cy, R, geo["cothon"]["quay_angles"]),
             "raft": (RLX, RLY), "market": AP(0, 4), "barge": None,
             "cart": next((c_["_xyz"] for c_ in cart_info if c_.get("placed") and c_["near"].startswith("granary")), None),
             "crane": (px + s[0] * 12, py + s[1] * 12), "cothon_ship": (moored[0][0]["X"], moored[0][0]["Y"]),
             "galley": next((i_["X"], i_["Y"], i_["ang"]) for i_, *_ in moored if i_["ob"].name.startswith("VII")),
             "barge_xy": next((i_["X"], i_["Y"], i_["ang"]) for i_, *_ in moored if i_["kind"] == "barge"), "agora_ang": aang, "raft_face": mface}
    return objs, res, views
