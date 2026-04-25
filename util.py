import bpy
import json
from pathlib import Path
from contextlib import contextmanager
import mathutils

IS_UPDATING = False
DATA_FILE = Path(__file__).parent / "data" / "global_list_data.json"

@contextmanager
def prevent_update():
    global IS_UPDATING
    IS_UPDATING = True
    try:
        yield
    finally:
        IS_UPDATING = False

# ==========================================
# File I/O Helpers
# ==========================================
def _read_json():
    if not DATA_FILE.exists():
        return []
    try:
        with DATA_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    except json.JSONDecodeError:
        print("警告: JSONファイルが破損しているため、空のリストとして扱います。")
        return []

def _write_json(data):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True) # フォルダがない場合の保険
    with DATA_FILE.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, default=json_fallback)

# ==========================================
# List Management
# ==========================================
def update_list(item_uid, new_name=None, new_data=None):
    if IS_UPDATING:
        return

    current_data = _read_json()
    found = False

    for entry in current_data:
        if entry.get("uid") == item_uid:
            if new_name:
                entry["name"] = new_name
            if new_data:
                entry["node_data"] = new_data # 辞書としてそのまま保存
            found = True
            break

    if found:
        _write_json(current_data)
        load_from_json()

def update_name_in_json(self, context):
    update_list(self.uid, new_name=self.name)

def update_data_in_json(item, data):
    update_list(item.uid, new_data=data)

def load_from_json():
    data = _read_json()
    wm = bpy.context.window_manager

    with prevent_update():
        wm.global_list.clear()
        for d in data:
            item = wm.global_list.add()
            item.uid = d.get("uid", "")
            item.name = d.get("name", "Nodes")
            
            node_data_content = d.get("node_data", {})
            item.node_data = json.dumps(node_data_content) if isinstance(node_data_content, dict) else str(node_data_content)

def store_to_json():
    wm = bpy.context.window_manager
    data_list = []

    for item in wm.global_list:
        parsed_node_data = {}
        if item.node_data:
            try:
                parsed_node_data = json.loads(item.node_data)
            except json.JSONDecodeError:
                pass

        data_list.append({
            "uid": item.uid,
            "name": item.name,
            "node_data": parsed_node_data
        })
    
    _write_json(data_list)

def json_fallback(obj):
    """JSONが理解できない型（Vector, Colorなど）に遭遇した時の自動変換関数"""
    
    # BlenderのVector, Color, Euler, Matrix ならリストに変換
    if isinstance(obj, (mathutils.Vector, mathutils.Color, mathutils.Euler, mathutils.Matrix)):
        return list(obj)
    
    # その他の反復可能オブジェクトも念のためリスト化
    if hasattr(obj, '__iter__') and not isinstance(obj, str):
        return list(obj)
    
    # どうしても変換できない未知の型は、エラーで落ちるのを防ぐため文字列にする
    return str(obj)


# ==========================================
# Serialization Helpers
# ==========================================
TARGET_PROPS = {
    "operation", "blend_type", "data_type", "mode", "distribution", 
    "subsurface_method", "noise_dimensions", "noise_type", "normalize", 
    "feature", "distance", "use_clamp", "clamp_result", "clamp_factor", 
    "interpolation", "interpolation_type", "color_mode", "wave_type", 
    "wave_profile", "rings_direction", "projection", "extension"
}

def _parse_socket_val(val):
    """VectorやColorなどの反復可能オブジェクトをリストに変換する安全な関数"""
    if hasattr(val, '__iter__') and not isinstance(val, str):
        return list(val)
    return val

def _serialize_special_node(node):
    """特殊ノード（ランプ、カーブ、画像、グループ）の個別処理"""
    if node.bl_idname == 'ShaderNodeValToRGB':
        ramp = node.color_ramp
        return {
            "type": "ramp",
            "data": {
                "color_mode": ramp.color_mode,
                "interpolation": ramp.interpolation,
                "elements": [{"position": e.position, "color": list(e.color)} for e in ramp.elements]
            }
        }
    
    elif node.bl_idname in ('ShaderNodeRGBCurve', 'ShaderNodeVectorCurve'):
        mapping = node.mapping
        return {
            "type": "curve",
            "data": {
                "clip_min_x": mapping.clip_min_x, "clip_min_y": mapping.clip_min_y,
                "clip_max_x": mapping.clip_max_x, "clip_max_y": mapping.clip_max_y,
                "use_clip": mapping.use_clip,
                "curves": [[{"location": (p.location.x, p.location.y), "handle_type": p.handle_type} 
                            for p in curve.points] for curve in mapping.curves]
            }
        }
        
    elif node.bl_idname == 'ShaderNodeTexImage' and node.image:
        img = node.image
        return {
            "type": "image",
            "data": {
                "image_name": img.name,
                "filepath": img.filepath,
                "color_space": getattr(img.colorspace_settings, "name", "sRGB"),
                "source": img.source,
                "alpha_mode": img.alpha_mode
            }
        }
        
    elif node.type == 'GROUP' and node.node_tree:
        return {
            "type": "group",
            "data": {
                "tree_name": node.node_tree.name,
                "tree_type": node.node_tree.bl_idname,
                "node_data": SerializeNodes(bpy.context, node.node_tree) # 再帰呼び出し
            }
        }
    return None

