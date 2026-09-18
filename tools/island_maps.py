#!/usr/bin/env python3
"""The island of Paxos for art-direction-grand-island-shape.html.

The island is a real elevation field (metres) on an 11 x 8 km world, laid out along the
dependency graph between the papers, so walking it from the north-west reads the volumes
in order. The same source yields:
  maps/island.svg          rough map (hypsometric bands, roads, sites, volume zones)
  maps/island-height.png   16-bit heightmap for Blender displacement
  maps/island-sites.json   site positions + elevations (for empties) and the check results
and the map, measured checks and reading-order table are written into the page between
its MAP/STATS/ORDER markers.

World: x east, y south, in metres. SVG unit = 5 m.
Heightmap range: -120 m .. +480 m  ->  0 .. 65535.
"""
import heapq, json, math, re
from pathlib import Path
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "maps"
W, H, CELL, U = 8000.0, 5500.0, 12.5, 5.0          # metres, metres, m/cell, m/svg-unit
NX, NY = int(W / CELL), int(H / CELL)
HMIN, HMAX = -120.0, 480.0

X0, Y0 = np.meshgrid((np.arange(NX) + .5) * CELL, (np.arange(NY) + .5) * CELL)
X, Y = X0, Y0                                     # primitives read these; warp() bends them

def set_world(w, h):
    """island() calls this first; everything below reads these globals."""
    global W, H, NX, NY, X0, Y0, X, Y
    W, H = float(w), float(h)
    NX, NY = int(W / CELL), int(H / CELL)
    X0, Y0 = np.meshgrid((np.arange(NX) + .5) * CELL, (np.arange(NY) + .5) * CELL)
    X, Y = X0, Y0

# ---------------------------------------------------------------- primitives
def blob(cx, cy, rx, ry, h, ang=0.0, p=2.0):
    a = math.radians(ang); c, s = math.cos(a), math.sin(a)
    u = ((X - cx) * c + (Y - cy) * s) / rx
    v = (-(X - cx) * s + (Y - cy) * c) / ry
    return h * np.exp(-((u * u + v * v) ** (p / 2)))

def seg_dist(x0, y0, x1, y1, XX=None, YY=None):
    XX = X if XX is None else XX; YY = Y if YY is None else YY
    dx, dy = x1 - x0, y1 - y0
    t = np.clip(((XX - x0) * dx + (YY - y0) * dy) / (dx * dx + dy * dy), 0, 1)
    return np.hypot(XX - (x0 + t * dx), YY - (y0 + t * dy)), t

def ridge(x0, y0, x1, y1, w, h, p=2.0):
    d, _ = seg_dist(x0, y0, x1, y1)
    return h * np.exp(-((d / w) ** p))

def value_noise(seed, wavelengths=(1200, 600, 300, 150, 75), gain=.55):
    rng = np.random.default_rng(seed)
    out, amp, tot = np.zeros_like(X0), 1.0, 0.0
    for wl in wavelengths:
        gx, gy = int(W / wl) + 3, int(H / wl) + 3
        g = rng.uniform(-1, 1, (gy, gx))
        fx, fy = X0 / wl, Y0 / wl
        ix, iy = fx.astype(int), fy.astype(int)
        tx, ty = fx - ix, fy - iy
        tx, ty = tx * tx * (3 - 2 * tx), ty * ty * (3 - 2 * ty)
        a = g[iy, ix] * (1 - tx) + g[iy, ix + 1] * tx
        b = g[iy + 1, ix] * (1 - tx) + g[iy + 1, ix + 1] * tx
        out += amp * (a * (1 - ty) + b * ty); tot += amp; amp *= gain
    return out / tot

def warp(seed, amp=240.0):
    global X, Y
    X = X0 + amp * value_noise(seed + 100, (2200, 1100, 550))
    Y = Y0 + amp * value_noise(seed + 200, (2200, 1100, 550))

def finish(mass, seed, coast_noise=95.0, relief_noise=40.0):
    global X, Y
    h = mass - 45 + coast_noise * value_noise(seed) \
        + relief_noise * np.clip(mass / 250, 0, 1) * value_noise(seed + 1, (320, 160, 80, 40))
    X, Y = X0, Y0
    return np.where(h < 0, h * 1.6, h)

def near_sea(h, metres):
    k = max(1, int(metres / CELL))
    m = (h < 0).astype(np.int32)
    c = np.pad(m, ((k + 1, k), (k + 1, k))).cumsum(0).cumsum(1)
    box = c[2 * k + 1:, 2 * k + 1:] - c[:-2 * k - 1, 2 * k + 1:] - c[2 * k + 1:, :-2 * k - 1] + c[:-2 * k - 1, :-2 * k - 1]
    return box > 0

def snap(h, p, lo, hi, coast=None, radius=700.0):
    ok = (h >= lo) & (h <= hi)
    if coast: ok &= near_sea(h, coast)
    d2 = (X0 - p[0]) ** 2 + (Y0 - p[1]) ** 2
    d2 = np.where(ok & (d2 < radius * radius), d2, np.inf)
    i, j = np.unravel_index(np.argmin(d2), d2.shape)
    if not np.isfinite(d2[i, j]):
        print(f"      ! no cell in [{lo},{hi}] coast={coast} within {radius} m of {p}")
        return (float(p[0]), float(p[1]))
    return (float(X0[i, j]), float(Y0[i, j]))

def cothon(h, cx, cy, r=150.0):
    """Carthage-type circular inner harbour: quay platform, basin, central islet, channel to deep water."""
    d2 = (X0 - cx) ** 2 + (Y0 - cy) ** 2
    deep = np.where((h < -6) & (d2 > (r + 130) ** 2), d2, np.inf)                 # open water beyond the quay platform, so the channel reaches the sea
    i, j = np.unravel_index(np.argmin(deep), deep.shape)
    ex, ey = X0[i, j], Y0[i, j]
    d = np.hypot(X0 - cx, Y0 - cy)
    h = np.where(d < r + 100, np.maximum(h, 7.0), h)
    cd, _ = seg_dist(cx, cy, ex, ey, X0, Y0)
    h = np.where((d < r) | (cd < 22), np.minimum(h, -7.0), h)
    return np.where(d < r * .3, 4.0, h), math.degrees(math.atan2(ey - cy, ex - cx))

def open_sightline(h, a, b, margin, width, lead=80.0):
    """Lower only the ground that rises within `margin` of the sightline a=(x, y, eye z) -> b, fading out
    sideways over `width` metres and easing in over the first `lead` metres, so the view opens as a soft
    valley instead of a cut. Ground is never raised, and a's own spot is untouched."""
    (ax, ay, az), (bx, by, bz) = a, b
    dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy)
    s = ((X0 - ax) * dx + (Y0 - ay) * dy) / (L * L)
    t = np.clip(s, 0, 1)
    d = np.hypot(X0 - (ax + t * dx), Y0 - (ay + t * dy))
    line = az + (bz - az) * t - margin
    w = np.exp(-(d / width) ** 2) * np.clip(s * L / lead, 0, 1)
    return np.where(h > line, h - (h - line) * w, h)

def settle(h, a, b, level, width):
    """Ease ground above `level` down towards it along a strip a -> b with a soft sideways falloff: a coastal
    flat that never raises ground, so the shore keeps its natural slope."""
    d, _ = seg_dist(a[0], a[1], b[0], b[1], X0, Y0)
    w = np.exp(-(d / width) ** 2)
    return np.where(h > level, h - (h - level) * w, h)

def channel(h, axis, t, half, depth, seed, feather=140.0, wander=110.0):
    """Cut a sea channel square across an axis at fraction t, its banks wandering with noise."""
    (x0, y0), (x1, y1) = axis
    L = math.hypot(x1 - x0, y1 - y0); ux, uy = (x1 - x0) / L, (y1 - y0) / L
    d = np.abs((X0 - x0) * ux + (Y0 - y0) * uy - t * L + wander * value_noise(seed, (1400, 700, 350)))
    w = np.clip((half + feather - d) / feather, 0, 1); w = w * w * (3 - 2 * w)
    return np.minimum(h, h * (1 - w) - depth * w)

def keep_islands(h, anchors, shoal=-3.0):
    """Drown every patch of land not connected to one of the anchor points."""
    keep = np.zeros(h.shape, bool)
    for a in anchors: keep |= land_component(h, a)
    return np.where((h > 0) & ~keep, shoal, h)

def bezier(pts, n=60):
    (x0, y0), (x1, y1), (x2, y2) = pts
    return [((1 - t) ** 2 * x0 + 2 * (1 - t) * t * x1 + t * t * x2, (1 - t) ** 2 * y0 + 2 * (1 - t) * t * y1 + t * t * y2)
            for t in np.linspace(0, 1, n)]

