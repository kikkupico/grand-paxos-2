"""The remaining sites, built on the terrain after the key buildings (called from blender_buildings.main):
hamlets, olive press and beacon towers (I); the four coastal watchtowers (II); the drummers'
posts and causeway markers (III); the Statue Walk (IV); the granary storehouses (VI); the guild hall,
lock-houses and ledger-cliff quarry (VIII); and the Raft monastery with its jetty (IX).

Each builder returns a Kit plus whatever the checks need. The checks use real sightlines through the terrain
mesh (ray casts), not the 2D map: hamlet rooftops must be hidden from each other, beacon fires and drum
platforms must see each other.
"""
import math, random
import numpy as np
from mathutils import Vector
from blender_kit import *                                                                          # noqa: F401,F403
import blender_arch as ba

def extra_mats():
    return {"fieldstone": mat("Fieldstone", "#b3a486"), "thatch": mat("Thatch", "#a08a5a"), "fire": mat("Beacon fire", "#ff8a3c", .5, 0, "#ff7a2a"),
            "white_fire": mat("White signal fire", "#fff7ea", .2, 0, "#ffffff"), "smoke": mat("Dark smoke", "#322e2a", .9),
            "lamp_flame": mat("Lamp flame", "#ffd060", .2, 0, "#ff9920"),
            "rock": mat("Rock outcrop", "#9c927f"), "cave": mat("Cave dark", "#1b1714", 1.0), "hide": mat("Drum hide", "#caa66b")}

def statue(k, M, X, Y, z, ang):
    k.box(X, Y, z - .5, z + 1.3, 1.1, 1.1, ang, M["marble"])
    k.cyl(X, Y, .32, z + 1.3, z + 3.0, M["marble"], 8)
    k.box(X, Y, z + 3.0, z + 3.45, .45, .45, ang, M["marble"])

def contour_angle(ground, X, Y, r=25):
    """Direction along the slope's contour, so long buildings lie across the hill, not down it."""
    gx = ground.z(X + r, Y) - ground.z(X - r, Y); gy = ground.z(X, Y + r) - ground.z(X, Y - r)
    return math.atan2(gx, -gy) if abs(gx) + abs(gy) > .5 else 0.0

def clear_sight(terrain, p, q, extra=()):
    """True if nothing on the terrain mesh (or the `extra` objects) blocks the straight line from p to q (Blender coordinates)."""
    p, q = Vector(p), Vector(q); d = q - p; L = d.length
    return not any(ob.ray_cast(p, d.normalized(), distance=max(L - 2.0, 0.0))[0] for ob in (terrain, *extra))

# ---------------------------------------------------------------- I · Disordered Sundials
def hamlet(ground, M, key, label, seed):
    X, Y = site(key); g = ground.z(X, Y); rnd = random.Random(seed)
    ground.pad(X, Y, 9, g, 12)
    k = Kit(f"I · {label}")
    k.cyl(X, Y, 7, g - 1, g + .15, M["pave"], 24)                                                  # threshing floor
    k.cyl(X + 6.2, Y, .3, g, g + 1.8, M["marble"], 8); k.cyl(X + 6.2, Y, .55, g + 1.8, g + 1.9, M["marble"], 16)   # the hamlet's own sundial
    top = g
    for i in range(6):
        a = i * TAU / 6 + rnd.uniform(-.3, .3); r = rnd.uniform(16, 28)
        hx, hy = X + r * math.cos(a), Y + r * math.sin(a)
        sx, sy, h = rnd.uniform(7, 10), rnd.uniform(5, 7), rnd.uniform(3.5, 4.5)
        house(k, ground, hx, hy, sx, sy, h, a + math.pi / 2, M["fieldstone"], M["roof"])
        top = max(top, on_ground(ground, hx, hy, sx, sy, a)[1] + h + 1.5)
    px, py = X - 36, Y + 8
    k.ring(px, py, 8, 8.6, ground.z(px, py) - 1, ground.z(px, py) + 1.2, M["fieldstone"], 32, .5, TAU - .2)   # animal pen
    return k, (X, Y, top)

