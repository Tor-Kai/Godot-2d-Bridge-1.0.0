import bpy
import re
import os
import bmesh
from mathutils import Vector
from pathlib import Path
from .gd2db_utilities import ProgressReporter

from math import (
    degrees,
    radians,
    sin,
    cos,
    atan2
)

from .gd2db_utilities import (
    rotate_around_point,
    export_objects,
    custom_message_box
    )


# Used to parse the elements of a scene
class GodotSceneParser:

    def __init__(self):
        self.reporting_instance = None
        self.elements = {
            "ext_resource": {},
            "sub_resource": [],
            "node": {},
            "connection": []
        }
        self.godot_version = int(bpy.context.scene.godot_2d_bridge_tools.godot_version)
        self.gd_scene_format = self.get_gd_scene_format()

    def get_gd_scene_format(self):
        if self.godot_version == 1:
            return 1
        elif self.godot_version in range(2, 9):
            return 2
        elif self.godot_version >= 9:
            return 3

    # used to get reporting instance after instantiation so the reporting instance can utilize data from the
    # instance of this class
    def get_reporting_instance(self, reporting_instance):
        self.reporting_instance = reporting_instance

    def _start_reporting_instance(self):
        if self.reporting_instance is not None:
            self.reporting_instance.start_sub_job()

    def _update_reporting_instance(self):
        if self.reporting_instance is not None:
            self.reporting_instance.update()
            self.reporting_instance.adjust_update_rate()

    def _end_reporting_instance(self):
        if self.reporting_instance is not None:
            self.reporting_instance.end_sub_job()

    # adds a series of nested dictionaries to self.elements["node"] of the supplied node and its children using the
    # node's path as the top level key
    def append_nodes(self, node):
        # utilize re pattern matching to get the nodes name and parents
        pattern = re.compile(r"(\[node name=\"(.+?)\" type=\"(.+?)\".)(parent=\"(.+?)\"])?")
        match = re.search(pattern, node)
        parents = match.group(5)
        name = match.group(2)

        # check if the node is the root node or an immediate child of the root node and assign the node_path accordingly
        # two nodes cannot have the same name and parents in Godot, node_path acts as a unique identifier, preventing
        # duplicates
        if not parents:
            node_path = "."
        elif parents == ".":
            node_path = name
        else:
            node_path = f"{parents}/{name}"

        # initialize the node_path dictionary if it doesn't exist and assign the node string to the "node" key
        if self.elements["node"].get(node_path) is not None:
            self.elements["node"][node_path]["node_string"] = node
        else:
            self.elements["node"][node_path] = {
                "node_string": node,
                "children": []
            }

        # check if parents is in "node"
        # if so, append "children" with node_path
        # otherwise, otherwise add parents as a dictionary
        # and initialise "node" as a string, and "children" with node_path
        if parents:
            if self.elements["node"].get(parents) is not None:
                self.elements["node"][parents]["children"].append(node_path)
            else:
                self.elements["node"][parents] = {
                    "node_string": "",
                    "children": [node_path]
                }

    # adds a dictionary entry to elements["ext_resource"] of the supplied resource with the resource id as the key
    def append_external_resources(self, resource):
        # use re pattern matching to find the resource's id
        pattern = re.compile(r"id=(\d+?)")
        match = re.search(pattern, resource)
        resource_id = int(match.group(1))

        # add the dictionary entry, using resource_id as the key ensures there is only one entry per id
        self.elements["ext_resource"][resource_id] = resource

    # sets up self.elements based on if the user supplied path to an existing Godot scene
    def initialize_scene_elements(self):
        # get the user supplied path and get the file extension of the file in that path
        original_path = bpy.context.scene.godot_2d_bridge_tools.godot_scene
        file_extension = original_path.split(".")[-1]

        # check if the user supplied a valid path to an existing Godot scene and get the appropriate scene elements
        if original_path and Path(original_path).exists() and file_extension == "tscn":
            self._parse_original_scene(original_path)
        else:
            # noinspection PyTypedDict
            self.elements["node"] = {
                ".": {
                    "node_string": "[node name=\"Node2D\" type=\"Node2D\"]\n",
                    "children": []
                }
            }

    # creates a sorted list of external resources and assigns the list to self.elements["ext_resource"]
    def sort_finalize_external_resources(self):

        # helper function to allow the _update_reporting_instance function to be used within list comprehension
        # used to avoid the slower for loop
        def update_and_return(value):
            self._update_reporting_instance()
            return value

        self._start_reporting_instance()

        # use the resource ids, assigned as dictionary keys, to sort and assign a list of external resources
        # noinspection PyTypedDict
        self.elements["ext_resource"] = [
            update_and_return(x[1]) for x in sorted(self.elements["ext_resource"].items())
        ]

        self._end_reporting_instance()

    # creates a sorted list of nodes and assigns the list to self.elements["node"]
    def sort_finalize_nodes(self):
        yielded_nodes = set()

        # utilize the nested dictionaries in self.elements["node"] to recursively travers the nodes a yield them in the
        # correct order
        # rule1: every node's parents must be yielded before that node is yielded
        # rule2: all of every node's descendants must be yielded before moving on to the next node
        def traverse_nodes(node_key="."):

            # use the yield_nodes set to prevent duplicate yields and yield the node from the node_key
            if node_key not in yielded_nodes:
                self._update_reporting_instance()
                yield self.elements["node"][node_key]["node_string"]
                yielded_nodes.add(node_key)

            # recursively yield all the node's descendants
            for child in self.elements["node"][node_key]["children"]:
                yield from traverse_nodes(node_key=child)

        self._start_reporting_instance()
        # noinspection PyTypedDict
        self.elements["node"] = list(traverse_nodes())
        self._end_reporting_instance()

    def parse_file_descriptor(self):
        load_steps = len(self.elements["ext_resource"]) + len(self.elements["sub_resource"])
        if load_steps:
            load_steps = f"load_steps={load_steps + 1} "
        else:
            load_steps = ""
        return f"[gd_scene {load_steps}format={self.gd_scene_format}]\n"

    # uses re patterns to find all the elements in a user supplied Godot scene and adds them to the appropriate key in
    # self.elements
    def _parse_original_scene(self, original_path):
        element_pattern = re.compile(r"^(\[)(.+?) .+?(?=\[)", re.MULTILINE | re.DOTALL)

        with open(original_path, "r") as original_scene:
            for match in element_pattern.finditer(original_scene.read()):
                if match.group(2) == "gd_scene":
                    self.gd_scene_format = int(match.group(0)[-4])
                elif match.group(2) == "node":
                    self.append_nodes(match.group(0))
                elif match.group(2) == "ext_resource":
                    self.append_external_resources(match.group(0))
                else:
                    self.elements[match.group(2)].append(match.group(0))