def causeway(h, ctrl, seed, crest=(1.2, 2.6)):
    """A tombolo between the lobes: dry in summer, its crest low enough for winter seas to break over it."""
    line = bezier(ctrl)
    d = np.full(h.shape, np.inf)
    for k in range(len(line) - 1):
        d = np.minimum(d, seg_dist(*line[k], *line[k + 1], X0, Y0)[0])
    wob = value_noise(seed + 300, (900, 450, 220))                               # crest and width wander along it
    top = crest[0] + (crest[1] - crest[0]) * np.clip(.5 + wob, 0, 1)
    half = 42 + 22 * wob
    h = np.where(h < 0, np.maximum(h, -2.5 - (d / (95 + 40 * wob)) ** 2), h)       # sandbar shallows, fading into the deep
    bar = top * (1 - (d / half) ** 2)
    return np.where((d < half) & (h < top), np.maximum(h, bar), h)

# ---------------------------------------------------------------- sites (shared numbering)
# Every site belongs to exactly one volume and is numbered in walking order from the north-west.
# Kinds of place several volumes need (harbours, chambers, signal headlands) are built once per volume.
SITES = [  # num, key, name, volume, kind
    (1,  "hamA",      "Hamlet A",                      "1", "dot"),
    (2,  "hamK",      "Hamlet K",                      "1", "dot"),
    (3,  "hamM",      "Hamlet M",                      "1", "dot"),
    (4,  "press",     "Olive press",                   "1", "dot"),
    (5,  "beacons",   "Beacon headlands",              "1", "multi"),
    (6,  "watchtowers", "Coastal watchtowers",          "2", "tower"),
    (7,  "fleet",      "Defensive fleet anchorages",    "3", "fleet"),
    (8,  "redoubt",    "Admirals' coastal redoubt",     "3", "redoubt"),
    (9,  "cothon",    "Lantern harbour (cothon)",      "4", "cothon"),
    (10, "drummers",  "Drummers' headlands",           "4", "multi"),
    (11, "strait",    "The causeway",                  "4", "strait"),
    (12, "town",      "Harbour town · agora",          "5", "dot"),
    (13, "port",      "Merchant quays",                "5", "port"),
    (14, "round",     "The Great Round",               "5", "round"),
    (15, "banquet",   "Banquet house",                 "5", "dot"),
    (16, "granary",   "Granary storehouses",           "6", "multi"),
    (17, "granary2",  "Granary on the heights",        "6", "dot"),
    (18, "citadel",   "Citadel of Iron Quorums",       "7", "citadel"),
    (19, "seawall",   "Citadel harbour & sea wall",    "7", "harbour"),
    (20, "hall",      "Guild hall",                    "8", "hall"),
    (21, "locks",     "Italian guild lock-houses",     "8", "multi"),
    (22, "cliffs",    "Ledger cliffs",                 "8", "cliff"),
    (23, "monastery", "Raft monastery",                "9", "dot"),
]
# Volumes are numbered in walking order. Dependencies between the papers as (parent, child),
# and the dependency graph's bands, north-west to south-east.
DEPENDS = [(1, 5), (2, 4), (4, 5), (5, 6), (5, 9), (3, 7), (6, 7), (6, 8), (6, 9)]
BANDS = [[1, 2, 3], [4], [5], [6], [7, 8, 9]]
VOL_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}
# what each site demands of the ground: (min m, max m, within-metres-of-sea or None)
RULES = {"hamA": (40, 230, None), "hamK": (40, 230, None), "hamM": (40, 230, None), "press": (90, 300, None),
         "citadel": (60, 240, 420), "watchtowers": (25, 220, 260),
          "town": (4, 50, 320), "round": (140, 270, None), "banquet": (90, 250, None),
          "granary": (5, 90, None), "granary2": (90, 240, None), "cliffs": (15, 220, 140), "locks": (60, 300, None),
          "monastery": (15, 180, None), "beacons": (15, 260, 260), "drummers": (15, 260, 260), "port": (1, 30, 200),
          "fleet": (-90, -10, None), "redoubt": (60, 220, 420), "seawall": (1, 25, 150), "hall": (60, 260, None)}

# ---------------------------------------------------------------- the island
AXIS = ((1500.0, 1300.0), (9800.0, 7200.0))                                       # NW root -> SE leaves
ROUND_COL, PORT = (5384.0, 4132.0), (5990.0, 3630.0)                              # the Round's col, and the quays below it

def axis_at(t, n=0.0):
    (x0, y0), (x1, y1) = AXIS
    L = math.hypot(x1 - x0, y1 - y0); ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = uy, -ux
    return (x0 + ux * L * t + nx * n, y0 + uy * L * t + ny * n)

def island():
    """The island laid out along the papers' dependency graph, read NW -> SE:
    I, II, III on the first lobe, then IV (the causeway neck), then V (the Round's col),
    then VI (the granary plain), then VII beside VIII, and IX on an islet across a strait.
    See DEPENDS/BANDS and SITES."""
    set_world(11000, 8000)
    (x0, y0), (x1, y1) = AXIS
    L = math.hypot(x1 - x0, y1 - y0); ux, uy = (x1 - x0) / L, (y1 - y0) / L
    nx, ny = uy, -ux                                                             # +n points north-east
    at = lambda t, n=0.0: (x0 + ux * L * t + nx * n, y0 + uy * L * t + ny * n)
    ang = math.degrees(math.atan2(uy, ux))
    bead = lambda t, n, ra, rc, hh, p=2.4: blob(*at(t, n), ra, rc, hh, ang=ang, p=p)
    warp(61, 200)
    m = ridge(*at(-.02), *at(.84), 620, 95, p=2.0)                               # the low spine that strings the beads
    m += bead(.05, 520, 760, 640, 190)                                           # I   Disordered Sundials
    m += bead(.11, -560, 720, 620, 285)                                          # II  Sleeping Shepherd (the summit)
    m += bead(.15, -1250, 560, 480, 150)                                         # III Admirals: coastal headland
    m += bead(.27, 0, 520, 420, 70)                                              # IV  Passable Season: the low neck
    m += bead(.425, 0, 380, 520, 185) + bead(.545, 0, 380, 520, 180)             # V   two knolls either side of the Round's col
    m += bead(.485, 0, 950, 650, 100, p=3.0)                                     #     the Parliament's broad middle
    m += ridge(*at(.43), *at(.54), 230, 40)                                       #     a narrow crest, so the col falls away to both coasts
    m -= ridge(*at(.48, 170), *at(.48, 1150), 230, 45, p=1.6)                   #     the valley from the col down to the port
    m += bead(.64, 720, 500, 440, 80)                                            #     natural shoulder on SE lobe
    m += bead(.66, -700, 700, 640, 70, p=3.0)                                    # VI  Ledger: the granary plain
    m += bead(.79, 760, 600, 540, 165)                                           # VII Citadel
    m += bead(.80, -760, 640, 560, 175)                                          # VIII Quarries: cliffs and the lock ridge
    m += bead(.975, 150, 520, 380, 150)                                          # IX  Raft Monks' islet
    for t, n, ra, rc, dd in ((.20, 1250, 420, 380, 150), (.70, 1350, 380, 420, 150), (.73, -1400, 360, 420, 150),
                             (.59, -1250, 380, 480, 190), (.59, 1300, 360, 460, 180)):
        m -= bead(t, n, ra, rc, dd)                                              # bays in the notches between paired zones
    h = finish(m, 61)
    h = settle(h, at(.505, 820), at(.59, 880), 12.0, 230)                          # the coastal flat the harbour town stands on
    R, T = ROUND_COL, PORT                                                       # keep the quays in view from the Round's tiers
    h = open_sightline(h, (*R, h_at(h, *R) + 8), (*T, h_at(h, *T) + 2), 10.0, 140.0)
    h = channel(h, AXIS, .31, 150, 9.0, seed=62, feather=320, wander=120)                               # the neck the causeway crosses
    def landfall(direction):                                                     # walk out from the neck until the ground is 3 m up
        t = .31
        while h_at(h, *at(t, -20)) < 3 and abs(t - .31) < .12: t += direction * 10 / L
        return t + direction * 40 / L
    t0, t1 = landfall(-1), landfall(1)
    cw = [at(t0, -20), at((t0 + t1) / 2, 90), at(t1, -20)]                          # the causeway always reaches land at both ends
    sea_before = h < 0
    h = causeway(h, cw, seed=61)
    h = channel(h, AXIS, .905, 170, 18.0, seed=63, feather=380, wander=260)                             # the strait to the Raft islet
    h = keep_islands(h, [at(.11, -560), at(.48), at(.975, 150)], shoal=-8.0)
    sites = {                                                                    # one volume per site, walked NW -> SE
        "hamA": at(.0, 650), "hamK": at(.08, -1000), "hamM": at(.17, 700), "press": at(.05, 450),
        "beacons": [at(.15, 1150), at(.225, 1000)],                              # I: across the north-east bay
        "watchtowers": [at(.04, 1000), at(.11, 750), at(.12, -1150), at(.05, -1350)], # II (North Bluff, East Cape, South Crag, West Point)
        "fleet": [at(.155, -1780), at(.138, -1740), at(.172, -1750), at(.155, -1920)], # III (Flag w0, Wing w1, Wing w2, Vanguard w3)
        "redoubt": at(.155, -1350),                                              # III (cliff redoubt overlooking fleet)
        "drummers": [at(.285, 700), at(.335, 700)], "strait": bezier(cw, 3)[1],  # IV (the cothon is the hint below)
        "town": at(.535, 900), "port": PORT, "round": ROUND_COL, "banquet": at(.48, 300),       # V
        "granary": [at(.62, -350), at(.65, -850), at(.68, -1300)], "granary2": at(.69, -150),  # VI
        "citadel": at(.80, 1150), "seawall": at(.785, 1550),                                   # VII
        "hall": at(.765, -350), "locks": [at(.80, -250 - 200 * k) for k in range(5)],          # VIII
        "cliffs": at(.83, -1350),
        "monastery": at(.975, 150),                                                            # IX
    }
    zones = [("I", .03, 900), ("II", .11, -650), ("III", .155, -1800), ("IV", .30, -700), ("V", .49, -900),
             ("VI", .64, -1250), ("VII", .815, 2050), ("VIII", .80, -1450), ("IX", .975, -650)]
    return h, sites, at(.26, -520), {"round_radius": 0, "round_saddle": True, "causeway": (cw, sea_before),
                                     "axis": AXIS, "sites": SITES, "sight_pairs": ["beacons", "drummers"],
                                     "zones": [(z, *at(t, n)) for z, t, n in zones]}