def olive_press(ground, M):
    X, Y = site("press"); g = ground.z(X, Y); ang = contour_angle(ground, X, Y)
    ground.pad(X, Y, 16, g, 18)
    k = Kit("I · Olive press")
    k.cyl(X, Y, 14, g - 1, g + .15, M["pave"], 32)
    house(k, ground, X - 6 * math.cos(ang), Y - 6 * math.sin(ang), 16, 10, 5, ang, M["fieldstone"], M["roof"])
    c, s = math.cos(ang + math.pi / 2), math.sin(ang + math.pi / 2)
    tx, ty = X + 9 * c, Y + 9 * s                                                                   # the crushing basin in the yard
    k.cyl(tx, ty, 2.3, g, g + 1.0, M["limestone"], 24); k.cyl(tx, ty, .35, g + 1.0, g + 2.2, M["timber"], 8)
    for side in (-1, 1): k.box(tx + side * .9 * math.cos(ang), ty + side * .9 * math.sin(ang), g + 1.0, g + 2.4, .6, 1.3, ang, M["limestone"])
    house(k, ground, X + 6 * math.cos(ang) - 8 * c, Y + 6 * math.sin(ang) - 8 * s, 10, 6, 3.5, ang, M["fieldstone"], M["roof"])
    return k

def beacon_towers(ground, M):
    k = Kit("I · Beacon towers"); fires = []
    for i in range(2):
        X, Y = site("beacons", i); g = ground.z(X, Y)
        k.box(X, Y, g - 2, g + 11, 6, 6, 0, M["fieldstone"])
        k.ring(X, Y, 2.6, 3.4, g + 11, g + 12.2, M["fieldstone"], 4, math.pi / 4, math.pi / 4 + TAU)
        k.cyl(X, Y, 1.4, g + 11, g + 12.2, M["fire"], 12)
        fires.append((X, Y, g + 13))
    return k, fires

