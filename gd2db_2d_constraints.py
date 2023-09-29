from bpy.app.handlers import (
    persistent,
    depsgraph_update_post
)

from bpy.app.timers import (
    register as register_timer,
    unregister as unregister_timer,
    is_registered as timer_registered
)

import bpy

from bmesh import (
    from_edit_mesh,
    update_edit_mesh
)


# returns a list of constraint handlers, the order is important
def handlers():
    return [
        gd2db_constraint_object,
        gd2db_constraint_pose,
        gd2db_constraint_edit_mesh,
        gd2db_constraint_sculpt
    ]


# can be used to remove the constraint timer for edit bones and any instances of the mode specific constraint handlers
def remove_all_constraints():
    # noinspection PyTypeChecker
    if timer_registered(gd2db_constraint_edit_armature):
        unregister_timer(gd2db_constraint_edit_armature)

    handlers_to_remove = [h for h in depsgraph_update_post if h.__name__ in [x.__name__ for x in handlers()]]
    for h in handlers_to_remove:
        depsgraph_update_post.remove(h)


# Blender does not seem to recognize the change in modes during undo and redo operations, so this handler is used to
# activate gd2db_constraint_changer by changing the mode_updater property to its default value
@persistent
def gd2db_undo_redo_activator(scene):
    scene.godot_2d_bridge_tools.mode_updater = "init"


# adds and removes mode specific constraint handlers and timers base on the current object mode
@persistent
def gd2db_constraint_changer(scene):
    # get the current object mode
    obj = bpy.context.object
    if obj:
        mode = obj.mode
    else:
        mode = ""

    # compair mode to the mode_updater property to check if the object mode has changed and check if there are any "2d"
    # objects present in the scene before running the rest of the handler
    if scene.godot_2d_bridge_tools.mode_updater != mode:
        if any((x.gd2db_object_2d for x in bpy.data.objects)):

            # get the type of active object for the context_key
            if mode == 'POSE' or mode == 'EDIT' or mode == 'SCULPT':
                obj_type = obj.type
            else:
                obj_type = ""
            context_key = f"{mode}:{obj_type}"
            key_list = ["OBJECT:", "POSE:ARMATURE", "EDIT:MESH", "SCULPT:MESH"]

            # clear all timers and handlers before adding a new one
            remove_all_constraints()

            # use the context_key to check if in the edit mode of an armature
            # if so, register the gd2db_constraint_edit_armature timer
            if context_key == 'EDIT:ARMATURE':
                # noinspection PyTypeChecker
                if not timer_registered(gd2db_constraint_edit_armature):
                    register_timer(gd2db_constraint_edit_armature)

            # if not in the edit mode of an armature, check if in a mode that a constraint handler would be applicable,
            # build a dictionary to get the correct handler, and append that handler to depsgraph_update_post
            elif context_key in key_list:
                handler = dict(zip(key_list, handlers()))[context_key]
                if handler not in depsgraph_update_post:
                    depsgraph_update_post.append(handler)

            # update mode_updater to the current mode so this handler only gets run if the mode context changes
            scene.godot_2d_bridge_tools.mode_updater = mode


# handler to ensure "2d" objects remain constrained to the xy plane in object mode
def gd2db_constraint_object(_scene):
    obj = bpy.context.object
    if obj and obj.gd2db_object_2d:
        obj.rotation_mode = 'XYZ'
        obj.lock_location[2] = True
        obj.lock_rotation[0] = True
        obj.lock_rotation[1] = True
        obj.lock_scale[2] = True


# handler to ensure pose bones in a "2d" armature remain constrained to the xy plane in pose mode
def gd2db_constraint_pose(_scene):
    bone = bpy.context.active_pose_bone
    if bone and bone.id_data.gd2db_object_2d:
        bone.rotation_mode = 'XYZ'
        bone.lock_location[2] = True
        bone.lock_rotation[0] = True
        bone.lock_rotation[1] = True
        bone.lock_scale[2] = True


# handler to ensure vertices in a "2d" mesh remain constrained to the xy plane in edit mode
# this handler iterates through every vertex for every depsgraph update, so it can get expensive for dense meshes
def gd2db_constraint_edit_mesh(_scene):
    obj = bpy.context.object
    if obj and obj.gd2db_object_2d:
        bm = from_edit_mesh(obj.data)
        bm.verts.ensure_lookup_table()
        for vertex in bm.verts:
            if vertex.co.z:
                vertex.co.z = 0
        update_edit_mesh(obj.data, loop_triangles=True)


# handler to ensure vertices in a "2d" mesh remain constrained to the xy plane in sculpt mode
# this handler iterates through every vertex for every depsgraph update, so it can get expensive for dense meshes
def gd2db_constraint_sculpt(_scene):
    obj = bpy.context.object
    if obj and obj.gd2db_object_2d:
        mesh = obj.data
        for vertex in mesh.vertices:
            if vertex.co.z:
                vertex.co.z = 0


# timer to ensure bones in a "2d" armature remain constrained to the xy plane in edit mode
# if the resolution of this timer is too low it will produce a flickering effect for any bone being manipulated
# this effect is purely visual but undesirable, which is why the timer is set to run so often -0.0001s-
# this timer iterates through every bone for every depsgraph update, however, this doesn't seem to have much, if any,
# effect on performance, no matter how many bones in the armature, further testing may be necessary
def gd2db_constraint_edit_armature():
    obj = bpy.context.object
    if obj and obj.gd2db_object_2d:
        for bone in obj.data.edit_bones:
            if bone.tail.z:
                bone.tail.z = 0
            if bone.head.z:
                bone.head.z = 0
            if bone.roll:
                bone.roll = 0
    return 0.0001
