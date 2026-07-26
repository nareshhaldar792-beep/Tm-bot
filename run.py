"""
Telegram Store Bot - Replit Runner
One-click start for Replit. Run: python run.py
"""

import os
import sys
import subprocess

def setup():
    """Setup the environment."""
    print("[*] Setting up environment...")

    # Install requirements
    print("[*] Installing dependencies...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])

    # Create data directories
    os.makedirs("data", exist_ok=True)
    os.makedirs("data/product_images", exist_ok=True)
    os.makedirs("data/qr_codes", exist_ok=True)
    os.makedirs("data/backups", exist_ok=True)

    # Check .env file
    if not os.path.exists(".env") and os.path.exists(".env.example"):
        print("[!] WARNING: .env file not found!")
        print("[!] Copy .env.example to .env and fill in your values.")
        print("[!] The bot will not work without a BOT_TOKEN!")

    print("[✓] Setup complete")
    print()

if __name__ == "__main__":
    setup()
    print("[*] Starting bot...")
    import main