# ==========================================
# Core Serialization / Deserialization
# ==========================================
def SerializeNodes(context, childTree=None):
    tree = childTree or getattr(context.space_data, "edit_tree", None) or context.space_data.node_tree
    nodes = tree.nodes if childTree else context.selected_nodes
    sel_names = {n.name for n in nodes} # in検索を高速化するためにSetを利用

    data = {"nodes": [], "links": []}

    # Groupのインターフェース保存
    if childTree and hasattr(tree, "interface"):
        data["interface"] = {"inputs": [], "outputs": []}
        for item in getattr(tree.interface, "items_tree", []):
            if item.item_type != 'SOCKET': continue
            
            sock_data = {
                "name": item.name, 
                "type": item.socket_type, 
                "default_value": _parse_socket_val(getattr(item, "default_value", None))
            }
            if item.in_out == 'INPUT': data["interface"]["inputs"].append(sock_data)
            elif item.in_out == 'OUTPUT': data["interface"]["outputs"].append(sock_data)

    # ノード情報の取得
    for node in nodes:
        node_data = {
            "name": node.name,
            "type": node.bl_idname,
            "location": (node.location.x, node.location.y),
            "width": node.width,
            "properties": {p: _parse_socket_val(getattr(node, p)) for p in TARGET_PROPS if hasattr(node, p)},
            "inputs": [{"index": i, "value": _parse_socket_val(s.default_value)} 
                       for i, s in enumerate(node.inputs) if not s.is_linked and hasattr(s, "default_value")],
            "outputs": [{"index": i, "value": _parse_socket_val(s.default_value)} 
                        for i, s in enumerate(node.outputs) if hasattr(s, "default_value")]
        }
        
        special = _serialize_special_node(node)
        if special:
            node_data["special_data"] = special
            
        data["nodes"].append(node_data)

    # リンク情報の取得
    for link in tree.links:
        if link.from_node.name in sel_names and link.to_node.name in sel_names:
            from_idx = next((i for i, s in enumerate(link.from_node.outputs) if s == link.from_socket), -1)
            to_idx = next((i for i, s in enumerate(link.to_node.inputs) if s == link.to_socket), -1)
            
            if from_idx != -1 and to_idx != -1:
                data["links"].append({
                    "from_node": link.from_node.name,
                    "from_socket_index": from_idx,
                    "to_node": link.to_node.name,
                    "to_socket_index": to_idx
                })

    return data

# ==========================================
# Deserialization Helpers (Internal)
# ==========================================

def _restore_socket_values(node, data_list, socket_type='inputs'):
    """ソケットのデフォルト値を復元する"""
    sockets = getattr(node, socket_type)
    for s_data in data_list:
        idx = s_data.get("index")
        val = s_data.get("value")
        if idx is not None and idx < len(sockets):
            try:
                sockets[idx].default_value = val
            except Exception:
                pass

def _restore_color_ramp(node, s_data):
    """ColorRamp（カラーランプ）の復元"""
    ramp = getattr(node, "color_ramp", None)
    if not ramp: return
    
    ramp.color_mode = s_data.get("color_mode", 'RGB')
    ramp.interpolation = s_data.get("interpolation", 'LINEAR')
    
    elements = s_data.get("elements", [])
    # 要素数を合わせる
    while len(ramp.elements) < len(elements): ramp.elements.new(1.0)
    while len(ramp.elements) > len(elements): ramp.elements.remove(ramp.elements[-1])
    
    for i, e_data in enumerate(elements):
        ramp.elements[i].position = e_data["position"]
        ramp.elements[i].color = e_data["color"]

