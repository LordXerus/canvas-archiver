import os
import re
import sys
from datetime import datetime
from api_client import list_courses, get_course_modules, get_module_items, get_file_info, download_file
from playwright_client import download_with_browser
from manifest import Manifest

def sanitize_filename(name):
    """
    Remove invalid characters from module/file names to use safely in filesystem paths.
    """
    if not name:
        return "Unnamed"
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()

def get_target_path(base_dir, current_save_path, item_title, file_info, manifest):
    """
    Determine the final output path using the naming strategy:
    1. Title + Ext
    2. Title (Canvas Filename) + Ext
    3. Title (Canvas ID) + Ext
    """
    canvas_filename = file_info.get('filename', '')
    canvas_id = str(file_info.get('id', ''))
    _, ext = os.path.splitext(canvas_filename)
    
    clean_title = sanitize_filename(item_title)
    
    # Ensure extension is present
    if not clean_title.lower().endswith(ext.lower()):
        base_name = clean_title + ext
    else:
        base_name = clean_title
        
    # Collision candidates
    name_no_ext = os.path.splitext(base_name)[0]
    candidates = [
        base_name,
        f"{name_no_ext} ({canvas_filename})", # User said "append raw canvas name"
        f"{name_no_ext} ({canvas_id}){ext}"
    ]
    
    for candidate in candidates:
        full_path = os.path.join(current_save_path, candidate)
        rel_path = os.path.relpath(full_path, base_dir)
        
        # Check if this path is taken by a DIFFERENT ID
        existing_entry, existing_id = manifest.get_file_by_path(rel_path)
        if existing_id is None or str(existing_id) == str(canvas_id):
            return full_path, rel_path
            
    # Final fallback
    final_name = f"{name_no_ext} ({canvas_id}){ext}"
    full_path = os.path.join(current_save_path, final_name)
    return full_path, os.path.relpath(full_path, base_dir)

def find_target_course():
    """
    Automatically search for the MAT 201 course.
    """
    try:
        courses = list_courses()
    except Exception as e:
        return None, f"Failed to list courses: {e}"

    candidates = []
    for c in courses:
        # Match against name or course_code
        name = c.get('name', '').upper()
        code = c.get('course_code', '').upper()
        
        # Logic: (ECE AND 447) AND (LEC)
        has_keywords = ('MAT' in name and '201' in name) or ('MAT' in code and '201' in code)
        is_lec = 'LEC' in name or 'LEC' in code
        
        if has_keywords: # and not is_lec:
            candidates.append(c)
    
    if not candidates:
        return None, "No courses found matching (MAT/201)."
    
    if len(candidates) > 1:
        # If we have multiple matches, list them and stop for safety
        match_list = "\n".join([f"- {c.get('name')} (ID: {c.get('id')})" for c in candidates])
        return None, f"Ambiguous course matches found:\n{match_list}\nPlease specify a COURSE_ID in .env."

    return candidates[0], None

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def ask_user(prompt_msg):
    """
    Prompt the user for input with colored text.
    """
    is_interactive = os.getenv("SCRAPE_INTERACTIVE", "True").lower() == "true"
    if not is_interactive:
        return True

    while True:
        choice = input(f"{YELLOW}{BOLD}[PROMPT]{RESET} {prompt_msg} (y/n/abort): ").lower().strip()
        if choice == 'y':
            return True
        if choice == 'n':
            return False
        if choice == 'abort':
            print(f"{RED}Aborting scrape as requested.{RESET}")
            sys.exit(0)
        print("Please enter 'y', 'n', or 'abort'.")

