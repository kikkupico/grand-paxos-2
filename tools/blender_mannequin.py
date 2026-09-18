"""A posable low-poly mannequin for panel layouts: one rigged 1.75 m figure, copied per character and told apart by colour.

The rig has named bones (Hips, Spine, Spine1, Spine2, Neck, Head, and Left/Right Shoulder, Arm, ForeArm, Hand, UpLeg,
Leg, Foot). The body is one mesh of simple parts (capsule limbs, ellipsoid torso and head, box hands and feet), each
weighted wholly to its bone, so it bends like an artist's jointed mannequin. A nose shows which way the head faces.
Copies share the mesh and rig data; each copy has its own pose and its own colour (an object-linked material).

The rest pose stands facing +X with its left toward +Y, arms hanging, feet on z = 0. Poses are rotations of named
bones about the figure's own axes (forward X, left Y, up Z), applied parent first in armature space, so they don't
depend on each bone's local axes. A positive angle about Y tips a bone forward when it points up (spine, neck, head)
and backward when it points down (legs, arms): a thigh swung forward is negative.
"""
import math
import bmesh, bpy
from mathutils import Matrix, Vector

NAME = "Mannequin"
# bone: (head, tail, parent, radius of its body part); y is the figure's left
BONES = {
    "Hips": ((0, 0, .93), (0, 0, 1.05), None, .15), "Spine": ((0, 0, 1.05), (0, 0, 1.18), "Hips", .14),
    "Spine1": ((0, 0, 1.18), (0, 0, 1.30), "Spine", .15), "Spine2": ((0, 0, 1.30), (0, 0, 1.43), "Spine1", .17),
    "Neck": ((0, 0, 1.45), (0, 0, 1.54), "Spine2", .05), "Head": ((0, 0, 1.54), (0, 0, 1.75), "Neck", .1),
}
for side, sy in (("Left", 1), ("Right", -1)):
    BONES.update({
        f"{side}Shoulder": ((0, .04 * sy, 1.41), (0, .18 * sy, 1.42), "Spine2", .06),
        f"{side}Arm": ((0, .2 * sy, 1.41), (0, .22 * sy, 1.13), f"{side}Shoulder", .05),
        f"{side}ForeArm": ((0, .22 * sy, 1.13), (0, .23 * sy, .88), f"{side}Arm", .042),
        f"{side}Hand": ((0, .23 * sy, .88), (0, .23 * sy, .78), f"{side}ForeArm", .045),
        f"{side}UpLeg": ((0, .1 * sy, .93), (0, .1 * sy, .5), "Hips", .075),
        f"{side}Leg": ((0, .1 * sy, .5), (0, .1 * sy, .08), f"{side}UpLeg", .055),
        f"{side}Foot": ((0, .1 * sy, .08), (.16, .1 * sy, .03), f"{side}Leg", .045)})

SIT = [("LeftUpLeg", "Y", -88), ("RightUpLeg", "Y", -88), ("LeftLeg", "Y", 80), ("RightLeg", "Y", 80),
       ("LeftArm", "Y", -25), ("RightArm", "Y", -25), ("LeftForeArm", "Y", -50), ("RightForeArm", "Y", -50)]
