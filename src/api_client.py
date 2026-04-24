import os
import requests
from dotenv import load_dotenv

load_dotenv()

CANVAS_DOMAIN = os.getenv("CANVAS_API_DOMAIN")
API_TOKEN = os.getenv("CANVAS_API_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}"
}

def _get_paginated(url):
    """
    Handle Canvas API pagination using the 'Link' header.
    Yields JSON responses page by page.
    """
    while url:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        yield response.json()
        
        # Check the 'Link' header for a 'next' relationship
        if 'next' in response.links:
            url = response.links['next']['url']
        else:
            url = None

def list_courses():
    """
    Fetch all active courses for the authenticated user.
    Endpoint: /api/v1/courses
    """
    url = f"{CANVAS_DOMAIN}/api/v1/courses"
    courses = []
    for page in _get_paginated(url):
        courses.extend(page)
    return courses

def get_course_modules(course_id):
    """
    Fetch all modules for a given course.
    Endpoint: /api/v1/courses/{course_id}/modules
    """
    url = f"{CANVAS_DOMAIN}/api/v1/courses/{course_id}/modules"
    modules = []
    for page in _get_paginated(url):
        modules.extend(page)
    return modules

def get_module_items(course_id, module_id):
    """
    Fetch all items within a specific module.
    Endpoint: /api/v1/courses/{course_id}/modules/{module_id}/items
    """
    url = f"{CANVAS_DOMAIN}/api/v1/courses/{course_id}/modules/{module_id}/items"
    items = []
    for page in _get_paginated(url):
        items.extend(page)
    return items

def get_file_info(file_id):
    """
    Fetch metadata for a specific file.
    Endpoint: /api/v1/files/{file_id}
    """
    url = f"{CANVAS_DOMAIN}/api/v1/files/{file_id}"
    response = requests.get(url, headers=HEADERS)
    response.raise_for_status()
    return response.json()

def download_file(file_url, output_path):
    """
    Download a file from Canvas using the API token and save it locally.
    Uses a temporary file to ensure atomic completion.
    """
    tmp_path = output_path + ".tmp"
    try:
        with requests.get(file_url, headers=HEADERS, stream=True) as r:
            r.raise_for_status()
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(tmp_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        # Rename tmp file to final destination on success
        if os.path.exists(output_path):
            os.remove(output_path)
        os.rename(tmp_path, output_path)
        return True
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise e
