# Godot 2d Bridge

## What is this for?

Godot 2D Bridge allows game developers using Godot -an open-source game engine- to build 2D mesh objects in Blender, skin those meshes to an armature and export those elements to a Godot scene (*.tscn) as 2D nodes.

## Why?

In Godot, developers can build 2D meshes as Polygon2D nodes and skin those meshes to 2D armatures -Skeleton2D nodes-. This allows developers to create smooth animations through deformation of raster images by assigning those images as textures to the Polygon2D node. However, this process is difficult through Godot's 2D mesh editor and not suitable for dense meshes or complex armatures.

That's where Godot 2D Bridge comes in. This add-on gives game developers the ability to leverage the tools available in Blender for mesh creation, manipulation, and skinning, to build 2D meshes and armatures for Godot.

## Installation

Select Code>Local>Download Zip at the top-right of the page or download "Godot_2d_Bridge_#.#.#.zip" from the "Releases" section on the right. In Blender go to Edit>Preferences>Add-ons>install and select the zip file you just downloaded. Detailed documentation will be included in the *.zip file if you downloaded the *.zip file from the top-right and can be downloaded separately from the releases section as Godot.2d.Bridge.Documentation.pdf.


## How To Use

Once installed, the interface for this addon can be found in the side-bar in Blender. Hovering over the elements of the UI will give you a short description of what each tool does.

A short demonstration of the add-on can be viewed [here](https://public-files.gumroad.com/7bmevsbb5jqn686b3m52am7w5v4z). The armature and the mesh where built ahead of time for this demo to focus on the features of the add-on, but you would normally want to convert those objects to 2D objects before performing major edits, because the add-on will lock the elements of an object to the x/y plane for you while you work.

The expected work-flow is to use a reference image to build a mesh and armature. Then, skin the armature to the mesh. Finally, export the objects to either a new or existing Godot scene. However, the tools in this add-on are pretty robust given it's scope and I expect you could find uses for them beyond what the add-on was designed for. I encourage you to experiment with this add-on even if you have no intention of using Godot.

## Compatibility

Works with Blender 2.8+.

Includes support for Godot 2.1 - 4.0+.

Works on Windows and should work in Linux as well, though I do not have the ability to test for Linux. If you use Linux let me know if you have any issues.

## Support the author

Currently the best way to support me is to make a purchase from my [Gumroad](https://torkai.gumroad.com/l/godot2dbridge) page and/or giving the addon a star rating on the same page. This addon is completely free and the Gumroad page is set up as pay-what-you want.

##Contact Me

For questions, comments, suggestions, addaboys, or criticisms you can contact me here on Github, through email at opensourcetorkai@gmail.com, or through [reddit](https://www.reddit.com/user/Tor-Kai).