POSES = {
    "stand": [("LeftArm", "X", -6), ("RightArm", "X", 6)],
    "stand_look_up": [("LeftArm", "X", -6), ("RightArm", "X", 6), ("Neck", "Y", -12), ("Head", "Y", -28)],
    "orator": [("LeftArm", "X", -6), ("RightArm", "Y", -150), ("RightArm", "X", 20), ("RightForeArm", "Y", -20)],
    "scroll": [("LeftArm", "Y", -40), ("RightArm", "Y", -40), ("LeftForeArm", "Y", -55), ("RightForeArm", "Y", -55),
               ("LeftArm", "X", 10), ("RightArm", "X", -10), ("Head", "Y", 15)],                    # holding a ledger open to read
    "run": [("Spine", "Y", 12), ("Spine1", "Y", 6), ("Head", "Y", -10),
            ("LeftUpLeg", "Y", -45), ("LeftLeg", "Y", 55), ("RightUpLeg", "Y", 30), ("RightLeg", "Y", 75),
            ("RightArm", "Y", -45), ("RightForeArm", "Y", -70), ("LeftArm", "Y", 40), ("LeftForeArm", "Y", -60)],
    "give": [("LeftArm", "X", -6), ("RightArm", "Y", -70), ("RightForeArm", "Y", -15), ("Spine1", "Y", 6)],
    "take": [("LeftArm", "X", -6), ("RightArm", "Y", -60), ("RightForeArm", "Y", -25), ("Spine", "Y", 8)],
    "argue": [("LeftArm", "X", -20), ("LeftForeArm", "Y", -40), ("RightArm", "Y", -100), ("RightForeArm", "Y", -30), ("Spine", "Y", 8)],
    "point": [("LeftArm", "X", -6), ("RightArm", "Y", -90), ("RightForeArm", "Y", 0), ("Spine", "Y", 4)],
    "hold_slate": [("LeftArm", "X", -6), ("RightArm", "Y", -55), ("RightForeArm", "Y", -55), ("Head", "Y", 15)],
    "examine": [("LeftArm", "Y", -45), ("RightArm", "Y", -45), ("LeftForeArm", "Y", -65), ("RightForeArm", "Y", -65), ("Head", "Y", 25)],
    "push_beam": [("Spine", "Y", 25), ("Spine1", "Y", 15), ("Head", "Y", -10),
                  ("LeftUpLeg", "Y", -25), ("LeftLeg", "Y", 30), ("RightUpLeg", "Y", 35), ("RightLeg", "Y", 20),
                  ("LeftArm", "Y", -80), ("LeftForeArm", "Y", -10), ("RightArm", "Y", -80), ("RightForeArm", "Y", -10)],
    "torch_high": [("LeftArm", "X", -6), ("RightArm", "Y", -160), ("RightArm", "X", 15), ("RightForeArm", "Y", -10), ("Head", "Y", -15)],
    "sit": SIT,
    "sit_look_up": SIT + [("Neck", "Y", -12), ("Head", "Y", -28)],
    "doze": SIT + [("Spine1", "Y", 12), ("Neck", "Y", 25), ("Head", "Y", 25)],
}
SEATED = {"sit", "sit_look_up", "doze"}
SEAT_DROP = .85                                                                                     # rig origin below the seat when seated
AXES = {"X": Vector((1, 0, 0)), "Y": Vector((0, 1, 0)), "Z": Vector((0, 0, 1))}

# each shape returns the vertices it made, so its part can be weighted to one bone
def _capsule(bm, a, b, r, seg=8):
    """A tapered low-poly limb from a to b with ball ends."""
    a, b = Vector(a), Vector(b); d = b - a; L = d.length
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    vs = bmesh.ops.create_cone(bm, cap_ends=True, segments=seg, radius1=r, radius2=r * .85, depth=L,
                               matrix=Matrix.Translation((a + b) / 2) @ rot)["verts"]
    for p, rr in ((a, r), (b, r * .85)):
        vs += bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=5, radius=rr, matrix=Matrix.Translation(p))["verts"]
    return vs

def _ellipsoid(bm, c, rx, ry, rz, seg=10):
    return bmesh.ops.create_uvsphere(bm, u_segments=seg, v_segments=7, radius=1, matrix=Matrix.Translation(c) @ Matrix.Diagonal((rx, ry, rz, 1)))["verts"]

def _box(bm, c, sx, sy, sz):
    return bmesh.ops.create_cube(bm, size=1, matrix=Matrix.Translation(c) @ Matrix.Diagonal((sx, sy, sz, 1)))["verts"]

