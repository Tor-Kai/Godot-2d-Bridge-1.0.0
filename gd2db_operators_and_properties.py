import bpy
from time import perf_counter

from bpy_types import (
    Operator,
    PropertyGroup
)

from bpy.props import (
    IntProperty,
    StringProperty,
    BoolProperty,
    EnumProperty,
)

from bpy_extras.io_utils import (
    ImportHelper,
    ExportHelper
)

from math import (
    prod,
    radians
)

from .gd2db_utilities import (
    rotate_around_point,
    ProgressReporter
)

from .gd2db_2d_constraints import remove_all_constraints
from .gd2db_scene_parsing import write_godot_scene
from .gd2db_utilities import export_objects, custom_message_box


# returns list of enumerator property items containing the name of empties within the scene that display images and
# return true for the gd2db_object_2d object property.
def available_references(_self, context):
    reference_object_list = [
        x for x in context.scene.objects
        if x.empty_display_type == 'IMAGE'
        and x.gd2db_object_2d
        and x.data is not None
        and any(x.data.size)
    ]
    if not reference_object_list:
        return [("None", "Add Reference Image", "")]
    else:
        reference_property_list = []
        for ref in reference_object_list:
            reference_property_list.append((ref.name, ref.name, f"{ref}"))
        return reference_property_list


class Godot2dBridgeProperties(PropertyGroup):

    pixels_per_unit: IntProperty(
        name="BU =",
        subtype='PIXEL',
        min=1,
        default=100,
        description="Pixels per Blender unit. Used to determine scale within a 2d space"
    )

    godot_scene: StringProperty(
        name="",
        description="Exported objects will be added to this scene"
    )

    use_collection: BoolProperty(
        name="Collections",
        description="Export collections as 2dNodes"
    )

    selected: BoolProperty(
        name="Selected",
        description="Export selected objects only"
    )

    # noinspection PyTypeChecker
    reference_empty: EnumProperty(
        items=available_references,
        name="",
        description="Chose an image empty to apply"
    )

    mode_updater: StringProperty(
        name="",
        default="init",
        description="Used to run handler only if mode is changed"
    )

    godot_version: EnumProperty(
        items=[
            ("1", "2.1", "Does not support \"Skeleton2D\" nodes or internal vertices"),
            ("2", "3.0", "Does not support \"Skeleton2D\" nodes or internal vertices"),
            ("3", "3.1", ""),
            ("4", "3.2", ""),
            ("5", "3.3", ""),
            ("6", "3.4", ""),
            ("7", "3.5", ""),
            ("8", "3.6", ""),
            ("9", "4.0+", "Versions beyond 4.0 may be unsupported"),
        ],
        name="",
        description="Chose the version of Godot to export the scene for",
        default="7"
    )


# returns a "2d" coordinate constrained to the min and max coordinates
def normalize_2d_coordinates(co, min_co, max_co):
    return (co[0] - min_co[0]) / (max_co[0] - min_co[0]), (co[1] - min_co[1]) / (max_co[1] - min_co[1])


# allows the user to select a godot scene that new objects will be imported into
# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_OT_scene_selection(Operator, ImportHelper):
    bl_label = "Godot Scene"
    bl_idname = "gd2db.scene"
    bl_options = {'REGISTER', "UNDO"}
    bl_description = "Chose *.tscn file to export too"

    filter_glob: StringProperty(default="*.tscn", options={'HIDDEN'})

    def execute(self, context):
        # noinspection PyUnresolvedReferences
        context.scene.godot_2d_bridge_tools.godot_scene = self.filepath
        return {'FINISHED'}


# clear operator for the godot_scene property
# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_OT_clear(Operator):
    bl_label = ""
    bl_idname = "gd2db.clear"
    bl_options = {'REGISTER', "UNDO"}
    bl_description = "Clear scene property"

    # noinspection PyMethodMayBeStatic
    def execute(self, context):
        context.scene.godot_2d_bridge_tools.godot_scene = ""
        return {'FINISHED'}


