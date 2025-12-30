import bpy
import os
import json
from contextlib import contextmanager

IS_UPDATING = False

@contextmanager
def prevent_update():
    global IS_UPDATING
    IS_UPDATING = True
    try:
        yield
    finally:
        IS_UPDATING = False

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "global_list_data.json")

def update_list(item_uid, new_name = None, new_data = None):
    if IS_UPDATING:
        return

    current_data = []
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                current_data = json.load(f)
        except:
            current_data = []
    
    found = False
    for entry in current_data:
        if entry.get("uid") == item_uid:
            if new_name:
                entry["name"] = new_name
            if new_data:
                entry["node_data"] = json.dumps(new_data, separators=(',', ':'))
            found = True
            break

    if found:
        with open(DATA_FILE, 'w') as f:
            json.dump(current_data, f, indent=4)
        load_from_json()
    else:
        pass

def update_name_in_json(self, context):
    update_list(self.uid, new_name=self.name)

def update_data_in_json(item, data):
    update_list(item.uid, new_data = data)

def load_from_json():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)

            wm = bpy.context.window_manager

            with prevent_update():
                wm.global_list.clear()

                for d in data:
                    item = wm.global_list.add()
                    item.uid = d["uid"]
                    item.name = d["name"]
                    item.node_data = d["node_data"]

        except json.JSONDecodeError:
            print("ファイルの中身は壊れている")

        finally:
            IS_UPDATING = False

def store_to_json():
    wm = bpy.context.window_manager

    data_list = []

    for item in wm.global_list:
        data = {
            "uid": item.uid,
            "name": item.name,
            "node_data": item.node_data
        }
        
        data_list.append(data)

    
    with open(DATA_FILE, 'w') as f:
        json.dump(data_list, f, indent=4)

def SerializeNodes(context):
    nodes = context.selected_nodes
    tree = context.space_data.edit_tree
    if tree is None:
        tree = context.space_data.node_tree

    data = {
        "node": [],
        "links": []
    }

    sel_names = [n.name for n in nodes]

    target_props = [
        "operation",        # Math, Vector Math, Boolean
        "blend_type",       # Mix Node
        "data_type",        # Mix Node (Float/Vector/Color...)
        "mode",             # Map Range
        "distribution",     # Brick Texture, Voronoi
        "subsurface_method", # Principled BSDF
        "noise_dimensions", # Noise Texture (2D/3D/4D)
        "noise_type",       # Noise Texture (fBM...)
        "normalize",        # Noise Texture (normalize)
        "feature",          # Voronoi (F1, F2...)
        "distance",         # Voronoi (Euclidean...)
        "use_clamp",        # Math Node Checkbox
        "clamp_result",     # Mix Node Checkbox
        "clamp_factor",     # Mix Node Checkbox (Old)
        "interpolation_type", # Map Range
        "color_mode",       # Gradient Texture
        "wave_type",        # Wave Texture
        "wave_profile",     # Wave Texture
        "rings_direction",  # Wave Texture
    ]

    for node in nodes:
        node_data = {
            "name": node.name,
            "id": node.bl_idname,
            "location": (node.location.x, node.location.y),
            "width": node.width,
            "inputs": [],
            "properties": {}
        }

        for prop_name in target_props:
            if hasattr(node, prop_name):
                val = getattr(node, prop_name)
                node_data["properties"][prop_name] = val

        for i, sock in enumerate(node.inputs):
            if not sock.is_linked and hasattr(sock, "default_value"):
                val = sock.default_value

                try:
                    val = list(val)
                except:
                    pass

                node_data["inputs"].append({"index": i, "value": val})

        if node.bl_idname == 'ShaderNodeValToRGB':
            ramp = node.color_ramp
            ramp_data = {
                "color_mode": ramp.color_mode,
                "interpolation": ramp.interpolation,
                "elements": []
            }
            for elt in ramp.elements:
                ramp_data["elements"].append({
                    "position": elt.position,
                    "color": list(elt.color)
                })
            node_data["special_data"] = {
                "type": "ramp",
                "data": ramp_data
            }
        elif node.bl_idname in ('ShaderNodeRGBCurve', 'ShaderNodeVectorCurve'):
            curve_mapping = node.mapping
            curve_data = {
                "curves": []
            }

            for curve in curve_mapping.curves:
                point_data = []
                for p in curve.points:
                    point_data.append({
                        "location": (p.location.x, p.location.y),
                        "handle_type": p.handle_type
                    })
                curve_data["curves"].append(point_data)

            curve_data["clip_min_x"] = curve_mapping.clip_min_x
            curve_data["clip_min_y"] = curve_mapping.clip_min_y
            curve_data["clip_max_x"] = curve_mapping.clip_max_x
            curve_data["clip_max_y"] = curve_mapping.clip_max_y
            curve_data["use_clip"] = curve_mapping.use_clip
                
            node_data["special_data"] = {
                "type": "curve",
                "data": curve_data
            }

        data["node"].append(node_data)
    

    for link in tree.links:
        if link.from_node.name in sel_names and link.to_node.name in sel_names:
            link_data = {
                "from_node": link.from_node.name,
                "from_socket_index": -1,
                "to_node": link.to_node.name,
                "to_socket_index": -1
            }

            for i, sock in enumerate(link.from_node.outputs):
                if sock == link.from_socket:
                    link_data["from_socket_index"] = i
                    break
            
            for i, sock in enumerate(link.to_node.inputs):
                if sock == link.to_socket:
                    link_data["to_socket_index"] = i
                    break
            
            data["links"].append(link_data)

    return data


