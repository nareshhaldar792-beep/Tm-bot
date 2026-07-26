# Telegram Store Bot - Configuration

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# ========== TELEGRAM BOT ==========
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "8469175911").split(",")]

# ========== BINANCE PAY API ==========
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
BINANCE_MERCHANT_ID = os.getenv("BINANCE_MERCHANT_ID", "")
BINANCE_API_BASE = os.getenv("BINANCE_API_BASE", "https://bpay.binanceapi.com")
BINANCE_WEBHOOK_SECRET = os.getenv("BINANCE_WEBHOOK_SECRET", "")
BINANCE_ENABLED = os.getenv("BINANCE_ENABLED", "false").lower() == "true"
BINANCE_EXTRA_CHARGE = float(os.getenv("BINANCE_EXTRA_CHARGE", "20"))

# ========== UPI / MANUAL PAYMENT ==========
UPI_ID = os.getenv("UPI_ID", "your-upi-id@upi")
UPI_NAME = os.getenv("UPI_NAME", "Store Name")
PHONEPE_NUMBER = os.getenv("PHONEPE_NUMBER", "")
GOOGLEPAY_NUMBER = os.getenv("GOOGLEPAY_NUMBER", "")
PAYTM_NUMBER = os.getenv("PAYTM_NUMBER", "")

# ========== DATABASE ==========
DATABASE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "store.db")

# ========== BOT SETTINGS ==========
STORE_NAME = os.getenv("STORE_NAME", "🛍 Premium Store")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "GlobalSupportchannel")
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "₹")
BOT_USERNAME = os.getenv("BOT_USERNAME", "YourStoreBot")

# ========== IMAGE / FILE PATHS ==========
PRODUCT_IMAGES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "product_images")
QR_CODES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "qr_codes")
PAYMENT_QR_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "payment_qr")
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "backups")
