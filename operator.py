import bpy
import json
import uuid
from . import util

class MY_OT_OverwriteItem(bpy.types.Operator):
    bl_idname = "global.overwrite_item"
    bl_label = "Overwrite Item"
    bl_description = "Overwrite the selected item with the selected nodes."


    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return (context.space_data.type == 'NODE_EDITOR' and bool(context.selected_nodes) and hasattr(wm, "global_list") and len(wm.global_list) > 0)

    def execute(self, context):
        if context.selected_nodes :
            wm = context.window_manager
            idx = wm.global_list_index
            if idx >= 0:
                target_item = wm.global_list[idx]
                item_name = target_item.name
                data = util.SerializeNodes(context)
                util.update_data_in_json(target_item, data)
                self.report({'INFO'}, f"Successfully overwrote nodes for '{item_name}'")
        
        return {'FINISHED'}


class MY_OT_RemoveItem(bpy.types.Operator):
    bl_idname = "global.remove_item"
    bl_label = "Remove Item"
    bl_description = "Remove selected item"

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return (context.space_data.type == 'NODE_EDITOR' and hasattr(wm, "global_list") and len(wm.global_list) > 0)

    def execute(self, context):
        wm = context.window_manager
        index = wm.global_list_index
        
        if 0 <= index < len(wm.global_list):
            wm.global_list.remove(index)
            item_name = wm.global_list[index].name if index < len(wm.global_list) else "Nodes"

            if index > 0:
                wm.global_list_index = index - 1

            util.store_to_json()

            self.report({'INFO'}, f"Successfully removed '{item_name}' from the list")

        return {'FINISHED'}

class MY_OT_Load(bpy.types.Operator):
    bl_idname = "global.load"
    bl_label = "Load to Node Editor"
    bl_description = "Load the selected item into the editor."

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return (context.space_data.type == 'NODE_EDITOR' and hasattr(wm, "global_list") and len(wm.global_list) > 0)

    def execute(self, context):
        wm = context.window_manager
        idx = wm.global_list_index

        if 0 <= idx < len(wm.global_list):
            item = wm.global_list[idx]
            
            if item.node_data:
                try:
                    data = json.loads(item.node_data)
                    util.DeserializeNodes(self, context, data)
                    self.report({'INFO'}, f"Successfully loaded nodes for '{item.name}'")
                    return {'FINISHED'}
                except json.JSONDecodeError:
                    self.report({'ERROR'}, "Failed to load data: Invalid JSON format")
                    return {'CANCELLED'}
                except Exception as e:
                    self.report({'WARNING'}, f"Failed to restore some nodes: {e}")
                    return {'CANCELLED'}

    
class MY_OT_RegisterItem(bpy.types.Operator):
    bl_idname = "global.register_item"
    bl_label = "Save Item"
    bl_description = "Save selected nodes to the list"

    @classmethod
    def poll(cls, context):
        return (context.space_data.type == 'NODE_EDITOR' and bool(context.selected_nodes))

    def execute(self, context):
        if context.selected_nodes:
            util.load_from_json()
            data = util.SerializeNodes(context)
            item = context.window_manager.global_list.add()
            item.uid = str(uuid.uuid4())
            item.name = "Nodes"
            item.node_data = json.dumps(data, default=util.json_fallback)
            util.store_to_json()

            self.report({'INFO'}, "Successfully saved selected nodes as a new item")
        return {'FINISHED'}

class MY_OT_Reload(bpy.types.Operator):
    bl_idname = "global.reload"
    bl_label = "Reload from File"
    bl_description = "Reload list"

    def execute(self, context):
        util.load_from_json()

        self.report({'INFO'}, "Successfully reloaded list from file")
        return {'FINISHED'}