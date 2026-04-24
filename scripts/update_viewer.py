import os
import json
import re

def get_directory_structure(root_dir):
    """
    Recursively builds a directory structure for HTML files.
    """
    structure = []
    
    # Sort directories and files for consistent output
    items = sorted(os.listdir(root_dir))
    
    for item in items:
        if item.startswith('.') or item == 'node_modules':
            continue
            
        path = os.path.join(root_dir, item)
        # Use relative path from the project root for the viewer to handle link generation
        # We assume export_viewer.html is in the project root.
        rel_path = os.path.relpath(path, start=os.getcwd())
        
        if os.path.isdir(path):
            children = get_directory_structure(path)
            if children:  # Only add directories that contain HTML files (directly or indirectly)
                structure.append({
                    "name": item,
                    "type": "directory",
                    "path": rel_path,
                    "children": children
                })
        elif item.lower().endswith('.html'):
            structure.append({
                "name": item,
                "type": "file",
                "path": rel_path
            })
            
    return structure

def update_viewer():
    exports_dir = os.path.join(os.getcwd(), 'exports', 'html')
    if not os.path.exists(exports_dir):
        print(f"Error: {exports_dir} does not exist.")
        return

    data = get_directory_structure(exports_dir)
    json_data = json.dumps(data, indent=2)
    
    viewer_path = os.path.join(os.getcwd(), 'export_viewer.html')
    
    if not os.path.exists(viewer_path):
        print("Viewer HTML not found. Please create it first.")
        return

    with open(viewer_path, 'r') as f:
        content = f.read()

    # Look for a script tag with id="file-data" and replace its content
    pattern = r'(<script id="file-data" type="application/json">)(.*?)(</script>)'
    replacement = f'\\1\n{json_data}\n\\3'
    
    if re.search(pattern, content, re.DOTALL):
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        with open(viewer_path, 'w') as f:
            f.write(new_content)
        print(f"Successfully updated file list in {viewer_path}")
    else:
        print("Could not find <script id=\"file-data\"> block in export_viewer.html")

if __name__ == "__main__":
    update_viewer()