# ---------------------------------------------------------------- II · The Curse of the Sleeping Guard
WATCHTOWER_DETAIL = {}
def watchtowers(ground, M):
    k = Kit("II · Coastal watchtowers")
    # Four coastal watchtowers:
    # 0: North Bluff, 1: East Cape, 2: South Crag (sleeping guard), 3: West Point
    for i in range(4):
        X, Y = site("watchtowers", i); g = ground.z(X, Y)
        ground.pad(X, Y, 10, g, 14)
        inland = ground.seaward(X, Y, radius=500)
        inland_ang = math.atan2(-inland[1], -inland[0])                # opposite to seaward (inland approach)
        dx, dy = math.cos(inland_ang), math.sin(inland_ang)
        c, s = dx, dy

        # 1. Flagstone base terrace & plinth
        k.cyl(X, Y, 6.8, g - 1.0, g + 0.35, M["pave"], 24)
        k.ring(X, Y, 6.5, 7.1, g - 1.0, g + 0.5, M["limestone"], 24)
        # Approach steps facing inland
        k.box(X + 5.8 * dx, Y + 5.8 * dy, g - 0.5, g + 0.18, 1.2, 2.2, inland_ang, M["limestone"])
        k.box(X + 4.9 * dx, Y + 4.9 * dy, g - 0.2, g + 0.35, 1.0, 1.8, inland_ang, M["limestone"])

        # 2. Hollow walls with open doorway facing inland
        w_door = 1.6
        half_ang = (w_door / 2.0) / 4.4
        a_start = inland_ang + half_ang
        a_end = inland_ang + TAU - half_ang

        # Plinth batter and ground-level wall with open doorway
        k.ring(X, Y, 3.4, 4.8, g + 0.35, g + 2.0, M["limestone"], 24, a0=a_start, a1=a_end)
        k.ring(X, Y, 3.4, 4.4, g + 2.0, g + 2.5, M["ashlar"], 24, a0=a_start, a1=a_end)
        # Upper continuous wall above doorway
        k.ring(X, Y, 3.4, 4.4, g + 2.5, g + 9.8, M["ashlar"], 24)

        # Horizontal stone string courses
        k.ring(X, Y, 4.38, 4.54, g + 3.8, g + 4.05, M["limestone"], 24)
        k.ring(X, Y, 4.38, 4.54, g + 7.2, g + 7.45, M["limestone"], 24)

        # 3. Interior stone floor & ceiling trapdoor deck
        k.cyl(X, Y, 3.4, g, g + 0.35, M["pave"], 20)
        k.cyl(X, Y, 2.0, g + 9.8, g + 10.0, M["timber"], 16)

        # 4. Flared machicolation corbels supporting projecting parapet
        for c_idx in range(16):
            ca = c_idx * TAU / 16
            cx, cy = math.cos(ca), math.sin(ca)
            k.box(X + 4.35 * cx, Y + 4.35 * cy, g + 9.3, g + 9.9, 0.35, 0.45, ca, M["limestone"])
            k.box(X + 4.5 * cx, Y + 4.5 * cy, g + 9.6, g + 9.9, 0.35, 0.45, ca, M["limestone"])
        # Cornice ring under parapet
        k.ring(X, Y, 3.3, 4.8, g + 9.8, g + 10.2, M["limestone"], 24)

        # 5. Parapet wall-walk and crenellated battlements
        k.ring(X, Y, 2.0, 3.4, g + 10.0, g + 10.2, M["pave"], 20)     # wall-walk floor
        k.ring(X, Y, 3.3, 4.8, g + 10.2, g + 11.0, M["limestone"], 24) # parapet lower breastwork
        # 8 crenellations (merlons rising 2.0 m above wall-walk deck)
        for m in range(8):
            a0 = m * TAU / 8
            a1 = a0 + TAU / 16
            k.ring(X, Y, 3.3, 4.8, g + 11.0, g + 12.2, M["limestone"], 4, a0, a1)
            k.ring(X, Y, 3.25, 4.85, g + 12.15, g + 12.3, M["marble"], 4, a0, a1)

        # 6. Framed doorway (facing inland toward the courier track)
        jamb_r = 4.1
        k.box(X + jamb_r * c - 0.95 * s, Y + jamb_r * s + 0.95 * c, g + 0.35, g + 2.55, 1.2, 0.5, inland_ang, M["limestone"])
        k.box(X + jamb_r * c + 0.95 * s, Y + jamb_r * s - 0.95 * c, g + 0.35, g + 2.55, 1.2, 0.5, inland_ang, M["limestone"])
        k.box(X + jamb_r * c, Y + jamb_r * s, g + 2.45, g + 2.8, 1.4, 2.4, inland_ang, M["limestone"])

        # 7. Arrow slits (seaward and flanking angles)
        for sa in (inland_ang + math.pi - 0.75, inland_ang + math.pi, inland_ang + math.pi + 0.75):
            sx, sy = math.cos(sa), math.sin(sa)
            k.box(X + 4.38 * sx, Y + 4.38 * sy, g + 4.2, g + 5.4, 0.25, 0.32, sa, M["cave"])
            k.box(X + 4.38 * sx, Y + 4.38 * sy, g + 7.6, g + 8.8, 0.25, 0.32, sa, M["cave"])

        # 8. Parapet bronze tripod braziers
        for ba_ang in (0, TAU / 3, 2 * TAU / 3):
            bx = math.cos(ba_ang); by = math.sin(ba_ang)
            k.box(X + 0.8 * bx, Y + 0.8 * by, g + 10.2, g + 11.2, 0.12, 0.15, ba_ang, M["iron"])
        k.frustum(X, Y, 0.8, 1.45, g + 11.0, g + 11.6, M["bronze"], 16)
        k.ring(X, Y, 1.3, 1.55, g + 11.55, g + 11.75, M["bronze"], 16)

        if i in (0, 1):
            # Towers 0 & 1 (North Bluff & East Cape): brilliant white signal flame (ATTACK)
            k.cyl(X, Y, 1.1, g + 11.6, g + 12.8, M["white_fire"], 12)
            k.frustum(X, Y, 1.0, 0.2, g + 12.6, g + 13.8, M["white_fire"], 8)
        elif i == 2:
            # Tower 2 (South Crag): the sleeping guard's tower — cold unlit embers, brand unlit
            k.cyl(X, Y, 1.2, g + 11.55, g + 11.7, M["rock"], 12)
            k.box(X + 0.2, Y + 0.3, g + 11.7, g + 11.82, 0.12, 1.1, 0.7, M["timber"])
        elif i == 3:
            # Tower 3 (West Point): smouldering black pine-smoke brazier (DEFEND)
            k.cyl(X, Y, 1.1, g + 11.55, g + 11.8, M["roof"], 12)
            k.frustum(X, Y, 0.9, 0.3, g + 11.75, g + 12.7, M["smoke"], 8)

        # 9. War-horn post on parapet
        px, py = X + 3.9 * math.cos(inland_ang + 1.2), Y + 3.9 * math.sin(inland_ang + 1.2)
        k.box(px, py, g + 10.2, g + 12.6, 0.25, 0.25, 0, M["timber"])
        k.frustum(px, py, 0.08, 0.32, g + 12.3, g + 13.0, M["bronze"], 8)

        # 10. South Crag specific interior: the sleeping guard at his table
        if i == 2:
            # Slate-table with legs
            k.box(X + 1.2 * dx, Y + 1.2 * dy, g + 0.35, g + 1.15, 0.8, 1.3, inland_ang, M["timber"])
            for lx, ly in ((-0.35, -0.55), (-0.35, 0.55), (0.35, -0.55), (0.35, 0.55)):
                k.box(X + 1.2 * dx + lx * c - ly * s, Y + 1.2 * dy + lx * s + ly * c, g + 0.35, g + 1.05, 0.1, 0.1, inland_ang, M["timber"])
            # Wooden guard bench
            k.box(X + 0.35 * dx, Y + 0.35 * dy, g + 0.35, g + 0.8, 0.45, 0.7, inland_ang, M["timber"])
            # Wax slates & bronze stylus on the table
            k.box(X + 1.3 * dx + 0.3 * dy, Y + 1.3 * dy - 0.3 * dx, g + 1.15, g + 1.18, 0.28, 0.4, inland_ang + 0.2, M["thatch"])
            k.box(X + 1.1 * dx - 0.35 * dy, Y + 1.1 * dy + 0.35 * dx, g + 1.15, g + 1.18, 0.26, 0.38, inland_ang - 0.3, M["thatch"])
            k.box(X + 1.2 * dx - 0.1 * dy, Y + 1.2 * dy + 0.1 * dx, g + 1.18, g + 1.2, 0.04, 0.25, inland_ang + 0.5, M["bronze"])
            # Bronze oil lamp on the corner of the table with glowing flame
            k.cyl(X + 1.45 * dx + 0.45 * dy, Y + 1.45 * dy - 0.45 * dx, 0.12, g + 1.15, g + 1.25, M["bronze"], 8)
            k.cyl(X + 1.45 * dx + 0.45 * dy, Y + 1.45 * dy - 0.45 * dx, 0.04, g + 1.25, g + 1.33, M["lamp_flame"], 8)
            # The Sleeping Guard: slumped face-down over the slate-table
            k.box(X + 0.75 * dx, Y + 0.75 * dy, g + 0.85, g + 1.45, 0.45, 0.55, inland_ang, M["roof"]) # torso
            k.box(X + 1.05 * dx, Y + 1.05 * dy, g + 1.15, g + 1.28, 0.35, 0.6, inland_ang, M["roof"])  # folded arms
            k.box(X + 1.05 * dx, Y + 1.05 * dy, g + 1.28, g + 1.5, 0.25, 0.25, inland_ang, M["sand"])  # head face-down
            k.cyl(X + 0.9 * dx - 0.45 * dy, Y + 0.9 * dy + 0.45 * dx, 0.2, g + 1.15, g + 1.35, M["bronze"], 10) # helmet
            # Wall ladder to parapet trapdoor
            k.box(X - 2.8 * dy, Y + 2.8 * dx, g + 0.35, g + 10.2, 0.2, 0.6, inland_ang + math.pi / 2, M["timber"])
            # Unlit torch in iron wall bracket
            k.box(X + 4.1 * dx + 1.1 * dy, Y + 4.1 * dy - 1.1 * dx, g + 1.5, g + 2.3, 0.08, 0.08, inland_ang, M["timber"])
            k.box(X + 4.1 * dx + 1.1 * dy, Y + 4.1 * dy - 1.1 * dx, g + 2.2, g + 2.45, 0.14, 0.14, inland_ang, M["roof"])
            # Clifftop trail cairn outside
            k.cyl(X + 6.8 * dx + 3.0 * dy, Y + 6.8 * dy - 3.0 * dx, 0.7, g, g + 1.2, M["fieldstone"], 8)
            k.cyl(X + 6.8 * dx + 3.0 * dy, Y + 6.8 * dy - 3.0 * dx, 0.4, g + 1.2, g + 1.8, M["fieldstone"], 6)

    WATCHTOWER_DETAIL.update({
        "towers": 4,
        "merlon_h_m": 2.0,
        "crenel_w_m": 0.8,
        "wall_walk_w_m": 1.4,
        "door_h_m": 2.2,
        "arrow_slit_h_m": 1.2,
        "tower_h_m": 12.0,
    })
    return k

