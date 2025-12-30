import bpy
from . import operator

class NODE_PT_my_panel(bpy.types.Panel):
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "Node Holder"
    bl_label = "Node Holder"

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        layout.template_list(
            "MY_UL_List",       # UIListクラス名
            "",                 # ID（通常は空でOK）
            wm,              # リストデータを持っている場所
            "global_list",          # リストのプロパティ名
            wm,              # インデックス（選択番号）を持っている場所
            "global_list_index",   # インデックスのプロパティ名
            rows=5
        )
        row = layout.row(align=True)
        row.operator("global.overwrite_item", icon="GREASEPENCIL", text="Overwrite")
        row.operator("global.remove_item", icon="X", text="Remove")
        row.operator("global.reload", icon='FILE_REFRESH', text="Reload")
        layout.operator("global.register_item", icon="IMPORT", text="Register Nodes")
        layout.operator("global.load", icon="NODETREE", text="Load Nodes")

class MY_UL_List(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon='NODETREE')

        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text="", icon='NODETREE')