def _restore_curves(node, s_data):
    """RGB/Vector Curve（カーブ）の復元"""
    mapping = getattr(node, "mapping", None)
    if not mapping: return
    
    mapping.clip_min_x = s_data.get("clip_min_x", 0.0)
    mapping.clip_min_y = s_data.get("clip_min_y", 0.0)
    mapping.clip_max_x = s_data.get("clip_max_x", 1.0)
    mapping.clip_max_y = s_data.get("clip_max_y", 1.0)
    mapping.use_clip = s_data.get("use_clip", False)
    
    for i, p_list in enumerate(s_data.get("curves", [])):
        if i >= len(mapping.curves): break
        curve = mapping.curves[i]
        # 点の数を合わせる
        while len(curve.points) < len(p_list): curve.points.new(0.0, 0.0)
        while len(curve.points) > len(p_list): curve.points.remove(curve.points[-1])
        
        for j, p_data in enumerate(p_list):
            p = curve.points[j]
            p.location = p_data["location"]
            p.handle_type = p_data.get("handle_type", 'AUTO')
    
    if hasattr(mapping, "update"): mapping.update()

def _restore_image(self, node, s_data):
    """Image Texture（画像）の復元"""
    img_name = s_data.get("image_name")
    filepath = s_data.get("filepath", "")
    
    image = bpy.data.images.get(img_name) if img_name else None
    
    if not image and filepath:
        try:
            image = bpy.data.images.load(filepath, check_existing=True)
        except RuntimeError:
            self.report({'WARNING'}, f"画像のロードに失敗: {filepath}")
            
    if image:
        node.image = image
        if "color_space" in s_data and hasattr(image, "colorspace_settings"):
            image.colorspace_settings.name = s_data["color_space"]

def _restore_node_group(self, context, node, s_data):
    """Node Group（グループ）の復元と再帰的展開"""
    tree_name = s_data.get("tree_name")
    if not tree_name: return
    
    group = bpy.data.node_groups.get(tree_name)
    if not group:
        # 新規グループ作成とインターフェース構築
        group_type = s_data.get("tree_type", "ShaderNodeTree")
        group = bpy.data.node_groups.new(name=tree_name, type=group_type)
        
        inner_data = s_data.get("node_data", {})
        interface = inner_data.get("interface", {})
        
        if hasattr(group, "interface"):
            for sock in interface.get("inputs", []):
                s = group.interface.new_socket(name=sock["name"], in_out='INPUT', socket_type=sock["type"])
                if "default_value" in sock and hasattr(s, "default_value"):
                    s.default_value = sock["default_value"]
            for sock in interface.get("outputs", []):
                group.interface.new_socket(name=sock["name"], in_out='OUTPUT', socket_type=sock["type"])
        
        # 再帰的に中身を展開
        DeserializeNodes(self, context, inner_data, iTree=group)
        
    node.node_tree = group

# ==========================================
# Main Deserialization Function
# ==========================================

def DeserializeNodes(self, context, data, iTree=None):
    # ツリーの決定
    tree = iTree or getattr(context.space_data, "edit_tree", None) or context.space_data.node_tree
    if not tree: return {'CANCELLED'}

    # 既存の選択を解除
    for n in tree.nodes: n.select = False

    node_map = {}
    node_list = data.get("nodes", [])

    # 1. ノードの作成と基本プロパティの復元
    for n_data in node_list:
        try:
            new_node = tree.nodes.new(n_data["type"])
        except RuntimeError:
            self.report({'ERROR'}, f"ノードタイプが見つかりません: {n_data['type']}")
            continue

        new_node.location = n_data.get("location", (0, 0))
        new_node.width = n_data.get("width", 140)
        new_node.select = True
        node_map[n_data["name"]] = new_node

        # 基本プロパティの一括復元
        for prop, val in n_data.get("properties", {}).items():
            if hasattr(new_node, prop):
                try: setattr(new_node, prop, val)
                except Exception: pass

        # ソケット値の復元
        _restore_socket_values(new_node, n_data.get("inputs", []), 'inputs')
        _restore_socket_values(new_node, n_data.get("outputs", []), 'outputs')

        # 特殊データの復元（切り出した関数へ委譲）
        special = n_data.get("special_data")
        if special:
            stype = special.get("type")
            sdata = special.get("data", {})
            if stype == "ramp": _restore_color_ramp(new_node, sdata)
            elif stype == "curve": _restore_curves(new_node, sdata)
            elif stype == "image": _restore_image(self, new_node, sdata)
            elif stype == "group": _restore_node_group(self, context, new_node, sdata)

    # 2. リンクの復元
    for l_data in data.get("links", []):
        try:
            node_from = node_map.get(l_data["from_node"])
            node_to = node_map.get(l_data["to_node"])
            if not node_from or not node_to: continue

            socket_out = node_from.outputs[l_data["from_socket_index"]]
            socket_in = node_to.inputs[l_data["to_socket_index"]]
            tree.links.new(socket_out, socket_in)
        except (IndexError, KeyError):
            pass

    return {'FINISHED'}