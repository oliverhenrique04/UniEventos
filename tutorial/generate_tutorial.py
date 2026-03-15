"""Generate a high‑quality tutorial for the UniEventos web application.

This script uses Playwright to automate a browser session, log in as each
profile type defined in ``config.json`` and capture screenshots of the main
pages that are relevant for that profile.  The screenshots are stored in
``tutorial/screenshots`` and a Markdown file ``tutorial/tutorial.md`` is
generated that references the images.

The script is intentionally lightweight – it does not depend on any
framework‑specific code and can be run from the project root:

    python -m tutorial.generate_tutorial

Before running the script you must install Playwright and its browsers:

    pip install -r requirements.txt
    playwright install

The configuration file ``tutorial/config.json`` contains the credentials
for each profile.  It is intentionally kept out of version control – the
example file ``tutorial/config.example.json`` shows the expected format.
"""

import json
import os
import pathlib
import sys
from datetime import datetime

try:
    from playwright.sync_api import sync_playwright
except Exception as exc:  # pragma: no cover
    print("Playwright is required to generate the tutorial. Install it with:\n\tpip install -r requirements.txt")
    sys.exit(1)

BASE_URL = os.getenv("BASE_URL", "http://localhost:5000")
CONFIG_PATH = pathlib.Path(__file__).parent / "config.json"
SCREENSHOT_DIR = pathlib.Path(__file__).parent / "screenshots"
MARKDOWN_PATH = pathlib.Path(__file__).parent / "tutorial.md"


def load_config() -> dict:
    """Load the JSON configuration file.

    The configuration file must contain a mapping of profile names to a
    dictionary with ``username`` and ``password`` keys.
    """
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(f"Configuration file not found: {CONFIG_PATH}")
    with open(CONFIG_PATH, "r", encoding="utf-8") as fp:
        return json.load(fp)


def login(page, username: str, password: str) -> None:
    """Perform a login on the application.

    The login form is located at ``/login`` and expects ``username`` and
    ``password`` fields.  After a successful login the user is redirected
    to the home page.
    """
    page.goto(f"{BASE_URL}/login")
    page.fill("input[name='username']", username)
    page.fill("input[name='password']", password)
    page.click("button[type='submit']")
    # Wait for navigation to the home page.
    page.wait_for_url(f"{BASE_URL}/")


def capture_page(page, name: str, url: str) -> pathlib.Path:
    """Navigate to ``url`` and capture a screenshot.

    The screenshot is stored in ``SCREENSHOT_DIR`` with a filename that
    includes the profile name and the page name.
    """
    page.goto(url)
    # Wait for the main content to load.
    page.wait_for_selector("body")
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    filename = SCREENSHOT_DIR / f"{name}.png"
    page.screenshot(path=str(filename), full_page=True)
    return filename


def generate_markdown(entries: list[tuple[str, pathlib.Path]]) -> None:
    """Generate a Markdown file that references the screenshots.

    ``entries`` is a list of tuples ``(title, path)``.
    """
    lines = [
        "# UniEventos Tutorial",
        "",
        f"Generated on {datetime.utcnow().isoformat()} UTC",
        "",
        "## Introduction",
        "",
        "This tutorial provides step-by-step instructions for using the UniEventos web application.",
        "The application has different interfaces based on user roles. This guide covers all profile types:",
        "",
        "- **Administrator**: Full access to all features and system management",
        "- **Instructor**: Access to course creation, event management, and certificate generation", 
        "- **Student**: Access to events, courses, and personal dashboard",
        "",
    ]
    for title, path in entries:
        rel_path = path.relative_to(path.parent)
        lines.append(f"## {title}")
        lines.append(f"![{title}]({rel_path})")
        lines.append("")
    MARKDOWN_PATH.write_text("\n".join(lines), encoding="utf-8")


def get_profile_pages(profile: str) -> dict[str, str]:
    """Define the pages to capture for each profile type."""
    pages = {
        "Home": f"{BASE_URL}/",
    }
    
    # Add specific pages based on profile type
    if profile == "admin":
        pages.update({
            "Admin Dashboard": f"{BASE_URL}/admin/dashboard",
            "User Management": f"{BASE_URL}/admin/users",
            "System Configuration": f"{BASE_URL}/admin/config"
        })
    elif profile == "instructor":
        pages.update({
            "Course Management": f"{BASE_URL}/courses",
            "Event Creation": f"{BASE_URL}/events/create",
            "Certificate Generation": f"{BASE_URL}/certificates/generate"
        })
    elif profile == "student":
        pages.update({
            "My Events": f"{BASE_URL}/events/my_events",
            "Enrollments": f"{BASE_URL}/enrollments",
            "Certificates": f"{BASE_URL}/certificates"
        })
    
    return pages


def main() -> None:
    config = load_config()
    entries: list[tuple[str, pathlib.Path]] = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        for profile, creds in config.items():
            page = context.new_page()
            try:
                login(page, creds["username"], creds["password"])
            except Exception as exc:  # pragma: no cover
                print(f"Failed to login as {profile}: {exc}")
                continue
            # Define the pages to capture for this profile.
            pages = get_profile_pages(profile)
            for name, url in pages.items():
                try:
                    screenshot = capture_page(page, f"{profile}_{name}", url)
                    entries.append((f"{profile.capitalize()} – {name}", screenshot))
                except Exception as exc:  # pragma: no cover
                    print(f"Failed to capture {name} for {profile}: {exc}")
            page.close()
        browser.close()
    generate_markdown(entries)
    print(f"Tutorial generated: {MARKDOWN_PATH}")


if __name__ == "__main__":  # pragma: no cover
    main()