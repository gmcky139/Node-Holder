import bpy
import json
import uuid
from . import util

class MY_OT_OverwriteItem(bpy.types.Operator):
    bl_idname = "global.overwrite_item"
    bl_label = "Overwrite Item"
    bl_description = "Overwrite the selected item with the selected nodes."

    def execute(self, context):
        if context.selected_nodes :
            wm = context.window_manager
            idx = wm.global_list_index
            if idx >= 0:
                target_item = wm.global_list[idx]
                data = util.SerializeNodes(context)
                util.update_data_in_json(target_item, data)
        
        return {'FINISHED'}


class MY_OT_RemoveItem(bpy.types.Operator):
    bl_idname = "global.remove_item"
    bl_label = "Remove Item"
    bl_description = "Remove selected item"

    def execute(self, context):
        wm = context.window_manager
        index = wm.global_list_index
        
        if 0 <= index < len(wm.global_list):
            wm.global_list.remove(index)

            if index > 0:
                wm.global_list_index = index - 1

        util.store_to_json()
                
        return {'FINISHED'}

class MY_OT_Load(bpy.types.Operator):
    bl_idname = "global.load"
    bl_label = "Load to Node Editor"
    bl_description = "Load the selected item into the editor."

    def execute(self, context):
        wm = context.window_manager
        idx = wm.global_list_index

        if 0 <= idx < len(wm.global_list):
            item = wm.global_list[idx]
            
            if item.node_data:
                try:
                    data = json.loads(item.node_data)
                    util.DeserializeNodes(context, data)
                except json.JSONDecodeError:
                    self.report({'ERROR'}, "データの読み込みに失敗しました")

        return {'FINISHED'}
    
class MY_OT_RegisterItem(bpy.types.Operator):
    bl_idname = "global.register_item"
    bl_label = "Save Item"
    bl_description = "Save selected nodes to the list"

    def execute(self, context):
        if context.selected_nodes:
            util.load_from_json()
            data = util.SerializeNodes(context)
            item = context.window_manager.global_list.add()
            item.uid = str(uuid.uuid4())
            item.name = "Nodes"
            item.node_data = json.dumps(data, separators=(',', ':'))
            util.store_to_json()
        return {'FINISHED'}

class MY_OT_Reload(bpy.types.Operator):
    bl_idname = "global.reload"
    bl_label = "Reload from File"
    bl_description = "Reload list"

    def execute(self, context):
        util.load_from_json()
        util.store_to_json()
        return {'FINISHED'}