TITLE = "The Dependency Spine"

def build():
    h, rough, hint, over = island()
    ct = snap(h, hint, 1, 30, 200, 900)
    h, mouth = cothon(h, *ct)
    over = {**over, "cothon_channel_deg": mouth}
    rules = {**RULES, **over}
    loc = {"cothon": ct, "strait": rough["strait"]}
    for skey, v in rough.items():
        if skey in loc: continue
        lo, hi, coast = rules[skey]
        loc[skey] = [snap(h, p, lo, hi, coast) for p in v] if isinstance(v, list) else snap(h, v, lo, hi, coast)
    place_by_sight(h, loc, rough, rules)
    loc["_tracks"] = track_network(h, loc, rules)
    return h, loc, rules

def candidates(h, centre, radius, lo, hi, step=50.0):
    out = []
    for dx in np.arange(-radius, radius + 1, step):
        for dy in np.arange(-radius, radius + 1, step):
            x, y = centre[0] + dx, centre[1] + dy
            if dx * dx + dy * dy <= radius * radius and 0 <= x < W and 0 <= y < H and lo <= h_at(h, x, y) <= hi:
                out.append((float(x), float(y)))
    return out

def harbour_of(loc):
    """The harbour the Round looks down on: its own quays, else the cothon."""
    return loc.get("port", loc["cothon"])

def place_by_sight(h, loc, rough, rules):
    """Sightline rules the elevation bands can't express: the Round's col and view, the banquet house, headland pairs, hidden hamlets."""
    # The Round: a saddle with sea on two sides -> maximise the sea arc, prefer two opposed arcs.
    lo, hi, _ = rules["round"]
    def score(p):
        b = sea_bearings(h, p, reach=3000, step_m=50)
        opposed = two_sided(b)
        harbour = los_clear(h, p, harbour_of(loc), 8, 2)      # "beyond the gate a galley sets sail from the harbour below"
        saddle = 300 if rules.get("round_saddle") and is_saddle(h, p) else 0
        return len(b) * 15 + (90 if opposed else 0) + (120 if harbour else 0) + saddle - math.dist(p, rough["round"]) / 25
    pool = candidates(h, rough["round"], rules.get("round_radius", 900), lo, hi) + [loc["round"]]
    clear = [c for c in pool if math.dist(c, loc["town"]) >= ROUND_TOWN_MIN]         # above the town, not in it
    loc["round"] = max(clear or pool, key=score)
    # Banquet house: a short walk east of the Round, lower, in plain view of the tiers.
    r = loc["round"]; rz = h_at(h, *r)
    want = (r[0] + 160, r[1])
    ok = [c for c in candidates(h, want, 200, max(5, rz - 70), rz - 4, 25)
          if c[0] - r[0] >= 120 and abs(c[1] - r[1]) <= 60 and los_clear(h, r, c, 6, 4)]   # due east, off the east gate
    if ok: loc["banquet"] = min(ok, key=lambda c: math.dist(c, want))
    else: print("      ! no visible banquet site east of the Round")
    # Beacon pairs: the second headland must see the first across the water.
    for key in rules.get("sight_pairs", []):
        sig = loc[key]; lo, hi, coast = rules[key]
        if los_clear(h, sig[0], sig[1], 6, 6): continue
        near = near_sea(h, coast)
        ok = [c for c in candidates(h, rough[key][1], 700, lo, hi, 25)
              if near[int(c[1] / CELL), int(c[0] / CELL)] and los_clear(h, sig[0], c, 6, 6)]
        if ok: sig[1] = min(ok, key=lambda c: math.dist(c, rough[key][1]))
        else: print(f"      ! {key}: no headland in sight of the first")
    # Hamlets: each hidden from the ones already placed.
    placed = [loc["hamA"]]
    for k in ("hamK", "hamM"):
        lo, hi, _ = rules[k]
        if all(not los_clear(h, loc[k], q, 3, 3) for q in placed):
            placed.append(loc[k]); continue
        ok = [c for c in candidates(h, rough[k], 900, lo, hi, 50) if all(not los_clear(h, c, q, 3, 3) for q in placed)]
        if ok: loc[k] = min(ok, key=lambda c: math.dist(c, rough[k]))
        else: print(f"      ! {k}: no hidden site within 900 m")
        placed.append(loc[k])

# ---------------------------------------------------------------- terrain queries
def h_at(h, x, y):
    j, i = int(np.clip(x / CELL, 0, NX - 1)), int(np.clip(y / CELL, 0, NY - 1))
    return float(h[i, j])

ROUND_TOWN_MIN = 500.0

def is_saddle(h, p, r=200.0, rel=8.0):
    """Ground rises both ways along one axis and falls both ways across it."""
    z0 = h_at(h, *p)
    d = [h_at(h, p[0] + r * math.sin(k * math.pi / 4), p[1] - r * math.cos(k * math.pi / 4)) - z0 for k in range(8)]
    return any(min(d[k], d[k + 4]) > rel and max(d[k + 2], d[(k + 6) % 8]) < -rel for k in range(4))

def measure_causeway(h, spec, step=10.0):
    """Crest profile of the bar over what was open water before it was laid."""
    ctrl, sea_before = spec
    line = bezier(ctrl, 400)
    crest, widths, run = [], [], 0.0
    for k in range(1, len(line) - 1):
        (x0, y0), (x1, y1) = line[k - 1], line[k + 1]
        x, y = line[k]; z = h_at(h, x, y)
        if not sea_before[int(np.clip(y / CELL, 0, NY - 1)), int(np.clip(x / CELL, 0, NX - 1))]: continue
        crest.append(z); run += math.dist(line[k], line[k + 1])
        nx, ny = -(y1 - y0), x1 - x0; n = math.hypot(nx, ny); nx, ny = nx / n, ny / n
        widths.append(sum(step for o in np.arange(-150, 150, step) if h_at(h, x + nx * o, y + ny * o) > 1.5))
    return {"length_m": round(run), "crest_min_m": round(min(crest), 1), "crest_max_m": round(max(crest), 1),
            "width_above_1_5m_mean": round(float(np.mean(widths))), "dry_in_calm": min(crest) > .5,
            "winter_seas_break_over": max(crest) <= 3.0}

def land_component(h, p):
    """Boolean mask of the dry land connected to p (4-neighbour flood fill)."""
    land = h > 0; seen = np.zeros_like(land)
    i0, j0 = int(np.clip(p[1] / CELL, 0, NY - 1)), int(np.clip(p[0] / CELL, 0, NX - 1))
    if not land[i0, j0]: return seen
    stack = [(i0, j0)]; seen[i0, j0] = True
    while stack:
        i, j = stack.pop()
        for ii, jj in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1)):
            if 0 <= ii < NY and 0 <= jj < NX and land[ii, jj] and not seen[ii, jj]:
                seen[ii, jj] = True; stack.append((ii, jj))
    return seen

# The track network: spurs to every mainland site, joined hub to hub in walking order. Hamlets hang off different
# hubs (press, watchtowers, beacon) so no track runs straight from one hamlet to another. min_z 0.5 lets tracks use the causeway.
TRACKS = [("hamA", "press"), ("press", "beacons:0"), ("press", "watchtowers:0"),
          ("watchtowers:0", "watchtowers:1"), ("watchtowers:1", "watchtowers:2"),
          ("watchtowers:2", "watchtowers:3"), ("watchtowers:3", "watchtowers:0"),
          ("watchtowers:3", "hamK"), ("hamM", "beacons:1"),
          ("watchtowers:2", "redoubt"), ("redoubt", "fleet"),
          ("watchtowers:1", "cothon"), ("beacons:1", "cothon"), ("cothon", "strait"), ("strait", "drummers:0"), ("strait", "drummers:1"),
          ("strait", "port"), ("port", "town"), ("round", "banquet"),
          ("town", "granary:0"), ("granary:0", "granary:1"), ("granary:1", "granary:2"), ("granary:0", "granary2"),
          ("granary2", "citadel"), ("citadel", "seawall"), ("granary2", "hall"), ("hall", "locks:0"), ("locks:0", "locks:4"), ("hall", "cliffs")]

