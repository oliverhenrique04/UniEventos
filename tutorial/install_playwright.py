"""Install Playwright browsers for tutorial generation."""

import subprocess
import sys

def install_playwright_browsers():
    """Install Playwright browsers."""
    try:
        # Install Playwright if not already installed
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
        
        # Install browsers
        subprocess.check_call([sys.executable, "-m", "playwright", "install"])
        
        print("✓ Playwright and browsers installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Playwright: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    install_playwright_browsers()