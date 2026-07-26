"""
Telegram Store Bot - Main Entry Point
Run this file to start the bot.
"""

import os
import sys
import time

# Ensure data directories exist
os.makedirs("data/product_images", exist_ok=True)
os.makedirs("data/qr_codes", exist_ok=True)
os.makedirs("data/payment_qr", exist_ok=True)
os.makedirs("data/backups", exist_ok=True)

from database import init_db
from bot_core import bot
import bot_user    # Import to register user handlers
import bot_admin   # Import to register admin handlers

print("=" * 50, flush=True)
print("🛍  Telegram Store Bot v3.0 Pro", flush=True)
print("=" * 50, flush=True)

# Initialize database
print("[*] Initializing database...", flush=True)
init_db()
print("[✓] Database initialized", flush=True)

# Admin check
from config import ADMIN_IDS, BOT_USERNAME
if not ADMIN_IDS:
    print("[!] WARNING: No Admin IDs configured. Update .env file!", flush=True)
else:
    print(f"[✓] Admin IDs: {ADMIN_IDS}", flush=True)

print(f"[✓] Bot username: @{BOT_USERNAME}", flush=True)
print(f"[*] Starting bot polling...", flush=True)
print("=" * 50, flush=True)

# Start bot with error handling
while True:
    try:
        print("[✓] Bot is running...", flush=True)
        bot.infinity_polling(timeout=30, long_polling_timeout=10, skip_pending=True)
    except KeyboardInterrupt:
        print("\n[!] Bot stopped by user", flush=True)
        sys.exit(0)
    except Exception as e:
        error_msg = str(e)
        print(f"[!] Error: {error_msg}", flush=True)
        if "409" in error_msg or "Conflict" in error_msg:
            print("[*] Another instance detected. Waiting 45s before retry...", flush=True)
            time.sleep(45)
            # Clear webhook just in case
            try:
                bot.remove_webhook()
                time.sleep(2)
            except:
                pass
        elif "ModuleNotFound" in error_msg or "SyntaxError" in error_msg or "ImportError" in error_msg:
            print("[!] Fatal error — exiting", flush=True)
            sys.exit(1)
        else:
            print("[*] Restarting in 15 seconds...", flush=True)
            time.sleep(15)