# ---------------------------------------------------------------- IV · Passable Season
def drummers(ground, M):
    k = Kit("IV · Drummers' posts"); decks = []
    for i in range(2):
        X, Y = site("drummers", i); g = ground.z(X, Y)
        k.cyl(X - 6, Y, 3, g - 1, g + 3, M["fieldstone"], 16); k.cone(X - 6, Y, 3.6, g + 3, g + 6, M["thatch"], 16)
        for dx in (-1.8, 1.8):
            for dy in (-1.8, 1.8): k.box(X + 2 + dx, Y + dy, g - 1, g + 3.5, .4, .4, 0, M["timber"])
        k.box(X + 2, Y, g + 3.5, g + 3.8, 4.6, 4.6, 0, M["timber"])
        k.cyl(X + 2, Y, .95, g + 3.8, g + 4.9, M["hide"], 16)
        decks.append((X + 2, Y, g + 5.5))
    return k, decks

def causeway_markers(ground, M):
    X, Y = site("strait"); k = Kit("IV · Causeway marker posts")
    c, r = ground._cr(X, Y); R = 36
    r0, c0 = max(int(r) - R, 0), max(int(c) - R, 0)
    win = ground.orig[r0:int(r) + R, c0:int(c) + R]
    rows, cols = np.nonzero((win > 0) & (win < 3.5))
    pts = np.stack([(cols + c0 + .5) * bt.CELL - bt.W / 2, bt.H / 2 - (rows + r0 + .5) * bt.CELL], 1)
    if len(pts) < 4: return k, 0
    ctr = pts.mean(0); u = np.linalg.svd(pts - ctr, full_matrices=False)[2][0]
    t = (pts - ctr) @ u; n = 0
    for tt in np.arange(t.min(), t.max(), 40):
        near = pts[np.abs(t - tt) < 15]
        if not len(near): continue
        px, py = near.mean(0); z = ground.z(px, py)
        if z <= 0: continue
        k.cyl(px, py, .25, z - 1, z + 3, M["timber"], 8); n += 1
    return k, n

