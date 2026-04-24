import os
from playwright.sync_api import sync_playwright

def download_with_browser(url, output_path):
    """
    Fallback method to download a file using Playwright.
    Useful when Canvas API returns access errors or requires a full session cookie.
    """
    with sync_playwright() as p:
        # Path for persistent browser state (cookies, login, etc.)
        user_data_dir = os.path.abspath(".playwright_cache")
        
        # Launching with head to allow the USER to see the process
        # Using persistent context to preserve login state
        context = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            slow_mo=500 # Adding a bit of delay to make it easier to see/interact
        )
        page = context.new_page()

        try:
            print(f"Attempting browser download for: {url}")
            # Increase timeout to allow for manual login if needed
            with page.expect_download(timeout=300000) as download_info:
                page.goto(url, wait_until="load")
            
            download = download_info.value
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            download.save_as(output_path)
            print(f"Successfully downloaded via browser to {output_path}")
            return True
        except Exception as e:
            print(f"Browser download failed: {e}. You might need to log in manually in the opened browser.")
            return False
        finally:
            context.close()