# parent class used to parse the node string for every element that is exported
class ObjectToExport:
    exportable_objects = ()
    pixels = 0
    existing_ids = []

    godot_version = 0
    gd_scene_format = 0

    vector_array_key = "PoolVector2Array"
    position_key = "position"
    rotation_key = "rotation"
    scale_key = "scale"
    texture_key = "texture"
    int_array_key = "PoolIntArray"
    float_array_key = "PoolRealArray"
    bone_length_key = "default_length"

    # used to get variables that do not change between instantiations
    # prevents unnecessary function calls and property lookups
    @classmethod
    def setup(cls, parsing_instance):
        cls.godot_version = parsing_instance.godot_version
        cls.gd_scene_format = parsing_instance.gd_scene_format
        cls.exportable_objects = list(export_objects())
        cls.pixels = bpy.context.scene.godot_2d_bridge_tools.pixels_per_unit
        cls.existing_ids = list(parsing_instance.elements["ext_resource"].keys())

        if cls.gd_scene_format == 1:
            cls.vector_array_key = "Vector2Array"
            cls.position_key = "transform/pos"
            cls.rotation_key = "transform/rot"
            cls.scale_key = "transform/scale"
            cls.texture_key = "texture/texture"
        elif cls.gd_scene_format == 3:
            cls.vector_array_key = "PackedVector2Array"
            cls.int_array_key = "PackedInt32Array"
            cls.float_array_key = "PackedFloat32Array"
            cls.bone_length_key = "length"

    def __init__(self, obj):
        self.obj = obj
        self.parents = self._hierarchy()

        # get a list of collections obj belongs to if obj is of the Object type
        if isinstance(self.obj, bpy.types.Object):
            self.collections = [x for x in self.parents if isinstance(x, bpy.types.Collection)]
        else:
            self.collections = []

        # get the parent string for the node
        if self.parents:
            self.parent_string = "/".join([x.name for x in self.parents])
        else:
            self.parent_string = "."

    # returns an ordered list of objects and collections that self.obj is a child of
    # only objects and collections that are being exported are included in the list
    # the hierarch_of argument can be used to get the hierarchy of an object other than self.obj
    def _hierarchy(self, hierarchy_of=None):
        if hierarchy_of is None:
            hierarchy_of = self.obj

        # recursively yields all the collections in a scene in the order they appear in the view layer panel of the
        # outliner
        def ordered_collections(collection=bpy.context.scene.collection):
            for child in collection.children:
                yield child
                yield from ordered_collections(collection=child)

        # recursively yields all the parented objects of an object
        # skips objects that are not being exported
        def parent_hierarchy(obj=hierarchy_of):
            if isinstance(obj, bpy.types.Object):
                if obj.parent:
                    if obj.parent in self.exportable_objects:
                        yield obj.parent
                        yield from parent_hierarchy(obj=obj.parent)
                    else:
                        for parent_object in parent_hierarchy(obj=obj.parent):
                            yield parent_object

        # start building the hierarchy_list
        hierarchy_list = list(parent_hierarchy())

        # determine the object used to initialize recursion in collection_hierarchy
        if hierarchy_list:
            init_obj = hierarchy_list[-1]
        else:
            init_obj = hierarchy_of

        # returns the first collection yielded from ordered_collections that is also linked to init_obj
        # collections are being used as stand-ins for Node2D nodes that will be added to the scene
        # Godot cannot have objects as children of more than one node, so all other collections in the list are ignored
        def first_linked_collection():
            for collection in ordered_collections():
                if collection in init_obj.users_collection:
                    return collection

        # if the user has activated the use_collections option, collection_hierarchy will recursively yield all the
        # collections that the init_obj belongs to
        def collection_hierarchy(obj=init_obj):
            if bpy.context.scene.godot_2d_bridge_tools.use_collection:

                # check if obj is of the type Object
                # then check the return value of first_liked_collection, and begin recursion up the collection tree
                if isinstance(obj, bpy.types.Object):
                    collection = first_linked_collection()
                    if collection:
                        yield collection
                        yield from collection_hierarchy(obj=collection)
                    else:
                        return
                elif isinstance(obj, bpy.types.Collection):
                    for collection in bpy.data.collections:
                        if obj in list(collection.children):
                            yield collection
                            yield from collection_hierarchy(obj=collection)
                            break

        return tuple(reversed(hierarchy_list + list(collection_hierarchy())))

    # because the user can choose not to export some or all of an objects parents it's necessary to recalculate an
    # object's transforms based on the parents being exported
    def _relative_object_transforms(self):
        world_matrix = self.obj.matrix_world
        transforms = {
            "loc_offset": Vector((0, 0, 0)),
            "rot_offset": Vector((0, 0, 0)),
            "scale_offset": Vector((1, 1, 1)),
            "global_loc": world_matrix.translation,
            "global_rot": Vector(tuple(world_matrix.to_euler())),
            "global_scale": world_matrix.to_scale()
        }

        # get the sum of transforms from exported parents
        object_parents = [x for x in self.parents if isinstance(x, bpy.types.Object)]
        for parent in object_parents:
            transforms["loc_offset"] += parent.location
            transforms["rot_offset"] += Vector(tuple(parent.rotation_euler))
            transforms["scale_offset"] *= parent.scale

        # eliminate rounding errors
        for key in transforms.keys():
            transforms[key] = Vector((
                round(transforms[key].x, 6),
                round(transforms[key].y, 6),
                round(transforms[key].z, 6),
            ))

        # calculate transforms from their parent offsets
        location = transforms["global_loc"] - transforms["loc_offset"]
        rotation = transforms["global_rot"] - transforms["rot_offset"]
        scale = Vector((transforms["global_scale"][x] / transforms["scale_offset"][x] for x in range(3)))

        # parse the transform strings
        location = f"{location.x * self.pixels}, {-location.y * self.pixels}"
        scale = f"{scale.x}, {scale.y}"

        # before Godot 3.1 rotation values of the *.tscn file where in degrees
        if self.gd_scene_format == 1:
            rotation = f"{degrees(-rotation.z)}"
        else:
            rotation = f"{-rotation.z}"

        return location, rotation, scale