# ---------------------------------------------------------------- V · Statue Walk
def smooth_path(pts, rounds=3, step=12.0):
    """Chaikin-smooth the 25 m grid path (as the 2D map does), then resample it every `step` metres."""
    p = np.array(pts, float)
    for _ in range(rounds):
        q = [p[0]]
        for a, b in zip(p, p[1:]): q += [.75 * a + .25 * b, .25 * a + .75 * b]
        p = np.array(q + [p[-1]])
    seg = np.hypot(*np.diff(p, axis=0).T); t = np.concatenate([[0], np.cumsum(seg)])
    ts = np.arange(0, t[-1], step)
    return list(zip(np.interp(ts, t, p[:, 0]), np.interp(ts, t, p[:, 1]))) + [tuple(p[-1])]

def seg_dist(c, p, q):
    (px, py), (qx, qy) = p, q; dx, dy = qx - px, qy - py
    t = max(0.0, min(1.0, ((c[0] - px) * dx + (c[1] - py) * dy) / max(dx * dx + dy * dy, 1e-9)))
    return math.hypot(px + t * dx - c[0], py + t * dy - c[1])

WALK_CUT_R, WALK_END_R = 85.0, 35.25                                                               # the kerb of the Round's terrace is at 34.5 m

def walk_route():
    """The Statue Walk as a Blender-space polyline, and the bearing of the Round's gate it ends at. The map's route runs
    on to the Round's centre and doubles back on itself near it, so it is cut where it first comes within WALK_CUT_R
    and eased onto the nearest gate's axis, ending at the terrace kerb. (Dropping the points inside the terrace left
    one paving slab laid straight across the bowl.)"""
    path = smooth_path([B(x, y) for x, y in SITES["built"]["statue_walk_m"]], rounds=2)
    RX, RY = site("round")
    cut = next(i for i, p in enumerate(path) if math.dist(p, (RX, RY)) <= WALK_CUT_R)
    T = path[cut]
    gate = round(math.atan2(T[1] - RY, T[0] - RX) / (TAU / 4)) * TAU / 4 % TAU
    u = (math.cos(gate), math.sin(gate))
    C, E = (RX + u[0] * 58, RY + u[1] * 58), (RX + u[0] * WALK_END_R, RY + u[1] * WALK_END_R)   # arrive along the gate axis
    n = max(2, math.ceil((math.dist(T, C) + math.dist(C, E)) / 12))
    tail = [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * c + t * t * e for a, c, e in zip(T, C, E)) for t in np.linspace(0, 1, n + 1)[1:]]
    return path[:cut + 1] + tail, gate

