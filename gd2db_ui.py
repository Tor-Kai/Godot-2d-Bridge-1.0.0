from bpy_types import Panel
from .gd2db_utilities import export_objects


# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_PT_setup_panel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Godot 2d Bridge"
    bl_label = "Editing"

    def draw(self, context):
        # noinspection PyUnresolvedReferences
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Object Conversion")
        row = box.row(align=True)
        if not any(
                x.type == "MESH"
                or x.type == "ARMATURE"
                or x.empty_display_type == 'IMAGE'
                for x in context.selected_objects
        ) or context.mode != 'OBJECT':
            row.enabled = False
        row.operator("gd2db.convert")

        # noinspection PyUnresolvedReferences
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Image Texture")
        row = box.row(align=True)
        row.prop(context.scene.godot_2d_bridge_tools, "reference_empty")
        row = box.row(align=True)
        if not any(x.gd2db_object_2d for x in context.selected_objects)\
                or not any(x.type == 'MESH' for x in context.selected_objects)\
                or context.scene.godot_2d_bridge_tools.reference_empty == "None"\
                or context.mode != 'OBJECT':
            row.enabled = False
        row.operator("gd2db.material")


# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_PT_export_panel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Godot 2d Bridge"
    bl_label = "Exporting"

    def draw(self, context):
        # noinspection PyUnresolvedReferences
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Export Options")
        sub_box = box.box()
        row = sub_box.row(align=True)
        row.operator("gd2db.scene")
        row = sub_box.row(align=True)
        row.prop(context.scene.godot_2d_bridge_tools, "godot_scene")
        row.operator("gd2db.clear", icon='CANCEL')
        row = box.row(align=True)
        row.prop(context.scene.godot_2d_bridge_tools, "use_collection")
        row.prop(context.scene.godot_2d_bridge_tools, "selected")

        # noinspection PyUnresolvedReferences
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Pixels / Blender Unit")
        row = box.row(align=True)
        row.prop(context.scene.godot_2d_bridge_tools, "pixels_per_unit")

        # noinspection PyUnresolvedReferences
        box = self.layout.box()
        row = box.row(align=True)
        row.label(text="Godot Version:")
        row = box.row(align=True)
        row.prop(context.scene.godot_2d_bridge_tools, "godot_version")

        # noinspection PyUnresolvedReferences
        row = self.layout.row(align=True)
        if not list(export_objects()) or context.mode != 'OBJECT':
            row.enabled = False
        row.operator("gd2db.export")