def DeserializeNodes(context, data):
    tree = context.space_data.edit_tree
    if tree is None:
        tree = context.space_data.node_tree

    for n in tree.nodes:
        n.select = False

    node_map = {}

    node_list = data.get("node", [])

    for n_data in node_list:
        new_node = tree.nodes.new(n_data["id"])
        new_node.location = n_data["location"]
        new_node.width = n_data["width"]
        new_node.select = True

        node_map[n_data["name"]] = new_node

        for prop, val in n_data["properties"].items():
            if hasattr(new_node, prop):
                try:
                    setattr(new_node,prop,val)
                except:
                    print(f"Property Error: {prop}")
        
        for inp in n_data["inputs"]:
            idx = inp["index"]
            val = inp["value"]

            if idx < len(new_node.inputs):
                try:
                    new_node.inputs[idx].default_value = val
                except:
                    pass

        special = n_data.get("special_data")

        if special:
            sType = special["type"]
            sData = special["data"]

            if sType == "ramp" and hasattr(new_node, "color_ramp"):
                ramp = new_node.color_ramp
                ramp.color_mode = sData.get("color_mode", 'RGB')
                ramp.interpolation = sData.get("interpolation", 'LINEAR')

                elements_data = sData.get("elements", [])

                current_len = len(ramp.elements)
                target_len = len(elements_data)

                if current_len < target_len:
                    for _ in range(target_len - current_len):
                        ramp.elements.new(1.0)
                elif current_len > target_len:
                    for i in range(current_len - 1 , target_len - 1, -1):
                        ramp.elements.remove(ramp.elements[i])

                for i, elt_d in enumerate(elements_data):
                    elt = ramp.elements[i]
                    elt.position = elt_d["position"]
                    elt.color = elt_d["color"]

            elif sType == "curve" and hasattr(new_node, "mapping"):
                mapping = new_node.mapping
                mapping.clip_min_x = sData.get("clip_min_x", 0.0)
                mapping.clip_min_y = sData.get("clip_min_y", 0.0)
                mapping.clip_max_x = sData.get("clip_max_x", 1.0)
                mapping.clip_max_y = sData.get("clip_max_y", 1.0)
                mapping.use_clip = sData.get("use_clip", False)

                saved_curve = sData.get("curves", [])

                for i, points_list in enumerate(saved_curve):
                    if i >= len(mapping.curves):
                        break

                    curve = mapping.curves[i]

                    target_len = len(points_list)
                    current_len = len(curve.points)

                    if target_len > current_len:
                        for _ in range(target_len - current_len):
                            curve.points.new(0.0, 0.0)
                    elif target_len < current_len:
                         for k in range(current_len - 1, target_len - 1, -1):
                            curve.points.remove(curve.points[k])

                    for j, p_data in enumerate(points_list):
                        p = curve.points[j]
                        p.location.x = p_data["location"][0]
                        p.location.y = p_data["location"][1]
                        p.handle_type = p_data.get("handle_type", 'AUTO')

                if hasattr(mapping, "update"):
                    mapping.update()

    

    for l_data in data["links"]:
        try:
            node_from = node_map[l_data["from_node"]]
            node_to = node_map[l_data["to_node"]]

            socket_out = node_from.outputs[l_data["from_socket_index"]]
            socket_in = node_to.inputs[l_data["to_socket_index"]]

            tree.links.new(socket_out, socket_in)

        except KeyError:
            print("Link Error: Node mapping failed")
        except IndexError:
            print("Link Error: Socket index mismatch")

    return {'FINISHED'}