def statue_walk(ground, M, agora, window=9, gate_z=None):
    """The processional way: the route smoothed, a road bed graded as a running average of the ground along it
    (the terrain is cut and filled to meet it), paved, with statues every ~45 m once clear of the town. It ends
    outside the Round, at the terrace kerb before a gate."""
    path, gate = walk_route()
    RX, RY = site("round")
    raw = np.array([ground.z(x, y) for x, y in path])
    pad_ = np.pad(raw, window // 2, mode="edge")
    bed = np.convolve(pad_, np.ones(window) / window, mode="valid")
    bed[0], bed[-1] = raw[0], raw[-1]
    if gate_z is not None:                                                                          # a landing level with the Round's gate threshold, ramped over the last 200 m:
        to_end = np.concatenate([np.cumsum([math.dist(p, q) for p, q in zip(path, path[1:])][::-1])[::-1], [0.0]])   # the running average had cut 4 m below the east gate
        w = np.array([1 - float(smooth(d / 200)) for d in to_end])
        bed = bed * (1 - w) + gate_z * w
    for (x, y), z in zip(path, bed):                                                               # cut and fill a 6 m bed, feathered 10 m
        ground.edit(x, y, 16, lambda d, dX, dY, g, z=z: np.where(d < 16, g + (z - g) * (1 - smooth((d - 6) / 10)), g))
    k = Kit("V · The Statue Walk")
    length, grades, statues, since, side = 0.0, [], 0, 0.0, 1
    for i in range(len(path) - 1):
        (x0, y0), (x1, y1) = path[i], path[i + 1]
        L = math.hypot(x1 - x0, y1 - y0)
        if L < .1: continue
        z0, z1 = bed[i], bed[i + 1]; ang = math.atan2(y1 - y0, x1 - x0)
        k.box((x0 + x1) / 2, (y0 + y1) / 2, min(z0, z1) - .6, max(z0, z1) + .2, L + 1.5, 5, ang, M["pave"])
        length += L; grades.append(abs(z1 - z0) / L); since += L
        if since >= 45 and math.hypot(x1 - agora[0], y1 - agora[1]) > 320 and math.dist((x1, y1), (RX, RY)) > 50:   # the Round's forecourt has its own statues
            nx, ny = -math.sin(ang) * side, math.cos(ang) * side
            statue(k, M, x1 + nx * 5, y1 + ny * 5, ground.z(x1 + nx * 5, y1 + ny * 5), ang); statues += 1
            since, side = 0.0, -side
    raw_grades = [abs(b_ - a_) / max(math.dist(p, q), .1) for a_, b_, p, q in zip(raw, raw[1:], path, path[1:])]
    steep = path[int(np.argmax(grades))]
    return k, {"length_m": round(length), "max_grade_pct": round(100 * max(grades), 1), "steepest_from_round_m": round(math.dist(steep, (RX, RY))), "mean_grade_pct": round(100 * float(np.mean(grades)), 1),
               "max_grade_ungraded_pct": round(100 * max(raw_grades), 1), "statues": statues,
               "closest_to_round_m": round(min(seg_dist((RX, RY), p, q) for p, q in zip(path, path[1:])), 2),   # segments, not points: a slab spans each one
               "ends_before_gate_deg": round(math.degrees(gate)), "end_from_round_m": round(math.dist(path[-1], (RX, RY)), 2)}


# ---------------------------------------------------------------- VI · Ledger of Many Decrees
def storehouse(k, ground, M, X, Y, length, width):
    ang = contour_angle(ground, X, Y); c, s = math.cos(ang), math.sin(ang)
    lo, hi = on_ground(ground, X, Y, length + 12, width + 12, ang, 1.5)
    k.box(X, Y, lo, hi + 1.2, length + 12, width + 12, ang, M["pave"])                             # raised, dry floor
    k.box(X, Y, hi + 1.2, hi + 9, length, width, ang, M["ashlar"])
    k.gable(X, Y, hi + 9, length + 1, width + 1.5, width * .22, ang, M["roof"])
    for side in (-1, 1):
        for u in np.arange(-length / 2 + 3, length / 2, 6):                                       # buttresses along the long walls
            k.box(X + u * c - side * (width / 2 + .6) * s, Y + u * s + side * (width / 2 + .6) * c, hi + 1.2, hi + 7.5, 1.2, 1.2, ang, M["ashlar"])
    ox, oy = X - (length / 2 + 9) * c, Y - (length / 2 + 9) * s
    house(k, ground, ox, oy, 8, 6, 3.8, ang, M["plaster"], M["roof"])                               # the clerk's office

def granaries(ground, M):
    k = Kit("VI · Granary storehouses")
    pts = [site("granary", i) for i in range(3)]
    for X, Y in pts: storehouse(k, ground, M, X, Y, 60, 20)
    HX, HY = site("granary2"); storehouse(k, ground, M, HX, HY, 45, 16)
    gaps = [math.dist(a, b) for i, a in enumerate(pts) for b in pts[i + 1:]]
    return k, round(min(gaps))

# ---------------------------------------------------------------- VIII · Quarries of the Roman Guilds
def guild_quarter(ground, M, extras):
    HX, HY = site("hall"); g = ground.z(HX, HY)
    locks = [site("locks", i) for i in range(5)]
    row = math.atan2(locks[-1][1] - locks[0][1], locks[-1][0] - locks[0][0])
    face = math.atan2(locks[0][1] - HY, locks[0][0] - HX)
    ground.pad(HX, HY, 22, g, 25)
    k = Kit("VIII · Guild hall, lock-houses and quarry")
    k.box(HX, HY, g - 1.5, g + 1.0, 34, 26, face, M["limestone"])
    k.box(HX - 2 * math.cos(face), HY - 2 * math.sin(face), g + 1.0, g + 10, 26, 22, face, M["ashlar"])
    k.gable(HX - 2 * math.cos(face), HY - 2 * math.sin(face), g + 10, 27, 23, 4, face, M["roof"])
    fx, fy = HX + 13.5 * math.cos(face), HY + 13.5 * math.sin(face)
    for j in range(6):
        off = (j - 2.5) * 4
        k.cyl(fx - off * math.sin(face), fy + off * math.cos(face), .5, g + 1.0, g + 9, M["marble"], 10)
    tops = []
    for i, (X, Y) in enumerate(locks):                                                              # five identical lock-houses
        lo, hi = on_ground(ground, X, Y, 12, 10, row, 1.5)
        k.box(X, Y, lo, hi + 5, 9, 8, row, M["plaster"]); k.gable(X, Y, hi + 5, 9.8, 8.8, 1.8, row, M["roof"])
        tx, ty = X + 6.5 * math.cos(row + math.pi / 2), Y + 6.5 * math.sin(row + math.pi / 2)
        k.box(tx, ty, lo, hi + 9, 4.2, 4.2, row, M["ashlar"])
        k.box(X - 4.6 * math.sin(row) * 0 + 4.55 * math.cos(row), Y + 4.55 * math.sin(row), hi + 2.2, hi + 2.9, .15, 1.6, row, M["marble"])   # nameplate
        tops.append(hi)
    CX, CY = site("cliffs"); s = ground.seaward(CX, CY); th = math.atan2(s[1], s[0])
    tx_, ty_ = -s[1], s[0]
    def benches(d, dX, dY, gg):
        along = dX * s[0] + dY * s[1]; across = dX * tx_ + dY * ty_
        inside = (np.abs(across) < 45) & (along > -70) & (along < 5) & (gg > 3)
        return np.where(inside, np.maximum(np.floor(gg / 6) * 6, 3.0), gg)
    ground.edit(CX, CY, 110, benches)                                                              # stepped quarry benches cut into the cliff
    rnd = random.Random(8); stacks = 0
    for i in range(14):
        bx, by = CX - s[0] * rnd.uniform(8, 60) + tx_ * rnd.uniform(-38, 38), CY - s[1] * rnd.uniform(8, 60) + ty_ * rnd.uniform(-38, 38)
        bz = ground.z(bx, by)
        for lvl in range(rnd.randint(2, 5)): k.box(bx, by, bz + lvl * 1.0, bz + (lvl + 1) * 1.0 - .05, 2.2, 1.1, th + rnd.uniform(-.1, .1), M["limestone"])
        stacks += 1
    SX, SY = ground.shore(CX, CY, s)
    k.box(SX + s[0] * 6, SY + s[1] * 6, -3, 1.8, 20, 30, th, M["limestone"])                       # loading quay
    for leg in range(3):                                                                            # a timber crane
        a = th + leg * TAU / 3
        k.box(SX + 3 * math.cos(a) / 2, SY + 3 * math.sin(a) / 2, 1.8, 11, .35, .35, a, M["timber"])
    k.box(SX + s[0] * 5, SY + s[1] * 5, 10.5, 11, 14, .4, th, M["timber"])
    ox, oy = CX - s[0] * 80, CY - s[1] * 80
    house(k, ground, ox, oy, 12, 8, 4.5, th, M["plaster"], M["roof"])                              # the guild's quarry office
    spacing = [math.dist(a, b) for a, b in zip(locks, locks[1:])]
    return k, {"lock_spacing_m": [round(v) for v in spacing], "lock_ground_min_m": round(min(tops), 1), "stone_stacks": stacks,
               "quay": (SX, SY, th), "names": ["CUSTOS I", "CUSTOS II", "CUSTOS III", "CVSTOS IIII", "CUSTOS V"]}

# ---------------------------------------------------------------- IX · Raft Monks
def monastery(ground, M, toward):
    X, Y = site("monastery"); g = ground.z(X, Y)
    face = math.atan2(toward[1] - Y, toward[0] - X); c, s = math.cos(face), math.sin(face)
    ground.pad(X, Y, 30, g, 30)
    k = Kit("IX · Raft monastery")
    for u, v, sx, sy in ((0, 17, 40, 7), (0, -17, 40, 7), (17, 0, 7, 27), (-17, 0, 7, 27)):
        mx, my = X + u * c - v * s, Y + u * s + v * c
        k.box(mx, my, g - 1.5, g + 5, sx, sy, face, M["plaster"])
        k.gable(mx, my, g + 5, sx + .6, sy + .6, 1.6, face if sx > sy else face + math.pi / 2, M["roof"])
    k.box(X, Y, g - .5, g + .2, 26, 26, face, M["garden"])
    sx_, sy_ = X + 27 * c, Y + 27 * s                                                              # the scriptorium, facing the main island
    k.box(sx_, sy_, g - 1.5, g + 8, 10, 16, face, M["plaster"]); k.gable(sx_, sy_, g + 8, 10.8, 16.8, 2.4, face + math.pi / 2, M["roof"])
    SX, SY = ground.shore(X, Y, np.array([c, s]), 1200)
    k.box(SX + c * 20, SY + s * 20, -2.5, 1.2, 50, 4, face, M["timber"])                           # jetty
    tip = ground.z(SX + c * 44, SY + s * 44)
    return k, round(tip, 1), {"shore": (SX, SY), "face": face}                                    # the Raft itself is a prop (blender_props.py)