TRACK_SLOPE_K = 150.0                                                            # mule tracks accept 15-25% grades rather than detour for kilometres

def site_point(h, loc, ref):
    key, _, k = ref.partition(":")
    v = loc[key]
    p = v[int(k or 0)] if isinstance(v, list) else v
    if key == "fleet":                                                           # mule track ends at the shore landing / skiff slipway
        p = axis_at(.155, -1670)
    if key == "strait":                                                          # onto the causeway's crest
        best = max(((p[0] + dx, p[1] + dy) for dx in range(-100, 101, 12) for dy in range(-100, 101, 12)), key=lambda q: h_at(h, *q) - math.hypot(q[0] - p[0], q[1] - p[1]) / 50)
        p = best
    if key == "cothon":                                                          # the site point is the lighthouse islet; tracks end on the quay ring
        ring = [(p[0] + 205 * math.cos(a), p[1] + 205 * math.sin(a)) for a in np.linspace(0, math.tau, 72, endpoint=False)]
        ring = [q for q in ring if 2 <= h_at(h, *q) <= 30]
        p = min(ring, key=lambda q: h_at(h, *q)) if ring else p
    return p

def track_network(h, loc, rules):
    """Least-cost paths for TRACKS, plus the Statue Walk from the town to the Round. The causeway corridor is passable
    even where its 25 m samples dip below the land threshold."""
    passable = None
    if "causeway" in rules:
        line = bezier(rules["causeway"][0], 80)
        dist = np.full(h.shape, np.inf)
        for q0, q1 in zip(line, line[1:]): dist = np.minimum(dist, seg_dist(*q0, *q1, X0, Y0)[0])
        passable = dist < 30
    out = [(a, b, least_cost_path(h, site_point(h, loc, a), site_point(h, loc, b), slope_k=TRACK_SLOPE_K, min_z=.5, passable=passable)) for a, b in TRACKS]
    return out, least_cost_path(h, loc["town"], loc["round"])

def tracks_connected(loc, edges):
    """Every mainland site sits in one connected network (the Round via the Statue Walk; IX is on its islet)."""
    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x: x = parent[x]
        return x
    for a, b in list(edges) + [("town", "round")]:
        parent[find(a.split(":")[0])] = find(b.split(":")[0])
    keys = {k for k in loc if k not in ("monastery",) and not k.startswith("_")}
    return len({find(k) for k in keys}) == 1, sorted(k for k in keys if find(k) != find("town"))

def open_water_reaches_edge(h, p):
    """The cothon basin's water connects to the open sea at the edge of the world."""
    water = land_component(-h, p)
    return water[0, :].any() or water[-1, :].any() or water[:, 0].any() or water[:, -1].any()

def axis_t(axis, p):
    (x0, y0), (x1, y1) = axis
    L2 = (x1 - x0) ** 2 + (y1 - y0) ** 2
    return ((p[0] - x0) * (x1 - x0) + (p[1] - y0) * (y1 - y0)) / L2

def dependency_order(loc, axis, sites):
    """Walking the axis NW -> SE reads the papers in dependency order: every site of a volume lies
    before every site of each volume built on it (DEPENDS), and the graph's bands follow one another."""
    ts = {}
    for num, key, name, vols, kind in sites:
        if key not in loc: continue
        pts = loc[key] if isinstance(loc[key], list) else [loc[key]]
        ts.setdefault(int(vols), []).extend(axis_t(axis, q) for q in pts)
    span = {v: (round(min(t), 3), round(max(t), 3)) for v, t in ts.items()}
    broken = [f"{VOL_ROMAN[a]}→{VOL_ROMAN[b]}" for a, b in DEPENDS if not span[a][1] < span[b][0]]
    bands = [(min(span[v][0] for v in g), max(span[v][1] for v in g)) for g in BANDS]
    band_ok = all(bands[k][1] < bands[k + 1][0] for k in range(len(bands) - 1))
    return {"edges_ok": not broken, "broken_edges": broken, "bands_ok": band_ok,
            "spans": {VOL_ROMAN[v]: span[v] for v in sorted(span)}}

def least_cost_path(h, a, b, slope_k=900.0, min_z=1.5, passable=None):
    """Dijkstra on a 25 m grid; roads avoid water (ground below min_z, unless `passable` says otherwise) and steep ground.
    Returns [] when b can't be reached."""
    step = 2                                                                      # 25 m moves
    hs = h[::step, ::step]; ny, nx = hs.shape; c = CELL * step
    ok = hs >= min_z
    if passable is not None: ok |= passable[::step, ::step][:ny, :nx]
    s = (int(a[1] / c), int(a[0] / c)); g = (int(b[1] / c), int(b[0] / c))
    dist = np.full(hs.shape, np.inf); prev = {}
    dist[s] = 0; pq = [(0.0, s)]
    nb = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    while pq:
        dd, (i, j) = heapq.heappop(pq)
        if (i, j) == g: break
        if dd > dist[i, j]: continue
        for di, dj in nb:
            ii, jj = i + di, j + dj
            if not (0 <= ii < ny and 0 <= jj < nx): continue
            if not ok[ii, jj] and (ii, jj) != g: continue
            run = c * math.hypot(di, dj); grade = abs(hs[ii, jj] - hs[i, j]) / run
            nd = dd + run * (1 + slope_k * grade * grade)
            if nd < dist[ii, jj]:
                dist[ii, jj] = nd; prev[(ii, jj)] = (i, j); heapq.heappush(pq, (nd, (ii, jj)))
    if g != s and g not in prev: return []
    path, cur = [], g
    while cur in prev: path.append(((cur[1] + .5) * c, (cur[0] + .5) * c)); cur = prev[cur]
    path.append(a); path.reverse(); path[-1] = b
    return path

def los_clear(h, p, q, eye=1.7, target=1.7, n=400):
    """True if nothing on the ground rises above the sightline from p (eye) to q (target)."""
    (x0, y0), (x1, y1) = p, q
    h0, h1 = max(h_at(h, x0, y0), 0) + eye, max(h_at(h, x1, y1), 0) + target
    for t in np.linspace(0, 1, n)[1:-1]:
        if h_at(h, x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) > h0 + (h1 - h0) * t + .5:
            return False
    return True

def sea_bearings(h, p, eye=8.0, reach=4000.0, step_deg=15, step_m=25.0):
    """Bearings (of 360/step) along which open sea is visible from p."""
    x0, y0 = p; e = h_at(h, x0, y0) + eye; seen = []
    for b in range(0, 360, step_deg):
        dx, dy = math.sin(math.radians(b)), -math.cos(math.radians(b))   # 0 = north
        best = -1e9
        for d in np.arange(step_m, reach, step_m):
            x, y = x0 + dx * d, y0 + dy * d
            if not (0 <= x < W and 0 <= y < H): break
            z = h_at(h, x, y)
            if z < 0:
                if (0 - e) / d > best: seen.append(b); break
            else:
                best = max(best, (z - e) / d)
    return seen

