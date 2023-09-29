bl_info = {
    "name": "Godot 2d Bridge",
    "author": "TorKai",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar > Godot 2d Bridge",
    "description": "Used to bridge Blender and Godot's 2d mesh, bone, and skinning functionality",
    "warning": "",
    "doc_url": "",
    "category": "Godot",
}

import bpy

from bpy.props import PointerProperty

from bpy.app.handlers import (
    depsgraph_update_post,
    undo_post,
    redo_post
)

from .gd2db_operators_and_properties import (
    GODOT_2D_BRIDGE_OT_scene_selection,
    GODOT_2D_BRIDGE_OT_export,
    GODOT_2D_BRIDGE_OT_clear,
    GODOT_2D_BRIDGE_OT_2d_object_toggle,
    GODOT_2D_BRIDGE_OT_apply_material,
    Godot2dBridgeProperties
)

from .gd2db_ui import (
    GODOT_2D_BRIDGE_PT_export_panel,
    GODOT_2D_BRIDGE_PT_setup_panel
)

from .gd2db_2d_constraints import (
    gd2db_constraint_changer,
    remove_all_constraints,
    gd2db_undo_redo_activator
)

from bpy.utils import (
    register_class,
    unregister_class
)


# =========================================================================
# Property Functions:
# =========================================================================


# used to make gd2db_object_2d readonly
def get_object_2d(self):
    setter = False
    if self.get("gd2db_object_2d"):
        setter = self["gd2db_object_2d"]
    return setter


# returns a list of enumerator property items containing the names of available images within the blender file
def gd2db_texture_items(_self, _context):
    item_list = [("None", "None", "")]
    for img in bpy.data.images:
        item_list.append((img.name, img.name, ""))
    return item_list


# =========================================================================
# Registration:
# =========================================================================


classes = (
    GODOT_2D_BRIDGE_OT_apply_material,
    GODOT_2D_BRIDGE_OT_scene_selection,
    GODOT_2D_BRIDGE_OT_export,
    GODOT_2D_BRIDGE_OT_clear,
    GODOT_2D_BRIDGE_OT_2d_object_toggle,
    GODOT_2D_BRIDGE_PT_setup_panel,
    GODOT_2D_BRIDGE_PT_export_panel,
    Godot2dBridgeProperties
)


def register():

    bpy.types.Object.gd2db_object_2d = bpy.props.BoolProperty(
        name="",
        get=get_object_2d,
        options={'HIDDEN'}
    )

    # noinspection PyTypeChecker
    bpy.types.Object.gd2db_texture_image = bpy.props.EnumProperty(
        name="gd2db_texture_image",
        items=gd2db_texture_items,
        options={'HIDDEN'}
    )

    bpy.types.Object.gd2db_image_width = bpy.props.IntProperty(
        name="gd2db_image_width",
        subtype="PIXEL",
        min=1,
        default=500,
        options={'HIDDEN'}
    )

    bpy.types.Object.gd2db_image_height = bpy.props.IntProperty(
        name="gd2db_image_height",
        subtype="PIXEL",
        min=1,
        default=500,
        options={'HIDDEN'}
    )

    depsgraph_update_post.append(gd2db_constraint_changer)
    redo_post.append(gd2db_undo_redo_activator)
    undo_post.append(gd2db_undo_redo_activator)

    for cls in classes:
        register_class(cls)
    bpy.types.Scene.godot_2d_bridge_tools = PointerProperty(type=Godot2dBridgeProperties)


def unregister():
    del bpy.types.Object.gd2db_object_2d
    del bpy.types.Object.gd2db_texture_image
    del bpy.types.Object.gd2db_image_width
    del bpy.types.Object.gd2db_image_height

    remove_all_constraints()
    depsgraph_update_post.remove(gd2db_constraint_changer)
    redo_post.remove(gd2db_undo_redo_activator)
    undo_post.remove(gd2db_undo_redo_activator)

    for cls in classes:
        unregister_class(cls)
    del bpy.types.Scene.godot_2d_bridge_tools


if __name__ == "__main__":
    register()