def source(scene):
    """The mannequin rig and body, built once per file in a hidden collection."""
    arm = bpy.data.objects.get(f"{NAME} · rig")
    if arm: return arm, bpy.data.objects[f"{NAME} · body"]
    coll = bpy.data.collections.new(f"{NAME} (source)"); scene.collection.children.link(coll)
    data = bpy.data.armatures.new(NAME); arm = bpy.data.objects.new(f"{NAME} · rig", data); coll.objects.link(arm)
    prev = bpy.context.view_layer.objects.active
    bpy.context.view_layer.objects.active = arm; bpy.ops.object.mode_set(mode="EDIT")
    for name, (h, t, parent, _) in BONES.items():
        eb = data.edit_bones.new(name); eb.head, eb.tail = h, t
        if parent: eb.parent = data.edit_bones[parent]
    bpy.ops.object.mode_set(mode="OBJECT"); bpy.context.view_layer.objects.active = prev
    me = bpy.data.meshes.new(NAME); body = bpy.data.objects.new(f"{NAME} · body", me); coll.objects.link(body)
    bm = bmesh.new(); deform = bm.verts.layers.deform.verify()
    for i, (name, (h, t, _, r)) in enumerate(BONES.items()):
        body.vertex_groups.new(name=name)
        h, t = Vector(h), Vector(t)
        if name in ("Hips",): vs = _ellipsoid(bm, (h + t) / 2, .11, r, .11)                          # torso parts overlap, so it reads as one body
        elif name.startswith("Spine"): vs = _ellipsoid(bm, (h + t) / 2, .1 if name != "Spine2" else .11, r, .12)
        elif name == "Head":
            vs = _ellipsoid(bm, (0, 0, 1.64), .1, .085, .115)
            vs += bmesh.ops.create_cone(bm, cap_ends=True, segments=4, radius1=.02, radius2=0, depth=.05,
                                        matrix=Matrix.Translation((.11, 0, 1.63)) @ Matrix.Rotation(math.pi / 2, 4, "Y"))["verts"]   # the nose
        elif name.endswith("Hand"): vs = _box(bm, (h + t) / 2, .04, .08, .11)
        elif name.endswith("Foot"): vs = _box(bm, (.06, h.y, .035), .25, .09, .07)
        elif name.endswith("Shoulder"): vs = _ellipsoid(bm, t, .06, .06, .06, 8)
        else: vs = _capsule(bm, h, t, r)
        for v in vs: v[deform][i] = 1.0
    bm.to_mesh(me); bm.free()
    for p in me.polygons: p.use_smooth = False
    body.parent = arm; mod = body.modifiers.new("rig", "ARMATURE"); mod.object = arm
    me.materials.append(None)
    coll.hide_render = coll.hide_viewport = True
    return arm, body

def pose(arm, name):
    for pb in arm.pose.bones: pb.matrix_basis = Matrix()
    for bone, axis, deg in POSES[name]:
        bpy.context.view_layer.update(); pb = arm.pose.bones[bone]
        m = pb.matrix.copy(); head = m.translation.copy()
        pb.matrix = Matrix.Translation(head) @ Matrix.Rotation(math.radians(deg), 4, AXES[axis]) @ Matrix.Translation(-head) @ m
    bpy.context.view_layer.update()

def material(hex_):
    name = f"Mannequin · {hex_}"
    m = bpy.data.materials.get(name)
    if m: return m
    m = bpy.data.materials.new(name); m.use_nodes = True; b = m.node_tree.nodes["Principled BSDF"]
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    b.inputs["Base Color"].default_value = (*[(v / 12.92) if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in c], 1)
    b.inputs["Roughness"].default_value = .6
    return m