# builds a material from the user selected image empty and applies it to selected mesh objects
# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_OT_apply_material(Operator):
    bl_label = "Apply Image"
    bl_idname = "gd2db.material"
    bl_options = {'REGISTER', "UNDO"}
    bl_description = "Apply the image displayed in the chosen empty to selected 2d meshes as a texture material"

    # noinspection PyMethodMayBeStatic
    def execute(self, context):

        # filter "2d" mesh objects for the selected objects list
        objects_to_apply = [
            x for x in context.selected_objects
            if x.type == 'MESH'
            and x.gd2db_object_2d
        ]

        # get the image empty chosen by the user
        empty = bpy.data.objects[context.scene.godot_2d_bridge_tools.reference_empty]

        # used to align the active uv of a mesh object to the relative position of the image empty
        def align_uv(object_to_align):
            # calculate the ratio of the image resolutions to the highest resolution axis
            image_ratios = tuple(x / max(empty.data.size) for x in empty.data.size)

            # calculate the min and max positions of uv points within the uv space
            min_position = (x * empty.empty_display_size for x in empty.empty_image_offset)
            min_position = (prod(x) for x in zip(min_position, empty.scale, image_ratios))
            min_position = tuple(sum(x) for x in zip(min_position, empty.location))
            max_position = (x * empty.empty_display_size + empty.empty_display_size for x in empty.empty_image_offset)
            max_position = (prod(x) for x in zip(max_position, empty.scale, image_ratios))
            max_position = tuple(sum(x) for x in zip(max_position, empty.location))

            # check if the mesh object has an uv layer and find the active uv, otherwise create a new uv layer
            if object_to_align.data.uv_layers:
                active_uv = [x for x in object_to_align.data.uv_layers if x.active_render][0]
            else:
                active_uv = object_to_align.data.uv_layers.new(name="UVMap")

            # iterate through object loops to get the vertex index for the associated uv point
            reporting_instance.start_sub_job()
            for loop in object_to_align.data.loops:
                reporting_instance.update()
                reporting_instance.adjust_update_rate()

                # get the x/y coordinate of the vertex relative to the rotation of the empty
                vertex_co = (object_to_align.matrix_world @ object_to_align.data.vertices[loop.vertex_index].co)[0:2]
                vertex_co = rotate_around_point(vertex_co, -empty.rotation_euler.z, point=(empty.location[0:2]))

                # normalize the vertex coordinate to the min and max positions of the uv and assign them to the uv
                uv_point = active_uv.data[loop.index].uv
                uv_point.x, uv_point.y = normalize_2d_coordinates(vertex_co, min_position, max_position)
            reporting_instance.end_sub_job()
            return

        # builds the material, based on the chosen image empty, to assign to the mesh object
        def create_material():
            # create a name unique to this plugin to prevent the operator from accidentally overwriting user created
            # materials or materials created by other plugins or scripts
            name = f"GD2DB: Material \"{empty.data.name}\""

            # used to check if the material exists
            def material_exists():
                exists = False
                for mat in bpy.data.materials:
                    if mat.name == name:
                        exists = True
                        break
                return exists

            # if the material exists perform the operation on that material, otherwise, create a new material
            if material_exists():
                material = bpy.data.materials[name]
            else:
                material = bpy.data.materials.new(name=name)

            # ensure use_nodes is set to true, change the blend_to alpha clip, set the threshold to 0.5, and get the
            # nodes and links for the node tree
            material.use_nodes = True
            material.blend_method = 'CLIP'
            material.alpha_threshold = 0.5
            nodes = material.node_tree.nodes
            links = material.node_tree.links

            # clear all existing nodes
            nodes.clear()

            # create and position the material nodes
            material_output = nodes.new("ShaderNodeOutputMaterial")
            material_output.location = (1200, 0)
            mix_shader = nodes.new('ShaderNodeMixShader')
            mix_shader.location = (900, 0)
            transparent_bsdf = nodes.new('ShaderNodeBsdfTransparent')
            transparent_bsdf.location = (600, 0)
            invert = nodes.new('ShaderNodeInvert')
            invert.location = (300, 0)
            texture = nodes.new('ShaderNodeTexImage')
            texture.location = (0, 0)

            # connect the nodes with links
            links.new(texture.outputs[0], mix_shader.inputs[2])
            links.new(texture.outputs[1], mix_shader.inputs[0])
            links.new(texture.outputs[1], invert.inputs[1])
            links.new(invert.outputs[0], transparent_bsdf.inputs[0])
            links.new(transparent_bsdf.outputs[0], mix_shader.inputs[1])
            links.new(mix_shader.outputs[0], material_output.inputs[0])

            # change the extension mode of the texture node to clip and assign the image in the empty to the image
            # property of the node
            texture.extension = 'CLIP'
            texture.image = empty.data
            return material

        if objects_to_apply:
            # create the material and get the image
            new_material = create_material()
            image = empty.data

            reporting_instance = ProgressReporter(
                "UV UPDATING", [x.name for x in objects_to_apply], [len(x.data.loops) for x in objects_to_apply]
            )

            # iterate through objects_to_apply, apply the new_material to active_material for each object,
            # and set the object properties based on the image
            for obj in objects_to_apply:
                obj.active_material = new_material
                obj.gd2db_texture_image = image.name
                obj.gd2db_image_width = image.size[0]
                obj.gd2db_image_height = image.size[1]
                align_uv(obj)
        return {'FINISHED'}