# used to parse the node string of a collection as a Node2D node
class CollectionObjectParser(ObjectToExport):
    def __init__(self, obj):
        super().__init__(obj)

    def node2d(self):
        return f"[node name=\"{self.obj.name}\" type=\"Node2D\" parent=\"{self.parent_string}\"]\n"


# used to parse the node string of a mesh as a Polygon2D node
class MeshObjectParser(ObjectToExport):

    def __init__(self, obj):
        super().__init__(obj)
        self.mesh = obj.data
        self.reporting_instance = None
        self.resource_path = ""
        self.resource_id = 0
        self.linked_armature = None

        # get the first armature in the modifier list of the mesh obj
        # Godot cannot link more than one armature to a single object, so all others are ignored
        for modifier in obj.modifiers:
            if modifier.type == 'ARMATURE' and modifier.object and modifier.object in self.exportable_objects:
                self.linked_armature = modifier.object
                break

    # used to get reporting instance after instantiation so the reporting instance can utilize data from the
    # instance of this class
    def get_reporting_instance(self, reporting_instance):
        self.reporting_instance = reporting_instance

    def _start_reporting_instance(self):
        if self.reporting_instance is not None:
            self.reporting_instance.start_sub_job()

    def _update_reporting_instance(self):
        if self.reporting_instance is not None:
            self.reporting_instance.update()
            self.reporting_instance.adjust_update_rate()

    def _end_reporting_instance(self):
        if self.reporting_instance is not None:
            self.reporting_instance.end_sub_job()

    # will save the image that is currently named in the gd2db_texture_image property of the mesh object, if any, and
    # calculate the appropriate resource id for the external resource
    def save_texture(self, scene_path, parsing_instance):

        # get the image object, the full name of the image file, and calculate the filepath to save the image to
        image = bpy.data.images[self.obj.gd2db_texture_image]
        image_filename = image.filepath.split(os.sep)[-1]
        # images are saved to their own folder to avoid overwriting images that may be in the same directory of the
        # scene, but still mitigates duplicates from multiple exports
        image_filepath = os.sep.join(scene_path.split(os.sep)[0:-1] + ["GD2DB_textures"] + [image_filename])

        # get the resource path string
        # used to check if the resource already exists in the scene and to parse new resource lines
        self.resource_path = f"res://GD2DB_textures/{image_filename}"

        # check if the external resource already exists as a dictionary entry and assign the key to self.resource_id
        for key, value in parsing_instance.elements["ext_resource"].items():
            if self.resource_path in value:
                self.resource_id = key
                break

        # check if the resource_id was found, if not, calculate the resource_id
        if not self.resource_id:
            if self.existing_ids:
                id_range = [x for x in range(1, sorted(self.existing_ids)[-1] + 2)]
                self.resource_id = list(set(self.existing_ids) ^ set(id_range))[0]
            else:
                self.resource_id = 1

        # append the calculated resource_id to the list of existing ids
        self.existing_ids.append(self.resource_id)

        # change the image objects filepath and run the save function
        image.filepath_raw = image_filepath
        image.save()

    # returns the external resource string based on the values in self.resource_path and self.resource_id
    def external_resource(self):
        return f"[ext_resource path=\"{self.resource_path}\" type=\"Texture\" id={self.resource_id}]\n"

    # returns a map of the indexes of vertices in blender to the index of those vertices expected in Godot
    def _vertex_map_and_internal_vertex_count(self):
        vertex_map = []

        # initialise the base mesh
        # need to use a base mesh because that is the only way to check if a vertex is on the edge of the mesh
        base_mesh = bmesh.new()
        base_mesh.from_mesh(self.mesh)

        # find the first edge vertex in the base mesh and use it to initialise the vertex_map list
        self._start_reporting_instance()
        for vertex in base_mesh.verts:
            if vertex.is_boundary:
                self._update_reporting_instance()
                vertex_map.append(vertex.index)
                break

        # once the first vertex is appended to vertex map this loop can start, appending the next vertex along the edge
        # as it goes, until it runs out of vertices along the edge of the mesh
        for vertex_ind in vertex_map:
            base_mesh.verts.ensure_lookup_table()
            vertex = base_mesh.verts[vertex_ind]
            next_vert = [
                other_vert for edge in vertex.link_edges
                if (other_vert := edge.other_vert(vertex).index) not in vertex_map
                and edge.is_boundary
            ]
            if next_vert:
                self._update_reporting_instance()
                vertex_map.append(next_vert[0])

        # free the base_mesh
        base_mesh.free()

        # initialise the internal_vertex_count and get a list of vertex indices to compair vertex_index against
        internal_vertex_count = 0
        vertex_indices = list(range(0, len(self.mesh.vertices)))

        # iterate over the difference between vertex_map and vertex_indices and append them to the vertex_map
        # prevents needing to iterate over indices that have already been sorted, and the order of the remaining
        # vertices does not matter as long as they fallow the edge vertices
        for vertex_index in set(vertex_indices).difference(vertex_map):
            self._update_reporting_instance()
            vertex_map.append(vertex_index)
            internal_vertex_count += 1

        self._end_reporting_instance()

        return {x: y for y, x in enumerate(vertex_map)}, internal_vertex_count

    # returns a string that Godot will recognize a list of polygons
    def _polygons(self, vertex_index_map):
        self._start_reporting_instance()
        polygons = []
        for polygon in self.obj.data.polygons:
            self._update_reporting_instance()
            # rebuild the list of vertex indices within the polygon using the vertex_index_map
            polygon_vertices = [str(vertex_index_map[vertex]) for vertex in polygon.vertices]
            polygons.append(f"{self.int_array_key}( {', '.join(polygon_vertices)} )")
        self._end_reporting_instance()
        return ", ".join(polygons)

    # returns three strings that Godot will recognize as vertex coordinates, bone weights, and uv coordinates
    # combined into one function to reduce vertex iterations
    def _vertex_relative_data(self, vertex_index_map):
        if self.mesh.uv_layers:
            active_uv = [x for x in self.mesh.uv_layers if x.active_render][0]
        else:
            active_uv = None
        texture_res = (self.obj.gd2db_image_width, self.obj.gd2db_image_height)

        # Godot's 2d uv's are directly linked to the meshes vertices, so I only need one loop per vertex
        # this builds a map of the vertex index to the first loop associated with that vertex
        loop_index_map = {}
        if active_uv:
            self._start_reporting_instance()
            for loop in self.mesh.loops:
                self._update_reporting_instance()
                if loop_index_map.get(loop.vertex_index) is None:
                    loop_index_map[loop.vertex_index] = loop.index
            self._end_reporting_instance()

        def bone_hierarchy(bone):
            return "/".join([x.name for x in reversed(bone.parent_recursive)] + [bone.name])

        # initiate a dictionary of bone weights, a list of uv coordinates and vertex coordinates
        # the correct values will be assigned to the correct index using the vertex_index_map
        if self.linked_armature is not None:
            bone_weights = {
                bone.name: ["0"] * len(self.mesh.vertices) for bone in self.linked_armature.pose.bones
            }
        else:
            bone_weights = {}
        if active_uv is not None:
            uv_coordinates = [""] * len(self.mesh.vertices)
        else:
            uv_coordinates = []
        vertex_coordinates = [""] * len(self.mesh.vertices)

        # iterate through the vertices gathering all the data for each vertex as it goes
        self._start_reporting_instance()
        for vertex in self.mesh.vertices:
            self._update_reporting_instance()

            # get the correct index of the vertex for Godot
            index = vertex_index_map[vertex.index]

            # iterate through the vertex groups and assign the weight of the vertex for that group to the correct
            # position in bone_weights
            if bone_weights:
                for group_element in vertex.groups:
                    group_name = self.obj.vertex_groups[group_element.group].name
                    if group_name in bone_weights:
                        bone_weights[group_name][index] = str(group_element.weight)

            # calculate the uv coordinate base on the associated loop index in the loop_index_map and assign it to the
            # correct position in the uv_coordinates list
            if uv_coordinates:
                uv_co_x = active_uv.data[loop_index_map[vertex.index]].uv.x * texture_res[0]
                uv_co_y = -active_uv.data[loop_index_map[vertex.index]].uv.y * texture_res[1] + texture_res[1]
                uv_coordinates[index] = f"{uv_co_x}, {uv_co_y}"

            # calculate the vertex coordinate and assign it to the correct position in the vertex_coordinates list
            vertex_coordinates[index] = f"{vertex.co.x * self.pixels}, {-vertex.co.y * self.pixels}"
        self._end_reporting_instance()

        # finish parsing bone_weights
        bone_weights = ", ".join(
            (
                f"\"{bone_hierarchy(self.linked_armature.pose.bones[bone_name])}\", "
                f"{self.float_array_key}( {', '.join(bone_weights[bone_name])} )"
                for bone_name in bone_weights
            )
        )
        return vertex_coordinates, bone_weights, uv_coordinates

    # returns a string that Godot will recognize as a path to the armature linked to this mesh
    def _skeleton_hierarchy(self):
        # use a list of the linked armatures parents and the meshes parents
        # to get a list of parents that are common to both of them
        armature_parents = (
                [x.name for x in self._hierarchy(hierarchy_of=self.linked_armature)] + [self.linked_armature.name]
        )
        mesh_parents = (
            [x.name for x in self.parents] + [self.obj.name]
        )
        common_parents = [x for x in armature_parents if x in mesh_parents]

        # calculate the difference between the number of the meshes' parents the number of their common parents
        relative_parents = len(mesh_parents) - len(common_parents)

        # the number of "../" tells Godot how many levels up the node tree to go before finding the first common parent
        return "/".join([".."] * relative_parents + armature_parents[len(common_parents):])

    # returns the Polygon2D node string
    def polygon2d_node(self):
        vertex_index_map, internal_vertex_count = self._vertex_map_and_internal_vertex_count()
        vertex_coordinates, bone_weights, uv_coordinates = self._vertex_relative_data(vertex_index_map)
        location, rotation, scale = self._relative_object_transforms()

        # remove references to internal vertices for Godot 3.0 and earlier
        if self.godot_version < 3:
            vertex_coordinates = vertex_coordinates[:-internal_vertex_count]
            uv_coordinates = uv_coordinates[:-internal_vertex_count]
            polygons_line = ""
            internal_vertex_line = ""
        else:
            polygons_line = f"polygons = [ {self._polygons(vertex_index_map)} ]\n"
            internal_vertex_line = f"internal_vertex_count = {internal_vertex_count}\n"

        # get lines for the linked armature if one is recognized
        if self.linked_armature is not None:
            skeleton_line = f"skeleton = NodePath(\"{self._skeleton_hierarchy()}\")\n"
            bones_line = f"bones = [ {bone_weights} ]\n"
        else:
            skeleton_line = ""
            bones_line = ""

        # get the texture reference if a texture is associated with this mesh
        if self.resource_id:
            texture_line = f"{self.texture_key} = ExtResource( {self.resource_id} )\n"
        else:
            texture_line = ""

        return (
            f"[node name=\"{self.obj.name}\" type=\"Polygon2D\" parent=\"{self.parent_string}\"]\n"
            f"{texture_line}"
            f"{self.position_key} = Vector2( {location} )\n"
            f"{self.rotation_key} = {rotation}\n"
            f"{self.scale_key} = Vector2( {scale} )\n"
            f"{skeleton_line}"
            f"polygon = {self.vector_array_key}( {', '.join(vertex_coordinates)} )\n"
            f"uv = {self.vector_array_key}( {', '.join(uv_coordinates)} )\n"
            f"{polygons_line}"
            f"{bones_line}"
            f"{internal_vertex_line}"
        )


