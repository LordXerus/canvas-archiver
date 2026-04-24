import os
import json
import shutil
from datetime import datetime

class Manifest:
    def __init__(self, course_dir):
        self.course_dir = course_dir
        self.manifest_path = os.path.join(course_dir, 'manifest.json')
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.manifest_path):
            try:
                with open(self.manifest_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Warning: Could not load manifest: {e}")
        
        return {
            "course_id": None,
            "last_full_scrape": None,
            "files": {}
        }

    def save(self):
        os.makedirs(self.course_dir, exist_ok=True)
        with open(self.manifest_path, 'w') as f:
            json.dump(self.data, f, indent=2)

    def get_file(self, canvas_id):
        return self.data['files'].get(str(canvas_id))

    def update_file(self, canvas_id, metadata):
        self.data['files'][str(canvas_id)] = metadata
        self.save()

    def get_file_by_path(self, local_path):
        """
        Find an existing file entry by its relative local path.
        Returns the entry and its ID, or (None, None).
        """
        for cid, entry in self.data['files'].items():
            if entry.get('local_path') == local_path:
                return entry, cid
        return None, None

    def archive_file(self, local_path, canvas_id, old_updated_at):
        """
        Move a file to the _old directory with a unique name.
        """
        if not os.path.exists(local_path):
            return

        module_dir = os.path.dirname(local_path)
        old_dir = os.path.join(module_dir, '_old')
        os.makedirs(old_dir, exist_ok=True)

        filename = os.path.basename(local_path)
        # Format: {canvas_id}_{timestamp}_{filename}
        # Replace : with - to be safe on all filesystems
        ts = old_updated_at.replace(':', '-') if old_updated_at else datetime.now().strftime("%Y%m%d-%H%M%S")
        archived_name = f"{canvas_id}_{ts}_{filename}"
        archived_path = os.path.join(old_dir, archived_name)

        # Handle collisions
        counter = 1
        base_name, ext = os.path.splitext(archived_path)
        while os.path.exists(archived_path):
            archived_path = f"{base_name}_v{counter}{ext}"
            counter += 1

        print(f"      Archiving old version to: {os.path.relpath(archived_path, self.course_dir)}")
        shutil.move(local_path, archived_path)
        return archived_path