def _prop_scroll(coll, arm, label, hand, open_=False):
    """A small parchment scroll held in `hand`, bone-parented so it follows the pose."""
    me = bpy.data.meshes.new(f"{label} · scroll"); bm = bmesh.new()
    if open_:
        for dz in (-.13, .13): _capsule(bm, (0, -.14, dz), (0, .14, dz), .018, 6)
        _box(bm, (0, 0, 0), .006, .24, .26)
    else:
        for dy in (-.025, .025): _capsule(bm, (0, dy, -.12), (0, dy, .12), .022, 6)
    bm.to_mesh(me); bm.free(); me.materials.append(material("#efe3c2"))
    ob = bpy.data.objects.new(f"{label} · scroll", me); coll.objects.link(ob)
    ob.parent = arm; ob.parent_type = "BONE"; ob.parent_bone = hand
    ob.location = (0, -.06, 0)                                                                      # from the bone's tail, back into the palm
    return ob

def _prop_slate(coll, arm, label, hand):
    """A rectangular clay order slate held in `hand`."""
    me = bpy.data.meshes.new(f"{label} · slate"); bm = bmesh.new()
    _box(bm, (0, 0, 0), .018, .16, .22)
    bm.to_mesh(me); bm.free(); me.materials.append(material("#bf7a50"))
    ob = bpy.data.objects.new(f"{label} · slate", me); coll.objects.link(ob)
    ob.parent = arm; ob.parent_type = "BONE"; ob.parent_bone = hand
    ob.location = (0, -.06, 0)
    return ob

def _prop_torch(coll, arm, label, hand):
    """A wooden torch with a glowing flame head held in `hand`."""
    me = bpy.data.meshes.new(f"{label} · torch"); bm = bmesh.new()
    _capsule(bm, (0, 0, -.25), (0, 0, .25), .02, 6)
    _ellipsoid(bm, (0, 0, .32), .06, .06, .09, 8)
    bm.to_mesh(me); bm.free(); me.materials.append(material("#ff8a3c"))
    ob = bpy.data.objects.new(f"{label} · torch", me); coll.objects.link(ob)
    ob.parent = arm; ob.parent_type = "BONE"; ob.parent_bone = hand
    ob.location = (0, -.06, 0)
    return ob

def _prop_abacus(coll, arm, label, hand):
    """A portable wooden counting frame held in `hand`."""
    me = bpy.data.meshes.new(f"{label} · abacus"); bm = bmesh.new()
    _box(bm, (0, 0, 0), .022, .22, .15)
    bm.to_mesh(me); bm.free(); me.materials.append(material("#a07040"))
    ob = bpy.data.objects.new(f"{label} · abacus", me); coll.objects.link(ob)
    ob.parent = arm; ob.parent_type = "BONE"; ob.parent_bone = hand
    ob.location = (0, -.06, 0)
    return ob

def place(scene, coll, x, y, z, facing_deg, pose_name, hex_, label, carry=None):
    """A posed, coloured mannequin in `coll`. z is the surface underfoot, or the seat for a seated pose. Returns the rig."""
    src_arm, src_body = source(scene)
    arm = src_arm.copy(); arm.name = f"{label} · rig"
    body = src_body.copy(); body.name = f"{label} · body"; body.parent = arm
    body.modifiers["rig"].object = arm
    coll.objects.link(arm); coll.objects.link(body)
    body.material_slots[0].link = "OBJECT"; body.material_slots[0].material = material(hex_)
    arm.location = (x, y, z - SEAT_DROP if pose_name in SEATED else z)
    arm.rotation_mode = "XYZ"; arm.rotation_euler = (0, 0, math.radians(facing_deg))
    bpy.context.view_layer.update(); pose(arm, pose_name)
    if carry == "scroll": _prop_scroll(coll, arm, label, "RightHand")
    elif carry == "ledger_open": _prop_scroll(coll, arm, label, "RightHand", open_=True)
    elif carry == "slate": _prop_slate(coll, arm, label, "RightHand")
    elif carry == "slate_left": _prop_slate(coll, arm, label, "LeftHand")
    elif carry == "torch": _prop_torch(coll, arm, label, "RightHand")
    elif carry == "abacus": _prop_abacus(coll, arm, label, "LeftHand")
    return arm