# used to parse the node string of an armature as a Skeleton2D node and its bones as Bone2D nodes
class ArmatureObjectParser(ObjectToExport):
    def __init__(self, obj):
        super().__init__(obj)

    # returns the node string for the Skeleton2D node
    def skeleton2d_node(self):
        location, rotation, scale = self._relative_object_transforms()
        return (
            f"[node name=\"{self.obj.name}\" type=\"Skeleton2D\" parent=\"{self.parent_string}\"]\n"
            f"{self.position_key} = Vector2( {location} )\n"
            f"{self.rotation_key} = {rotation}\n"
            f"{self.scale_key} = Vector2( {scale} )\n"
        )

    # returns the node string for the Bone2D node of a bone in this armature
    def bone2d_node(self, pose_bone):

        # returns the location of the bone in the rest position, calculated for use in Godot's 2d space
        def rest_location():
            edit_bone = pose_bone.bone
            position = Vector((edit_bone.head_local.x, edit_bone.head_local.y))
            if edit_bone.parent:
                slope = (
                    edit_bone.parent.head_local.x - edit_bone.parent.tail_local.x,
                    edit_bone.parent.head_local.y - edit_bone.parent.tail_local.y
                )

                parent_angle = atan2(slope[0], slope[1]) + radians(90)
                parent_position = Vector((edit_bone.parent.head_local.x, edit_bone.parent.head_local.y))
            else:
                parent_angle = 0.0
                parent_position = Vector((0.0, 0.0))
            position -= parent_position
            position = rotate_around_point(position, parent_angle)
            return position[0] * self.pixels, -position[1] * self.pixels

        # returns the location of the bone in the pose position, calculated for use in Godot's 2d space
        def pose_location():
            position = Vector((pose_bone.head.x, pose_bone.head.y))
            if pose_bone.parent:
                slope = (
                    pose_bone.parent.head.x - pose_bone.parent.tail.x,
                    pose_bone.parent.head.y - pose_bone.parent.tail.y
                )
                parent_angle = atan2(slope[0], slope[1]) + radians(90)
                parent_position = Vector((pose_bone.parent.head.x, pose_bone.parent.head.y))
            else:
                parent_angle = 0.0
                parent_position = Vector((0.0, 0.0))
            position -= parent_position
            position = rotate_around_point(position, parent_angle)
            return position[0] * self.pixels, -position[1] * self.pixels

        # returns the rotation of the bone in the rest position, calculated for use in Godot's 2d space
        def rest_angle():
            edit_bone = pose_bone.bone
            slope = (
                edit_bone.head_local.x - edit_bone.tail_local.x,
                edit_bone.head_local.y - edit_bone.tail_local.y
            )

            angle = atan2(slope[0], slope[1]) + radians(90)
            if edit_bone.parent:
                slope = (
                    edit_bone.parent.head_local.x - edit_bone.parent.tail_local.x,
                    edit_bone.parent.head_local.y - edit_bone.parent.tail_local.y
                )

                parent_angle = atan2(slope[0], slope[1]) + radians(90)
            else:
                parent_angle = 0
            angle -= parent_angle
            return atan2(sin(angle), cos(angle))

        # returns the rotation of the bone in the pose position, calculated for use in Godot's 2d space
        def pose_angle():
            slope = (
                pose_bone.head.x - pose_bone.tail.x,
                pose_bone.head.y - pose_bone.tail.y
            )

            angle = atan2(slope[0], slope[1]) + radians(90)
            if pose_bone.parent:
                slope = (
                    pose_bone.parent.head.x - pose_bone.parent.tail.x,
                    pose_bone.parent.head.y - pose_bone.parent.tail.y
                )

                parent_angle = atan2(slope[0], slope[1]) + radians(90)
            else:
                parent_angle = 0
            angle -= parent_angle
            return atan2(sin(angle), cos(angle))

        # calculate the path of the Bone2D node
        if self.parent_string != ".":
            parents = [self.parent_string]
        else:
            parents = []
        parents += [self.obj.name] + [x.name for x in reversed(pose_bone.parent_recursive)]
        parents = "/".join(parents)

        # get the rest values, so I don't have to rerun those functions
        location_at_rest = rest_location()
        angle_at_rest = rest_angle()

        # parse a string that Godot will recognize as the bone's rest position
        rest_pose = ", ".join(
            [
                str(x) for x in (
                    cos(angle_at_rest), sin(angle_at_rest), -sin(angle_at_rest), cos(angle_at_rest), *location_at_rest
                )
            ]
        )

        # use the armatures pose position to determine whether to export the bone position in the rest mode or the pose
        # mode, ensures the user gets the results they expect as seen in Blender
        if self.obj.data.pose_position == 'POSE':
            current_position = pose_location()
            current_angle = pose_angle()
        else:
            current_position = location_at_rest
            current_angle = angle_at_rest

        # parse lines that are present only in Godot 4.0 and later
        if self.gd_scene_format == 3:
            auto_calculate_line = "auto_calculate_length_and_angle = false\n"
            angle_line = "bone_angle = 0\n"
        else:
            auto_calculate_line = ""
            angle_line = ""

        return (
            f"[node name=\"{pose_bone.name}\" type=\"Bone2D\" parent=\"{parents}\"]\n"
            f"{self.position_key} = Vector2( {current_position[0]}, {current_position[1]} )\n"
            f"{self.rotation_key} = {current_angle}\n"
            f"{self.scale_key} = Vector2( {pose_bone.scale.x}, {pose_bone.scale.y} )\n"
            f"rest = Transform2D( {rest_pose} )\n"
            f"{auto_calculate_line}"
            f"{self.bone_length_key} = {pose_bone.length * self.pixels}\n"
            f"{angle_line}"
        )