# toggles the gd2db_object_2d property and constrains the "2d" objects to the x/y plane using handlers
# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_OT_2d_object_toggle(Operator):
    bl_label = "2d/3d Object"
    bl_idname = "gd2db.convert"
    bl_options = {'REGISTER', "UNDO"}
    bl_description = "Toggle the selected objects' status as 2d object"

    # noinspection PyMethodMayBeStatic
    def execute(self, context):
        # filter mesh, armature, and image empty object types from the selected objects list
        objects_to_apply = (
            x for x in context.selected_objects
            if x.type == 'MESH'
            or x.type == 'ARMATURE'
            or x.empty_display_type == 'IMAGE'
        )

        # operator needs to change the active object to change the position of edit bones, so the currently active
        # object is saved to a variable for reapplication at the end of the operator
        active_object = context.view_layer.objects.active

        # iterate through objects_to_apply and check the gd2db_object_2d property to determine which actions to take
        for obj in objects_to_apply:
            if not obj.gd2db_object_2d:

                # apply rotation, Blender won't apply transforms to empties displaying images with multiple users,
                # so the image is removed from the empty and reapplied to get around this
                if obj.type == 'EMPTY':
                    current_image = obj.data
                    obj.data = None
                    bpy.ops.object.transform_apply(location=False, scale=False, properties=False)
                    obj.data = current_image
                else:
                    bpy.ops.object.transform_apply(location=False, scale=False, properties=False)

                # set the gd2db_object_2d property to true to indicate to the rest of the addon this object is a "2d"
                # object, set the rotation mode to xyz euler, 0 the z location, and set the z scale to 1
                obj['gd2db_object_2d'] = True
                obj.rotation_mode = 'XYZ'
                obj.location.z = 0
                obj.scale.z = 1

                # lock the x and y rotation, and the z location and scale properties of the object
                obj.lock_rotation[0] = True
                obj.lock_rotation[1] = True
                obj.lock_scale[2] = True
                obj.lock_location[2] = True

                # check if the object is a mesh or an armature, if it's a mesh then create texture image properties, and
                # 0 the z coordinates of vertices
                if obj.type == 'MESH':
                    obj.gd2db_texture_image = "None"
                    obj.gd2db_image_width = 500
                    obj.gd2db_image_height = 500
                    for vert in obj.data.vertices:
                        vert.co.z = 0

                # if the object is an armature then iterate through its pose and edit bones and set there position and
                # rotation to the x/y plane
                elif obj.type == 'ARMATURE':
                    for bone in obj.pose.bones:
                        # change the pose bone's rotation mode to xyz euler, 0 the bones z location and x/y rotation,
                        # and set the z scale to 1
                        bone.rotation_mode = 'XYZ'
                        bone.location.z = 0
                        bone.rotation_euler.x = 0
                        bone.rotation_euler.y = 0
                        bone.scale.z = 1

                        # lock the x and y rotation, and the z location and scale properties of the pose bone
                        bone.lock_location[2] = True
                        bone.lock_scale[2] = True
                        bone.lock_rotation[0] = True
                        bone.lock_rotation[1] = True

                    # change the active object to the armature and put it in edit mode
                    context.view_layer.objects.active = obj
                    bpy.ops.object.mode_set(mode='EDIT')

                    edit_bones = obj.data.edit_bones
                    for bone in edit_bones:

                        # get the x/y coordinates of the head and tail of the edit bone and check if they're the same
                        # if they are the bone is rotated 90 degrees to prevent removing the bone when the z coordinates
                        # are zeroed
                        bone_head_x_y = bone.head.x, bone.head.y
                        bone_tail_x_y = bone.tail.x, bone.tail.y
                        if bone_head_x_y == bone_tail_x_y:
                            bone_point = bone.head.x, bone.head.z
                            new_tail_x_z = rotate_around_point((bone.tail.x, bone.tail.z), radians(90), bone_point)
                            bone.tail.x, bone.tail.z = new_tail_x_z

                        # 0 the head, tail, and roll
                        bone.head.z = 0
                        bone.tail.z = 0
                        bone.roll = 0

                    # reset the mode to object mode
                    bpy.ops.object.mode_set(mode='OBJECT')
            else:
                # remove the plugin related properties, the plugin will no longer recognize this object as a "2d" object
                # and all locked properties can now be changed by the user
                del obj["gd2db_object_2d"]
                if obj.type == 'MESH':
                    del obj["gd2db_texture_image"]
                    del obj["gd2db_image_width"]
                    del obj["gd2db_image_height"]

        # reset the active object and remove all constraint handlers and timers
        context.view_layer.objects.active = active_object
        if not any((x.gd2db_object_2d for x in bpy.data.objects)):
            remove_all_constraints()
        return {'FINISHED'}