def arcs(bearings, step=15):
    """Contiguous runs of visible-sea bearings, as (centre_deg, width_deg)."""
    on = set(bearings)
    if len(on) * step >= 360: return [(0, 360)]
    start = next(b for b in range(0, 360, step) if b not in on)
    out, run = [], []
    for k in range(1, 361 // step + 1):
        b = (start + k * step) % 360
        if b in on: run.append(b)
        elif run:
            out.append(((run[0] + (len(run) - 1) * step / 2) % 360, len(run) * step)); run = []
    return out

def two_sided(bearings):
    """Sea on both sides of a saddle: two arcs ≥30° facing apart, or one arc wrapping ≥240°."""
    a = arcs(bearings)
    if any(w >= 240 for _, w in a): return True
    big = [c for c, w in a if w >= 30]
    return any(abs((x - y + 180) % 360 - 180) >= 120 for x in big for y in big)

def checks(h, loc, rules):
    hams = [("A", loc["hamA"]), ("K", loc["hamK"]), ("M", loc["hamM"])]
    pairs = [(a, b) for i, a in enumerate(hams) for b in hams[i + 1:]]
    ham_seen = [f"{a[0]}–{b[0]}" for a, b in pairs if los_clear(h, a[1], b[1], 3, 3)]
    pair_keys = rules.get("sight_pairs", [])        # each list's first two points: a beacon pair across the water
    sig_ok = sum(los_clear(h, loc[k][0], loc[k][1], 6, 6) for k in pair_keys)
    sig_pairs = pair_keys
    sea = sea_bearings(h, loc["round"])
    return {"hamlets_mutually_visible": ham_seen,
            "banquet_visible_from_round": los_clear(h, loc["round"], loc["banquet"], 6, 4),
            "round_sea_bearings": len(sea) * 15, "round_sea_two_sided": two_sided(sea), "round_sea_arcs": arcs(sea),
            "signal_pairs_clear": [sig_ok, len(sig_pairs)],
            "town_to_round_clear": los_clear(h, loc["round"], harbour_of(loc), 8, 2),
            "round_in_saddle": is_saddle(h, loc["round"]), "round_town_m": round(math.dist(loc["round"], loc["town"])),
            "banquet_offset_m": [round(loc["banquet"][0] - loc["round"][0]), round(loc["banquet"][1] - loc["round"][1])],
            **({"causeway": measure_causeway(h, rules["causeway"])} if "causeway" in rules else {}),
            **({"dependency_order": dependency_order(loc, rules["axis"], rules["sites"])} if "axis" in rules else {}),
            "tracks_connect_every_mainland_site": tracks_connected(loc, [(a, b) for a, b, p in loc["_tracks"][0] if len(p) >= 2])[0],
            "tracks_unreachable": [f"{a}–{b}" for a, b, p in loc["_tracks"][0] if len(p) < 2],
            "tracks_hamlet_to_hamlet": [f"{a}–{b}" for a, b in TRACKS if a.startswith("ham") and b.startswith("ham")],
            "causeway_joins_the_neck": bool(land_component(h, loc["watchtowers"][0])[int(loc["round"][1] / CELL), int(loc["round"][0] / CELL)]),
            "agora_on_dry_land": bool(agora_footprint(h, *town_layout(h, loc)[0][:2], math.radians(town_layout(h, loc)[0][2])).min() > 2),
            "cothon_open_to_sea": bool(open_water_reaches_edge(h, (loc["cothon"][0] + 100, loc["cothon"][1]))),   # start in the basin, not on the islet
            **({"monastery_detached": not land_component(h, loc["round"])[int(loc["monastery"][1] / CELL), int(loc["monastery"][0] / CELL)]}
               if "monastery" in loc else {})}

# ---------------------------------------------------------------- contours
def march(h, t):
    f = np.pad(h, 1, constant_values=-1e4)
    ny, nx = f.shape
    ins = f >= t
    code = ins[:-1, :-1] * 8 + ins[:-1, 1:] * 4 + ins[1:, 1:] * 2 + ins[1:, :-1] * 1
    pt = {}
    def P(e):
        if e not in pt:
            k, i, j = e
            if k == "h": a, b, x0, y0, dx, dy = f[i, j], f[i, j + 1], j, i, 1, 0
            else:        a, b, x0, y0, dx, dy = f[i, j], f[i + 1, j], j, i, 0, 1
            fr = (t - a) / (b - a) if b != a else .5
            pt[e] = ((x0 + dx * fr - 1 + .5) * CELL / U, (y0 + dy * fr - 1 + .5) * CELL / U)
        return e
    adj = {}
    def link(a, b):
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    T = {1: [("l", "b")], 2: [("b", "r")], 3: [("l", "r")], 4: [("t", "r")], 6: [("t", "b")],
         7: [("l", "t")], 8: [("l", "t")], 9: [("t", "b")], 11: [("t", "r")], 12: [("l", "r")],
         13: [("b", "r")], 14: [("l", "b")]}
    for i, j in zip(*np.nonzero((code > 0) & (code < 15))):
        c = int(code[i, j])
        E = {"t": ("h", i, j), "b": ("h", i + 1, j), "l": ("v", i, j), "r": ("v", i, j + 1)}
        if c in (5, 10):
            centre = (f[i, j] + f[i, j + 1] + f[i + 1, j] + f[i + 1, j + 1]) / 4 >= t
            if c == 5: pairs = [("l", "t"), ("b", "r")] if centre else [("l", "b"), ("t", "r")]
            else:      pairs = [("t", "r"), ("l", "b")] if centre else [("l", "t"), ("b", "r")]
        else:
            pairs = T[c]
        for a, b in pairs: link(P(E[a]), P(E[b]))
    loops, seen = [], set()
    for start in adj:
        if start in seen: continue
        loop, prev, cur = [], None, start
        while True:
            seen.add(cur); loop.append(pt[cur])
            nxt = [n for n in adj[cur] if n != prev and n not in seen]
            if not nxt: break
            prev, cur = cur, nxt[0]
        if len(loop) >= 6: loops.append(loop)
    return loops

def chaikin(pts, n=2, closed=True):
    for _ in range(n):
        q = []
        m = len(pts) if closed else len(pts) - 1
        for k in range(m):
            (x0, y0), (x1, y1) = pts[k], pts[(k + 1) % len(pts)]
            q += [(.75 * x0 + .25 * x1, .75 * y0 + .25 * y1), (.25 * x0 + .75 * x1, .25 * y0 + .75 * y1)]
        pts = q if closed else [pts[0]] + q + [pts[-1]]
    return pts

def rdp(pts, eps):
    if len(pts) < 3: return pts
    a, b = np.array(pts[0]), np.array(pts[-1]); ab = b - a; n = np.hypot(*ab) or 1.0
    d = [abs(ab[0] * (p[1] - a[1]) - ab[1] * (p[0] - a[0])) / n for p in pts[1:-1]]
    k = int(np.argmax(d)) + 1
    if d[k - 1] > eps: return rdp(pts[:k + 1], eps)[:-1] + rdp(pts[k:], eps)
    return [pts[0], pts[-1]]

def loops_to_d(loops, eps=.45, min_area=6.0):
    out = []
    for lp in loops:
        xs, ys = zip(*lp)
        area = .5 * abs(sum(xs[k] * ys[k - 1] - xs[k - 1] * ys[k] for k in range(len(lp))))
        if area < min_area: continue
        c = chaikin(lp)
        far = max(range(len(c)), key=lambda k: (c[k][0] - c[0][0]) ** 2 + (c[k][1] - c[0][1]) ** 2)
        p = rdp(c[:far + 1], eps)[:-1] + rdp(c[far:] + [c[0]], eps)
        out.append("M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in p) + "Z")
    return "".join(out)

def smooth_d(pts_m, closed=False):
    p = [(x / U, y / U) for x, y in pts_m]
    p = rdp(chaikin(p, 3, closed=False), .6)
    return "M" + "L".join(f"{x:.1f} {y:.1f}" for x, y in p)

# ---------------------------------------------------------------- svg
SEA_T = [-60, -25]
LAND_T = [0, 20, 70, 140, 220, 300, 380]
LINE_T = [-5, -13, -24]

AGORA_M = (40.0, 30.0)

def agora_footprint(h, x, y, ang):
    c, s = math.cos(ang), math.sin(ang)
    return np.array([h_at(h, x + u * c - v * s, y + u * s + v * c) for u in np.linspace(-AGORA_M[0] / 2, AGORA_M[0] / 2, 9)
                     for v in np.linspace(-AGORA_M[1] / 2, AGORA_M[1] / 2, 7)])

def agora_on_land(h, x, y, ang, inland):
    """Move the agora inland (toward `inland`) until its whole footprint stands on dry ground 2 m up."""
    n = math.hypot(*inland) or 1; ux, uy = inland[0] / n, inland[1] / n
    for step in range(60):
        if agora_footprint(h, x + ux * step * 5, y + uy * step * 5, ang).min() > 2: return x + ux * step * 5, y + uy * step * 5
    return x, y

def town_layout(h, loc):
    """The harbour town: 44 x 30 m insulae on a street grid squared to the harbour, with the agora left open
    at the centre. Returns ((x, y, deg) of the agora, [(x, y, deg) per insula]), deg measured from +x towards +y."""
    rng = np.random.default_rng(7)
    tx, ty = loc["town"]; cx_, cy_ = harbour_of(loc); rnd = loc["round"]
    ang = math.atan2(cy_ - ty, cx_ - tx); ca, sa = math.cos(ang), math.sin(ang)
    tx, ty = agora_on_land(h, tx, ty, ang, (rnd[0] - tx, rnd[1] - ty))
    blocks = []
    for i in range(-9, 10):
        for j in range(-9, 10):
            u, v = i * 52.0, j * 38.0                                            # 44 x 30 m blocks, 8 m streets
            if abs(u) < 60 and abs(v) < 45: continue                             # the agora
            x, y = tx + u * ca - v * sa, ty + u * sa + v * ca
            z = h_at(h, x, y)
            if not 3 < z < 95 or math.hypot(u, v) > 460 + 80 * rng.random() or rng.random() < .2: continue
            if math.dist((x, y), (cx_, cy_)) < 240 or math.dist((x, y), rnd) < 380: continue
            if abs(h_at(h, x + 25, y) - h_at(h, x - 25, y)) > 16 or abs(h_at(h, x, y + 25) - h_at(h, x, y - 25)) > 16: continue
            blocks.append((float(x), float(y), math.degrees(ang)))
    return (float(tx), float(ty), math.degrees(ang)), blocks

def svg_for(title, h, site_list, loc, zones=(), clean=False):
    """clean=True is the layout reference for the painted map: no text, numbers, dots, compass or scale bar."""
    S = []
    VW, VH = W / U, H / U
    S.append(f'<svg class="islemap" viewBox="0 0 {VW:.0f} {VH:.0f}" role="img" aria-labelledby="map-island-t" xmlns="http://www.w3.org/2000/svg">')
    S.append(f'<title id="map-island-t">{title}: rough map of Paxos</title>')
    S.append(f'<rect class="sea0" x="0" y="0" width="{VW:.0f}" height="{VH:.0f}"/>')
    if clean:                                                                    # one shallow halo, so offshore shoals can't read as land
        near_land = near_sea(-h, 250.0)
        S.append(f'<path class="sea2" fill-rule="evenodd" d="{loops_to_d(march(np.where(near_land, h, -50.0), -6), .8, 20)}"/>')
    else:
        for k, t in enumerate(SEA_T):
            S.append(f'<path class="sea{k + 1}" fill-rule="evenodd" d="{loops_to_d(march(h, t), .8, 20)}"/>')
        for k, t in enumerate(LINE_T):
            S.append(f'<path class="wline wl{k}" d="{loops_to_d(march(h, t), .6, 10)}"/>')
    for k, t in enumerate(LAND_T):
        d = loops_to_d(march(h, t), .45, 6 if k else 3)
        S.append(f'<path class="land{k}{" coast" if k == 0 else " contour"}" fill-rule="evenodd" d="{d}"/>')
    for z, zx, zy in ([] if clean else zones):                                   # volume zones along the dependency axis
        S.append(f'<text class="zone" x="{zx / U:.0f}" y="{zy / U:.0f}">{z}</text>')
    # tracks (least-cost network), then the Statue Walk on top
    tracks, walk = loc["_tracks"]
    for a, b, path in tracks:
        if len(path) > 2: S.append(f'<path class="road track" d="{smooth_d(path)}"/>')
    S.append(f'<path class="road walk" d="{smooth_d(walk)}"/>')
    if not clean: S.append(f'<path class="road walk-dots" d="{smooth_d(walk)}"/>')
    # town: insulae on a street grid squared to the harbour, agora left open at the centre
    agora, blocks = town_layout(h, loc)
    tx, ty, adeg = agora
    S.append(f'<rect class="agora" x="-9" y="-7" width="18" height="14" transform="translate({tx / U:.1f} {ty / U:.1f}) rotate({adeg:.1f})"/>')
    for x, y, bdeg in blocks:
        S.append(f'<rect class="house" x="-4.4" y="-3" width="8.8" height="6" transform="translate({x / U:.1f} {y / U:.1f}) rotate({bdeg:.1f})"/>')
    # site symbols; number badges dodge symbols and each other
    # site symbols; number badges dodge symbols and each other
    RAD = {"round": 20, "cothon": 34, "strait": 24, "citadel": 22, "cliff": 30, "port": 16, "harbour": 20, "hall": 12, "tower": 12, "fleet": 24, "redoubt": 18}
    marks = []
    for num, skey, name, vols, kind in site_list:
        if skey not in loc: continue
        pts = loc[skey] if isinstance(loc[skey], list) else [loc[skey]]
        marks += [(px / U, py / U, RAD.get(kind, 8) if k == 0 else 8, num) for k, (px, py) in enumerate(pts)]
    badges = []
    def badge_at(x, y, r0, num):
        """Nearest spot that clears every symbol and badge, and sits nearer its own site than any other."""
        best, best_key = None, None
        for dist in (r0 + 16, r0 + 28, r0 + 42, r0 + 58):
            for a in (-40, -140, 40, 140, -90, 90, 0, 180):
                bx, by = x + dist * math.cos(math.radians(a)), y + dist * math.sin(math.radians(a))
                if not (16 < bx < VW - 16 and 16 < by < VH - 16): continue
                gaps = [math.hypot(bx - mx, by - my) - mr - 15 for mx, my, mr, n in marks if n != num]
                gaps += [math.hypot(bx - qx, by - qy) - 30 for qx, qy in badges]
                own = min(math.hypot(bx - mx, by - my) - mr for mx, my, mr, n in marks if n == num)
                clear = min(gaps, default=99)
                if clear >= 2 and all(own < math.hypot(bx - mx, by - my) - mr for mx, my, mr, n in marks if n != num):
                    return bx, by
                if best_key is None or clear > best_key: best, best_key = (bx, by), clear
        return best
    for num, skey, name, vols, kind in site_list:
        if skey not in loc: continue
        pts = loc[skey] if isinstance(loc[skey], list) else [loc[skey]]
        cls = " ".join(f"v{v}" for v in vols.split())
        S.append(f'<g class="site {cls}" data-site="{num}">')
        x, y = pts[0][0] / U, pts[0][1] / U
        if kind == "round":
            S.append(f'<circle class="sym-round" cx="{x:.1f}" cy="{y:.1f}" r="16"/><circle class="sym-round-in" cx="{x:.1f}" cy="{y:.1f}" r="6.5"/>')
            for a in range(4):
                gx, gy = x + 16 * math.cos(a * math.pi / 2), y + 16 * math.sin(a * math.pi / 2)
                S.append(f'<rect class="sym-gate" x="{gx - 3.5:.1f}" y="{gy - 3.5:.1f}" width="7" height="7"/>')
        elif kind == "cothon":
            S.append(f'<circle class="sym-cothon" cx="{x:.1f}" cy="{y:.1f}" r="30"/><circle class="sym-cothon-isle" cx="{x:.1f}" cy="{y:.1f}" r="9"/>')
            for a in range(7):
                ang = a * math.tau / 7 - math.pi / 2
                q1x, q1y = x + 30 * math.cos(ang), y + 30 * math.sin(ang)
                q2x, q2y = x + 22 * math.cos(ang), y + 22 * math.sin(ang)
                S.append(f'<line class="sym-quay" x1="{q1x:.1f}" y1="{q1y:.1f}" x2="{q2x:.1f}" y2="{q2y:.1f}"/>')
                # Navigators' ship moored alongside each quay, bow pointed inward toward the lantern
                dx, dy = -math.cos(ang), -math.sin(ang)
                nx, ny = -math.sin(ang), math.cos(ang)
                sx, sy = x + 25.8 * math.cos(ang) + 2.0 * nx, y + 25.8 * math.sin(ang) + 2.0 * ny
                bx, by = sx + 2.8 * dx, sy + 2.8 * dy
                stx, sty = sx - 2.8 * dx, sy - 2.8 * dy
                p1x, p1y = sx + 0.4 * dx + 1.0 * nx, sy + 0.4 * dy + 1.0 * ny
                p2x, p2y = sx - 1.6 * dx + 0.7 * nx, sy - 1.6 * dy + 0.7 * ny
                s1x, s1y = sx + 0.4 * dx - 1.0 * nx, sy + 0.4 * dy - 1.0 * ny
                s2x, s2y = sx - 1.6 * dx - 0.7 * nx, sy - 1.6 * dy - 0.7 * ny
                d_ship = f"M{bx:.1f} {by:.1f} Q{p1x:.1f} {p1y:.1f} {p2x:.1f} {p2y:.1f} L{stx:.1f} {sty:.1f} L{s2x:.1f} {s2y:.1f} Q{s1x:.1f} {s1y:.1f} Z"
                S.append(f'<path class="sym-ship" d="{d_ship}"/>')
        elif kind == "fleet":
            # 4 defensive warships anchored in battle line with skiff tracks
            for k, (wx, wy) in enumerate(pts[:4]):
                px, py = wx / U, wy / U
                ang = math.radians(235)
                dx, dy = math.cos(ang), math.sin(ang)
                nx, ny = -math.sin(ang), math.cos(ang)
                bx, by = px + 6.0 * dx, py + 6.0 * dy
                stx, sty = px - 6.0 * dx, py - 6.0 * dy
                p1x, p1y = px + 1.0 * dx + 2.2 * nx, py + 1.0 * dy + 2.2 * ny
                p2x, p2y = px - 3.5 * dx + 1.6 * nx, py - 3.5 * dy + 1.6 * ny
                s1x, s1y = px + 1.0 * dx - 2.2 * nx, py + 1.0 * dy - 2.2 * ny
                s2x, s2y = px - 3.5 * dx - 1.6 * nx, py - 3.5 * dy - 1.6 * ny
                d_ship = f"M{bx:.1f} {by:.1f} Q{p1x:.1f} {p1y:.1f} {p2x:.1f} {p2y:.1f} L{stx:.1f} {sty:.1f} L{s2x:.1f} {s2y:.1f} Q{s1x:.1f} {s1y:.1f} Z"
                rx, ry = bx + 2.5 * dx, by + 2.5 * dy
                S.append(f'<path class="sym-ship" d="{d_ship}"/>'
                         f'<line class="sym-ship" x1="{bx:.1f}" y1="{by:.1f}" x2="{rx:.1f}" y2="{ry:.1f}"/>')
            if not clean and len(pts) >= 4:
                # Skiff routes between flagships
                for (a, b) in ((0, 1), (0, 2), (0, 3)):
                    p0 = (pts[a][0] / U, pts[a][1] / U)
                    p1 = (pts[b][0] / U, pts[b][1] / U)
                    S.append(f'<line class="sym-skiff-lane" x1="{p0[0]:.1f}" y1="{p0[1]:.1f}" x2="{p1[0]:.1f}" y2="{p1[1]:.1f}"/>')
        elif kind == "redoubt":
            S.append(f'<rect class="sym-hall" x="{x - 12:.1f}" y="{y - 9:.1f}" width="24" height="18" rx="2"/>'
                     f'<rect class="sym-bldg" x="{x - 14:.1f}" y="{y - 11:.1f}" width="6" height="6"/>'
                     f'<rect class="sym-bldg" x="{x + 8:.1f}" y="{y - 11:.1f}" width="6" height="6"/>'
                     f'<circle class="sym-tower-fire" cx="{x:.1f}" cy="{y:.1f}" r="2.2"/>')
        elif kind == "tower":
            for tx, ty in pts:
                px, py = tx / U, ty / U
                if clean:
                    S.append(f'<rect class="sym-bldg" x="{px - 4:.1f}" y="{py - 4:.1f}" width="8" height="8"/>')
                else:
                    S.append(f'<path class="sym-tower" d="M{px - 4.5:.1f} {py + 4.5:.1f}V{py - 2.5:.1f}H{px - 2.5:.1f}V{py - 4.5:.1f}H{px - 1:.1f}V{py - 2.5:.1f}H{px + 1:.1f}V{py - 4.5:.1f}H{px + 2.5:.1f}V{py - 2.5:.1f}H{px + 4.5:.1f}V{py + 4.5:.1f}Z"/>'
                             f'<circle class="sym-tower-fire" cx="{px:.1f}" cy="{py:.1f}" r="1.5"/>')
        elif kind == "citadel":
            S.append(f'<path class="sym-citadel" d="M{x - 18:.1f} {y + 11:.1f}L{x - 18:.1f} {y - 7:.1f}L{x - 10:.1f} {y - 13:.1f}L{x + 10:.1f} {y - 13:.1f}L{x + 18:.1f} {y - 7:.1f}L{x + 18:.1f} {y + 11:.1f}Z"/>')
        elif kind == "port":
            S.append(f'<path class="sym-port" d="M{x - 15:.1f} {y:.1f}H{x + 15:.1f}M{x - 10:.1f} {y:.1f}V{y - 10:.1f}M{x:.1f} {y:.1f}V{y - 10:.1f}M{x + 10:.1f} {y:.1f}V{y - 10:.1f}"/>')
        elif kind == "harbour":
            S.append(f'<path class="sym-mole" d="M{x - 18:.1f} {y + 4:.1f}A18 18 0 0 1 {x + 18:.1f} {y + 4:.1f}"/>')
        elif kind == "hall":
            S.append(f'<circle class="sym-hall" cx="{x:.1f}" cy="{y:.1f}" r="10"/><circle class="sym-round-in" cx="{x:.1f}" cy="{y:.1f}" r="4"/>')
        elif kind == "strait" and not clean:
            S.append(f'<circle class="sym-strait" cx="{x:.1f}" cy="{y:.1f}" r="22"/>')
        elif kind == "cliff":
            for k in range(-3, 4):
                S.append(f'<line class="sym-cliff" x1="{x + k * 9:.1f}" y1="{y - 9:.1f}" x2="{x + k * 9 + 4:.1f}" y2="{y + 9:.1f}"/>')
        if kind not in ("tower", "fleet"):
            for px, py in pts[(1 if kind in ("round", "cothon", "citadel", "strait", "cliff", "port", "harbour", "hall", "redoubt") else 0):]:
                if clean: S.append(f'<rect class="sym-bldg" x="{px / U - 4:.1f}" y="{py / U - 3:.1f}" width="8" height="6"/>')
                else: S.append(f'<circle class="sym-dot" cx="{px / U:.1f}" cy="{py / U:.1f}" r="7"/>')
        if not clean:
            bx, by = badge_at(pts[0][0] / U, pts[0][1] / U, RAD.get(kind, 8), num); badges.append((bx, by))
            S.append(f'<g class="tag"><circle class="num-bg" cx="{bx:.1f}" cy="{by:.1f}" r="15"/>'
                     f'<text class="num" x="{bx:.1f}" y="{by + 7:.1f}">{num}</text></g>')
        S.append('</g>')
    # compass + scale (1 km and 5 stadia at 185 m)
    if not clean: S.append(f'<g class="furniture"><g transform="translate({VW - 80:.0f} 90)"><path class="compass" d="M0 -38L9 6L0 0L-9 6Z"/>'
             '<text class="compass-n" x="0" y="-46">N</text></g>'
             f'<g transform="translate(60 {VH - 50:.0f})"><rect class="scale-bg" x="-14" y="-44" width="300" height="66" rx="3"/>'
             '<path class="scale" d="M0 0H200M0 -7V7M100 -5V5M200 -7V7"/>'
             '<text class="scale-t" x="0" y="-14">0</text><text class="scale-t" x="200" y="-14">1 km</text>'
             f'<path class="scale st" d="M0 10H{5 * 185 / U:.1f}"/><text class="scale-t sm" x="{5 * 185 / U + 8:.1f}" y="16">5 stadia</text></g></g>')
    S.append('</svg>')
    return "\n".join(S)

SVG_STYLE = """<style>
.sea0{fill:#8fbccd}.sea1{fill:#a9cdd8}.sea2{fill:#c3dde1}
.wline{fill:none;stroke:#136f9e;stroke-width:1}.wl0{opacity:.5}.wl1{opacity:.3}.wl2{opacity:.16}
.land0{fill:#eee0b0}.land1{fill:#e2d59b}.land2{fill:#cfcb8c}.land3{fill:#b6b87d}.land4{fill:#a0a670}.land5{fill:#bfae8f}.land6{fill:#ddd2c0}
.coast{stroke:#1c1512;stroke-width:2.2;stroke-linejoin:round}.contour{stroke:#1c1512;stroke-opacity:.22;stroke-width:.8}
.road{fill:none;stroke-linecap:round;stroke-linejoin:round}.walk{stroke:#faf3e0;stroke-width:5}.walk-dots{stroke:#1c1512;stroke-width:4.2;stroke-dasharray:0 9}
.track{stroke:#6b5a43;stroke-width:1.4;stroke-dasharray:5 4}
.house{fill:#bf4a26;stroke:#1c1512;stroke-width:.6}.agora{fill:#faf3e0;stroke:#1c1512;stroke-width:.8}
.sym-round{fill:#f8f5ee;stroke:#1c1512;stroke-width:2.4}.sym-round-in{fill:#e2cf9b;stroke:#1c1512;stroke-width:1}.sym-gate{fill:#c1912b;stroke:#1c1512;stroke-width:1}
.sym-cothon{fill:#7fb2c8;stroke:#1c1512;stroke-width:2.2}.sym-cothon-isle{fill:#f8f5ee;stroke:#1c1512;stroke-width:1.4}.sym-quay{stroke:#1c1512;stroke-width:2}
.sym-citadel{fill:#8e2323;stroke:#1c1512;stroke-width:1.6}.sym-strait{fill:none;stroke:#8e2323;stroke-width:2.2;stroke-dasharray:4 3}
.sym-cliff{stroke:#1c1512;stroke-width:2}.sym-port{fill:none;stroke:#1c1512;stroke-width:3.2;stroke-linecap:round}.sym-mole{fill:none;stroke:#1c1512;stroke-width:5;stroke-linecap:round}.sym-hall{fill:#f8f5ee;stroke:#1c1512;stroke-width:2.2}.sym-bldg{fill:#bf4a26;stroke:#1c1512;stroke-width:.8}.sym-dot{fill:#1c1512;stroke:#faf3e0;stroke-width:1.5}
.sym-tower{fill:#1c1512;stroke:#faf3e0;stroke-width:1}.sym-tower-fire{fill:#e2822a}.sym-ship{fill:#1c1512;stroke:#faf3e0;stroke-width:.8}.sym-skiff-lane{fill:none;stroke:#136f9e;stroke-width:1;stroke-dasharray:3 3;opacity:.65}
.zone{fill:#1c1512;fill-opacity:.2;font:700 italic 74px Optima,'Gill Sans',sans-serif;text-anchor:middle;dominant-baseline:middle}.num-bg{fill:#1c1512}.num{fill:#ffe36e;font:700 19px Optima,'Gill Sans',sans-serif;text-anchor:middle}
.compass{fill:#1c1512}.compass-n,.scale-t{fill:#1c1512;font:700 22px Optima,'Gill Sans',sans-serif;text-anchor:middle}.scale-t.sm{font-size:17px;text-anchor:start;font-weight:400}
.scale-bg{fill:#faf3e0;fill-opacity:.85;stroke:#1c1512;stroke-width:1}.scale{fill:none;stroke:#1c1512;stroke-width:2}.scale.st{stroke-width:4;stroke:#bf4a26}
</style>"""

PAGE = ROOT / "art-direction-grand-island-shape.html"
VOL_TITLES = {1: "The Disordered Sundials", 2: "The Curse of the Sleeping Guard", 3: "Traitors Among Admirals",
              4: "The Passable Season", 5: "The Part-time Parliament", 6: "The Ledger of Many Decrees",
              7: "The Citadel of Iron Quorums", 8: "The Quarries of the Roman Guilds", 9: "The Reformation of the Raft Monks"}

def order_table(order, axis):
    """The walk as a table: each volume's stretch of the axis and what it builds on."""
    (x0, y0), (x1, y1) = axis
    km = math.hypot(x1 - x0, y1 - y0) / 1000
    band = {v: k + 1 for k, g in enumerate(BANDS) for v in g}
    rows = []
    for v in (v for g in BANDS for v in g):
        lo, hi = order["spans"][VOL_ROMAN[v]]
        parents = [VOL_ROMAN[a] for a, b in DEPENDS if b == v]
        rows.append(f'<tr><td class="n">{band[v]}</td><td class="n">{VOL_ROMAN[v]}</td><td>{VOL_TITLES[v]}</td>'
                    f'<td>{", ".join(parents) or "nothing (a root)"}</td><td class="n">{lo * km:.1f}–{hi * km:.1f} km</td></tr>')
    ok = "✓ all nine links hold" if order["edges_ok"] else "✗ broken: " + ", ".join(order["broken_edges"])
    return ('<div class="tbl"><table><thead><tr><th>Phase</th><th>Vol</th><th>Title</th><th>Builds on</th><th>Along the walk</th></tr></thead><tbody>'
            + "".join(rows) + f'</tbody></table></div><p class="muted">Measured from the north-west tip along the island\'s axis. {ok}; '
            + ("the bands don't overlap." if order["bands_ok"] else "the bands overlap.") + '</p>')

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    html = PAGE.read_text() if PAGE.exists() else None
    h, loc, rules = build()
    report = {}
    for num, skey, name, vols, kind in SITES:
        if skey not in loc: continue
        v = loc[skey]
        pts = v if isinstance(v, list) else [v]
        report[skey] = {"num": num, "name": name, "volumes": [VOL_ROMAN[int(x)] for x in vols.split()],
                        "points_m": [[round(px), round(py), round(h_at(h, px, py), 1)] for px, py in pts]}
    svg = svg_for(TITLE, h, SITES, loc, rules.get("zones", ()))
    (OUT / "island.svg").write_text(svg.replace(">", ">" + SVG_STYLE, 1))
    ref = svg_for(TITLE, h, SITES, loc, clean=True)                              # stage 2 layout reference, see tools/paint_reference.py
    (OUT / "island-reference.svg").write_text(ref.replace(">", ">" + SVG_STYLE, 1))
    png = np.clip((h - HMIN) / (HMAX - HMIN), 0, 1) * 65535
    Image.fromarray(png.astype(np.uint16)).save(OUT / "island-height.png")
    land = (h > 0).mean() * W * H / 1e6
    ck = checks(h, loc, rules)
    print(f"    checks: hamlets seen {ck['hamlets_mutually_visible'] or 'none'} | banquet {ck['banquet_visible_from_round']}"
          f" | sea from Round {ck['round_sea_bearings']}° two-sided {ck['round_sea_two_sided']} {ck['round_sea_arcs']} | signals {ck['signal_pairs_clear']}"
          f" | harbour seen {ck['town_to_round_clear']} | walk {math.dist(loc['town'], loc['round']):.0f} m"
          f" | saddle {ck['round_in_saddle']} | banquet offset {ck['banquet_offset_m']} | causeway {ck.get('causeway')}"
          f" | order {ck.get('dependency_order')} | IX detached {ck.get('monastery_detached')}")
    agora, blocks = town_layout(h, loc)
    built = {"cothon": {"centre_m": [round(v) for v in loc["cothon"]], "basin_radius_m": 150, "islet_radius_m": 45,
                        "channel_bearing_deg_from_x_toward_y": round(rules["cothon_channel_deg"], 1)},
             "town": {"agora_m_deg": [round(agora[0]), round(agora[1]), round(agora[2], 1)], "insula_m": [44, 30],
                      "insulae_m_deg": [[round(x), round(y), round(d, 1)] for x, y, d in blocks]},
             "statue_walk_m": [[round(x), round(y)] for x, y in loc["_tracks"][1]],
             "tracks_m": [{"from": a, "to": b, "path": [[round(x), round(y)] for x, y in path]} for a, b, path in loc["_tracks"][0]]}
    meta = {"title": TITLE, "world_m": [W, H], "cell_m": CELL, "built": built,
            "height_png_range_m": [HMIN, HMAX], "land_km2": round(land, 2),
            "summit_m": round(float(h.max())), "checks": ck, "sites": report}
    (OUT / "island-sites.json").write_text(json.dumps(meta, indent=1))
    print(f"{TITLE}: land {land:.1f} km², summit {h.max():.0f} m")
    for skey, r in report.items():
        print(f"    {r['num']:>2} {skey:9s}", " ".join(f"{p[2]:>6.1f}" for p in r["points_m"]))
    if html:
        rp, tp, bp = (report[k_]["points_m"][0] for k_ in ("round", "town", "banquet"))
        cw = ck.get("causeway")
        rows = [("Sea on both sides of the Round", ck["round_sea_two_sided"]),
                ("Harbour in view from the Round", ck["town_to_round_clear"]),
                ("Banquet house in view from the tiers", ck["banquet_visible_from_round"]),
                ("Hamlets out of each other's sight", not ck["hamlets_mutually_visible"]),
                ("Beacons in sight across the water" if ck["signal_pairs_clear"][1] == 1 else "Beacon and drum pairs in sight across the water",
                 ck["signal_pairs_clear"][0] == ck["signal_pairs_clear"][1]),
                ("The Round sits in a saddle", ck["round_in_saddle"]),
                (f"The Round clear of the town (≥{ROUND_TOWN_MIN:.0f} m)", ck["round_town_m"] >= ROUND_TOWN_MIN),
                ("Banquet house due east (±60 m)", ck["banquet_offset_m"][0] >= 120 and abs(ck["banquet_offset_m"][1]) <= 60)]
        if "dependency_order" in ck:
            rows += [("Each volume after the ones it builds on (9 links)", ck["dependency_order"]["edges_ok"]),
                     ("The graph's five bands run NW → SE without overlapping", ck["dependency_order"]["bands_ok"])]
        if "monastery_detached" in ck: rows += [("Raft monastery on its own island", ck["monastery_detached"])]
        rows += [("The agora stands wholly on dry land", ck["agora_on_dry_land"]),
                 ("The causeway joins the neck in calm weather", ck["causeway_joins_the_neck"]),
                 ("The lantern harbour's basin opens to the sea", ck["cothon_open_to_sea"]),
                 ("Tracks connect every mainland site", ck["tracks_connect_every_mainland_site"]),
                 ("No track runs straight from one hamlet to another", not ck["tracks_hamlet_to_hamlet"])]
        if cw: rows += [("Causeway dry in calm weather", cw["dry_in_calm"]),
                        ("Winter seas break over it (crest ≤ 3 m)", cw["winter_seas_break_over"])]
        stats = (f'<dl class="stats"><div><dt>Land</dt><dd>{land:.1f} km²</dd></div>'
                 f'<div><dt>Summit</dt><dd>{h.max():.0f} m</dd></div>'
                 f'<div><dt>The Round sits at</dt><dd>{rp[2]:.0f} m</dd></div>'
                 f'<div><dt>Harbour → Round</dt><dd>{math.dist(tp[:2], rp[:2]) / 1000:.2f} km, {rp[2] - tp[2]:.0f} m climb</dd></div>'
                 f'<div><dt>Banquet house</dt><dd>{ck["banquet_offset_m"][0]} m east, {abs(ck["banquet_offset_m"][1])} m {"south" if ck["banquet_offset_m"][1] > 0 else "north"}, {rp[2] - bp[2]:.0f} m below</dd></div>'
                 f'<div><dt>Sea seen from the Round</dt><dd>{ck["round_sea_bearings"]}° of horizon</dd></div>'
                 + (f'<div><dt>Causeway</dt><dd>{cw["length_m"]} m long, crest {cw["crest_min_m"]}–{cw["crest_max_m"]} m, ~{cw["width_above_1_5m_mean"]} m wide above 1.5 m</dd></div>' if cw else "")
                 + "".join(f'<div class="ck {"pass" if ok else "fail"}"><dt>{label}</dt><dd>{"✓ yes" if ok else "✗ no"}</dd></div>'
                           for label, ok in rows)
                 + '</dl>')
        blocks = [("MAP", svg), ("STATS", stats)]
        if "dependency_order" in ck: blocks.append(("ORDER", order_table(ck["dependency_order"], rules["axis"])))
        for tag, body in blocks:
            html = re.sub(rf"(<!-- {tag} -->).*?(<!-- /{tag} -->)",
                          lambda mo: mo.group(1) + "\n" + body + "\n" + mo.group(2), html, flags=re.S)
        PAGE.write_text(html)

if __name__ == "__main__":
    main()
