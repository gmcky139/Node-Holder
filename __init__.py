bl_info = {
    "name": "Node Holder",
    "author": "gmcky139",
    "version": (1, 0, 0),
    "blender": (4, 5, 0),
    "location": "Node Editor > Sidebar > Node Holder",
    "description": "Save selected nodes with connections and data for reuse across blend files.",
    "support": "COMMUNITY",
    "warning": "",
    "doc_url": "https://github.com/gmcky139/Node-Holder",
    "tracker_url": "https://github.com/gmcky139/Node-Holder/issues",
    "category": "Node",
}

import bpy
import importlib
import uuid
from . import util
from . import ui
from . import operator


class GlobalItem(bpy.types.PropertyGroup):
    uid: bpy.props.StringProperty(default="")
    name: bpy.props.StringProperty(name="Name", default="New Item", update = util.update_name_in_json)
    node_data: bpy.props.StringProperty(name="Node Data JSON", default="{}")

pyfiles = [
    util,
    ui,
    operator
]

for p in pyfiles:
    if str(p) in locals():
        importlib.reload(p)

classes = [
    GlobalItem,
    ui.MY_UL_List,
    operator.MY_OT_OverwriteItem,
    operator.MY_OT_RemoveItem,
    operator.MY_OT_Load,
    operator.MY_OT_RegisterItem,
    operator.MY_OT_Reload,
    ui.NODE_PT_my_panel
]

def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.WindowManager.global_list = bpy.props.CollectionProperty(type=GlobalItem)
    bpy.types.WindowManager.global_list_index = bpy.props.IntProperty()

    util.load_from_json()

def unregister():
    util.store_to_json()

    del bpy.types.WindowManager.global_list
    del bpy.types.WindowManager.global_list_index

    for c in reversed(classes):
        bpy.utils.unregister_class(c)

if __name__ == "__main__":
    register()