# exports objects and collections based on user defined parameters
# noinspection PyPep8Naming
class GODOT_2D_BRIDGE_OT_export(Operator, ExportHelper):
    bl_label = "Export"
    bl_idname = "gd2db.export"
    bl_description = "Export objects to a *.tscn file"

    # set the filename extension and filter for ExportHelper
    filename_ext = ".tscn"
    filter_glob: StringProperty(default="*.tscn", options={'HIDDEN'})

    def execute(self, _context):
        # get the start time of the export process
        export_start_time = perf_counter()

        # use the gd2db_scene_parsing module to write a new *.tscn file
        # noinspection PyUnresolvedReferences
        export_success = write_godot_scene(self.filepath)

        if export_success:
            # parse the list of exported objects
            exported_list = [f"\"{x.name}\"" for x in export_objects()]
            if len(exported_list) > 2:
                exported_list = ", ".join(exported_list[0:-1]), exported_list[-1]
                exported_list = f"{exported_list[0]}, and {exported_list[1]}"
            elif len(exported_list) > 1:
                exported_list = f"{exported_list[0]} and {exported_list[1]}"
            else:
                exported_list = exported_list[0]

            # generate a successful export popup indicating the objects exported and the elapsed time for export process
            custom_message_box(
                message=f"{exported_list} successfully exported in {perf_counter() - export_start_time:05.2f}s.",
                title="Success!",
                icon='INFO'
            )
        return {'FINISHED'}