def main():
    course_id = os.getenv("COURSE_ID")
    course_name = "Unknown Course"

    if not course_id:
        print("Course ID not found in .env. Attempting discovery...")
        course, error = find_target_course()
        if error:
            print(f"Discovery Error: {error}")
            return
        course_id = course['id']
        course_name = course.get('name', f"Course_{course_id}")
        print(f"Discovered course: {course_name} (ID: {course_id})")
    else:
        print(f"Using COURSE_ID from .env: {course_id}")

    print(f"Starting Canvas Scraper...")
    
    try:
        modules = get_course_modules(course_id)
        print(f"Found {len(modules)} modules.")
    except Exception as e:
        print(f"Error: Failed to fetch modules. Details: {e}")
        return

    # Base directory: downloads/{Sanitized Course Name}/
    sanitized_course = sanitize_filename(course_name)
    base_dir = os.path.join("downloads", sanitized_course)
    os.makedirs(base_dir, exist_ok=True)

    # Initialize Manifest
    manifest = Manifest(base_dir)
    manifest.data['course_id'] = course_id

    for module in modules:
        module_name = sanitize_filename(module.get('name', 'Unnamed Module'))
        module_id = module.get('id')
        print(f"\n{BLUE}{BOLD}--- {module_name} ---{RESET}")
        
        module_path = os.path.join(base_dir, module_name)
        os.makedirs(module_path, exist_ok=True)
        
        try:
            items = get_module_items(course_id, module_id)
        except Exception as e:
            print(f"  {RED}Error fetching items for {module_name}: {e}{RESET}")
            continue

        # Keep track of current submodule path (Canvas SubHeaders)
        current_save_path = module_path

        for item in items:
            item_type = item.get('type')
            
            if item_type == 'SubHeader':
                # Create a sub-directory for the submodule
                submodule_name = sanitize_filename(item.get('title', 'Submodule'))
                current_save_path = os.path.join(module_path, submodule_name)
                os.makedirs(current_save_path, exist_ok=True)
                print(f"  {BLUE}[{submodule_name}]{RESET}")
            
            elif item_type == 'File':
                item_title = item.get('title', 'Unknown_File')
                content_id = item.get('content_id')
                
                if not content_id:
                    continue
                
                # Metadata fetch
                try:
                    file_info = get_file_info(content_id)
                    remote_updated = file_info.get('updated_at')
                    remote_size = file_info.get('size')
                    download_url = file_info.get('url')
                except Exception as e:
                    print(f"      {RED}Metadata error for ID {content_id}: {e}. Skipping.{RESET}")
                    continue

                output_path, rel_path = get_target_path(base_dir, current_save_path, item_title, file_info, manifest)
                file_name = os.path.basename(output_path)
                
                print(f"    [Processing] {file_name} (ID: {content_id})...")
                
                # Hypotheses checks
                entry = manifest.get_file(content_id)
                needs_download = False
                
                if entry:
                    # Check for path migration (naming strategy update)
                    old_rel_path = entry.get('local_path')
                    if old_rel_path and old_rel_path != rel_path:
                        old_abs_path = os.path.join(base_dir, old_rel_path)
                        if os.path.exists(old_abs_path):
                            print(f"{YELLOW}      [MIGRATION] Naming strategy suggests: {rel_path}{RESET}")
                            print(f"      Current path: {old_rel_path}")
                            if ask_user(f"Rename local file to follow new naming scheme?"):
                                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                                os.rename(old_abs_path, output_path)
                                entry['local_path'] = rel_path
                                manifest.save()
                    
                    # Hypothesis B: Same ID -> Same Updated At (One ID = One Version)
                    if entry.get('updated_at') != remote_updated:
                        print(f"{RED}{BOLD}      [HYPOTHESIS B BROKEN] ID {content_id} timestamp changed!{RESET}")
                        print(f"      Manifest: {entry.get('updated_at')}")
                        print(f"      Remote:   {remote_updated}")
                        if ask_user(f"ID {content_id} ('{file_name}') has new timestamp. Archive old and re-download?"):
                            manifest.archive_file(os.path.join(base_dir, entry['local_path']), content_id, entry.get('updated_at'))
                            needs_download = True
                        else:
                            print(f"      {YELLOW}Skipping update per user request.{RESET}")
                            continue
                    
                    # Hypothesis A: Same ID & Same Timestamp -> Same Size
                    elif entry.get('size') != remote_size:
                        print(f"{RED}{BOLD}      [HYPOTHESIS A BROKEN] ID {content_id} size changed but timestamp is IDENTICAL!{RESET}")
                        print(f"      Manifest Size: {entry.get('size')}")
                        print(f"      Remote Size:   {remote_size}")
                        if ask_user(f"ID {content_id} size mismatch for identical timestamp. Re-download?"):
                            needs_download = True
                        else:
                            print(f"      {YELLOW}Skipping re-download per user request.{RESET}")
                            continue
                    
                    else:
                        # Hypotheses passed. Check local file existence/size for physical integrity.
                        if os.path.exists(output_path):
                            local_size = os.path.getsize(output_path)
                            if local_size == remote_size:
                                print(f"      {GREEN}[Up-to-date]{RESET}")
                                continue
                            else:
                                print(f"{RED}{BOLD}      [WARNING] Local size mismatch! Remote: {remote_size}, Local: {local_size}{RESET}")
                                if ask_user(f"Physical file '{file_name}' size mismatch. Re-download?"):
                                    needs_download = True
                        else:
                            print(f"      {YELLOW}[Missing] File not found at {rel_path}.{RESET}")
                            needs_download = True
                else:
                    # New ID to manifest. Check if path is taken (implies ID swap for this item)
                    existing_entry, existing_id = manifest.get_file_by_path(rel_path)
                    if existing_entry:
                        print(f"{YELLOW}{BOLD}      [ID SWAP] Path {rel_path} now points to NEW ID {content_id}.{RESET}")
                        print(f"      Old ID: {existing_id} ({existing_entry.get('updated_at')})")
                        print(f"      New ID: {content_id} ({remote_updated})")
                        # Auto-archive per request: "New ID and new timestamp -> auto archive and update"
                        manifest.archive_file(output_path, existing_id, existing_entry.get('updated_at'))
                        needs_download = True
                    else:
                        needs_download = True

                if needs_download:
                    print(f"      {BOLD}[Downloading]{RESET} {file_name}...")
                    
                    # Capture full metadata
                    full_metadata = {k: v for k, v in file_info.items() if k not in ['url']}
                    full_metadata['item_title'] = item_title
                    
                    # Update manifest to STARTED
                    manifest.update_file(content_id, {
                        "canvas_id": content_id,
                        "local_path": rel_path,
                        "updated_at": remote_updated,
                        "size": remote_size,
                        "status": "STARTED",
                        "downloaded_at": None,
                        "metadata": full_metadata
                    })

                    try:
                        if download_file(download_url, output_path):
                            print(f"      {GREEN}Done.{RESET}")
                            manifest.update_file(content_id, {
                                "canvas_id": content_id,
                                "local_path": rel_path,
                                "updated_at": remote_updated,
                                "size": remote_size,
                                "status": "FINISHED",
                                "downloaded_at": datetime.now().isoformat(),
                                "metadata": full_metadata
                            })
                    except Exception as api_err:
                        print(f"      {YELLOW}API failed: {api_err}. Trying Playwright...{RESET}")
                        try:
                            if download_with_browser(download_url, output_path):
                                print(f"      {GREEN}Done (via browser).{RESET}")
                                manifest.update_file(content_id, {
                                    "canvas_id": content_id,
                                    "local_path": rel_path,
                                    "updated_at": remote_updated,
                                    "size": remote_size,
                                    "status": "FINISHED",
                                    "downloaded_at": datetime.now().isoformat(),
                                    "metadata": full_metadata
                                })
                            else:
                                print(f"      {RED}[FAIL] {file_name}{RESET}")
                        except Exception as pw_err:
                            print(f"      {RED}[ERROR] {pw_err}{RESET}")

    manifest.data['last_full_scrape'] = datetime.now().isoformat()
    manifest.save()
    print(f"\n{GREEN}{BOLD}Scraping complete!{RESET}")

    print("\nScraping complete!")

if __name__ == "__main__":
    main()