# uses data gathered by the previous classes to write a new *.tscn file
def write_godot_scene(new_file_path):

    # instantiate GodotSceneParser and get the initial elements of the scene to be built
    parsing_instance = GodotSceneParser()
    parsing_instance.initialize_scene_elements()

    # give a warning message and return if the user is attempting to add elements in a different formate from the
    # original scene
    if parsing_instance.gd_scene_format != parsing_instance.get_gd_scene_format():
        custom_message_box(
            message="You are attempting to export objects to a scene "
                    "with a different format than the selected Godot version.",
            title="Export Canceled!",
            icon="CANCEL",
        )
        return False

    # called after instantiation of GodotSceneParser to use data from the elements variable
    ObjectToExport.setup(parsing_instance)

    # iterate through the objects being exported and parse their nodes
    for obj in ObjectToExport.exportable_objects:
        print("\n")
        job_name = f"Parsing \"{obj.name}\" Node"

        # check if the object is a mesh or an armature to determine what type of parser to use
        if obj.type == 'MESH':
            object_parser = MeshObjectParser(obj)

            # build the list of job titles and calculate there totals
            sub_jobs = [
                "Parsing Node2D Nodes",
                "Building Vertex Index Map",
                "Building Loop Index Map",
                "Gathering Vertex Data",
                "Building Polygons"
            ]
            sub_job_totals = [
                len(object_parser.collections),
                len(obj.data.vertices),
                len(obj.data.loops),
                len(obj.data.vertices),
                len(obj.data.polygons)
            ]

            # remove the loop index map job if there are no uv layers
            if not obj.data.uv_layers:
                del sub_jobs[2]
                del sub_job_totals[2]

            # instantiate the ProgressReporter and apply that instance to the object_parser
            reporting_instance = ProgressReporter(job_name, sub_jobs, sub_job_totals)
            object_parser.get_reporting_instance(reporting_instance)

            # iterate through the collections this object is a child of and parse the "Node2D" node
            reporting_instance.start_sub_job()
            for collection in object_parser.collections:
                reporting_instance.update()
                reporting_instance.adjust_update_rate()

                collection_parser_instance = CollectionObjectParser(collection)
                parsing_instance.append_nodes(collection_parser_instance.node2d())

            reporting_instance.end_sub_job()

            # save the texture and parse the external resource if an image exists for this mesh
            if obj.gd2db_texture_image != "None":
                object_parser.save_texture(new_file_path, parsing_instance)
                parsing_instance.append_external_resources(object_parser.external_resource())

            # parse the Polygon2D node
            parsing_instance.append_nodes(object_parser.polygon2d_node())

        if obj.type == 'ARMATURE':
            object_parser = ArmatureObjectParser(obj)

            # build the list of job titles, calculate there totals, and instantiate the ProgressReporter
            sub_jobs = [
                "Parsing Node2D Nodes",
                "Parsing Bone2D Nodes"
            ]
            sub_job_totals = [
                len(object_parser.collections),
                len(obj.pose.bones)
            ]
            reporting_instance = ProgressReporter(job_name, sub_jobs, sub_job_totals)

            # iterate through the collections this object is a child of and parse the "Node2D" node
            reporting_instance.start_sub_job()
            for collection in object_parser.collections:
                reporting_instance.update()
                reporting_instance.adjust_update_rate()
                collection_parser_instance = CollectionObjectParser(collection)
                parsing_instance.append_nodes(collection_parser_instance.node2d())
            reporting_instance.end_sub_job()

            # parse the Skeleton2D node and append it to the parsing_instance
            parsing_instance.append_nodes(object_parser.skeleton2d_node())

            # iterate through the bones in this armature and parse the "Bone2D" node
            reporting_instance.start_sub_job()
            for bone in obj.pose.bones:
                reporting_instance.update()
                reporting_instance.adjust_update_rate()
                parsing_instance.append_nodes(object_parser.bone2d_node(bone))
            reporting_instance.end_sub_job()

    # parse the name of the new file, build the list of job titles, and calculate there totals
    new_file = new_file_path.split(os.sep)[-1]
    sub_jobs = [
        "Sort and Finalize Resources",
        "Sort and Finalize Nodes",
        f"Writing Scene Elements to \"{new_file}\""
    ]
    sub_job_totals = [
        len(parsing_instance.elements["ext_resource"]),
        len(parsing_instance.elements["node"]),
        sum([len(x) for x in parsing_instance.elements.values()])
    ]

    print("\n")
    reporting_instance = ProgressReporter(f"Finalizing Scene", sub_jobs, sub_job_totals)
    parsing_instance.get_reporting_instance(reporting_instance)

    # sort and finalize the nodes and external resources of the scene
    parsing_instance.sort_finalize_external_resources()
    parsing_instance.sort_finalize_nodes()

    # create the *.tscn file and write the elements from the parsing_instance to the file
    reporting_instance.start_sub_job()
    elements = [parsing_instance.parse_file_descriptor()] + sum(parsing_instance.elements.values(), [])
    with open(new_file_path, "w") as new_godot_scene:
        for element in elements:
            reporting_instance.update()
            new_godot_scene.write(f"{element}\n")
    reporting_instance.end_sub_job()
    return True
