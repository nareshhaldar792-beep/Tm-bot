"""
Payment Handler — QR codes, payment messages, Binance integration
"""

import qrcode
import os
from io import BytesIO

import config
from config import (
    UPI_ID, UPI_NAME, PHONEPE_NUMBER, GOOGLEPAY_NUMBER, PAYTM_NUMBER,
    CURRENCY_SYMBOL, QR_CODES_DIR, PAYMENT_QR_DIR, STORE_NAME
)
from database import get_binance_extra_charge, is_binance_enabled, get_config
from binance_pay import binance_api


# ---- Dynamic config getters (DB overrides .env) ----
def _cfg(key, default):
    """Get config from DB, falling back to env default."""
    return get_config(key, default)

def _get_upi_id():
    return _cfg("upi_id", UPI_ID)

def _get_upi_name():
    return _cfg("upi_name", UPI_NAME)

def _get_phonepe_number():
    return _cfg("phonepe_number", PHONEPE_NUMBER)

def _get_gpay_number():
    return _cfg("gpay_number", GOOGLEPAY_NUMBER)

def _get_paytm_number():
    return _cfg("paytm_number", PAYTM_NUMBER)


# ---- Payment QR paths (uploaded by admin) ----
def _payqr_path(name: str) -> str:
    return os.path.join(PAYMENT_QR_DIR, name)


UPI_QR_PATH     = _payqr_path("upi_qr.png")
PHONEPE_QR_PATH = _payqr_path("phonepe_qr.png")
GPAY_QR_PATH    = _payqr_path("gpay_qr.png")
PAYTM_QR_PATH   = _payqr_path("paytm_qr.png")

_QR_MAP = {
    "upi":     UPI_QR_PATH,
    "phonepe": PHONEPE_QR_PATH,
    "gpay":    GPAY_QR_PATH,
    "paytm":   PAYTM_QR_PATH,
}


def has_payment_qr(method: str) -> bool:
    """Check if a static QR image was uploaded for this method."""
    path = _QR_MAP.get(method)
    return path is not None and os.path.exists(path)


# ---- Helpers ----

def generate_qr_image(data: str, filepath: str, size: int = 300) -> str:
    """Generate a QR code image and save it. Returns filepath."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").resize((size, size))
    img.save(filepath)
    return filepath


def format_amount(amount: float) -> str:
    """Format amount for display."""
    if amount == int(amount):
        return f"{CURRENCY_SYMBOL}{int(amount)}"
    return f"{CURRENCY_SYMBOL}{amount:.2f}"


# ---- Payment message builder (shared template) ----

def _build_payment_text(method_emoji: str, method_name: str, order_id: str,
                         amount: float, product_name: str, plan_name: str = "",
                         extra_info: str = "") -> str:
    """Build a consistent payment message for all manual methods."""
    text = (
        f"╔══════════════════════════════╗\\n"
        f"║    {method_emoji} {method_name}    ║\\n"
        f"╚══════════════════════════════╝\\n\\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n"
        f"📦 *Product*\\n"
        f"   `{product_name}`\\n"
    )
    if plan_name:
        text += f"📋 *Plan*\\n"
        text += f"   `{plan_name}`\\n"
    text += (
        f"💰 *Amount*\\n"
        f"   *{format_amount(amount)}*\\n"
        f"📋 *Order ID*\\n"
        f"   `{order_id}`\\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n"
    )
    if extra_info:
        text += extra_info + "\\n\\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━━━\\n\\n"
    text += (
        f"📌 *Payment Steps:*\\n"
        f"1️⃣ Scan QR or copy UPI ID\\n"
        f"2️⃣ Pay exact amount: *{format_amount(amount)}*\\n"
        f"3️⃣ Copy the UTR / Transaction ID\\n"
        f"4️⃣ Click 'Submit UTR' button below 👇\\n\\n"
        f"⚠️ _Payment without UTR will be rejected_"
    )
    return text


def get_upi_payment_text(order_id: str, amount: float, product_name: str,
                          plan_name: str = "") -> str:
    upi_id = _get_upi_id()
    upi_name = _get_upi_name()
    extra = f"📱 *Pay via any UPI app*\\n\\n*UPI ID:* `{upi_id}`\\n*Name:* {upi_name}"
    return _build_payment_text("🏦", "UPI Payment", order_id, amount,
                                product_name, plan_name, extra)


def get_phonepay_payment_text(order_id: str, amount: float, product_name: str,
                               plan_name: str = "") -> str:
    number = _get_phonepe_number()
    upi_name = _get_upi_name()
    extra = f"📱 *Pay via PhonePe*\\n\\n*Number:* `{number}`\\n*Name:* {upi_name}"
    return _build_payment_text("💙", "PhonePe Payment", order_id, amount,
                                product_name, plan_name, extra)


def get_googlepay_payment_text(order_id: str, amount: float, product_name: str,
                                plan_name: str = "") -> str:
    number = _get_gpay_number()
    upi_name = _get_upi_name()
    extra = f"📱 *Pay via Google Pay*\\n\\n*Number:* `{number}`\\n*Name:* {upi_name}"
    return _build_payment_text("🟢", "Google Pay Payment", order_id, amount,
                                product_name, plan_name, extra)


def get_paytm_payment_text(order_id: str, amount: float, product_name: str,
                            plan_name: str = "") -> str:
    number = _get_paytm_number()
    upi_name = _get_upi_name()
    extra = f"📱 *Pay via Paytm*\\n\\n*Number:* `{number}`\\n*Name:* {upi_name}"
    return _build_payment_text("🔵", "Paytm Payment", order_id, amount,
                                product_name, plan_name, extra)


# ---- Binance Pay (dynamic QR + ₹extra charge) ----

def get_binance_amount(base_price: float) -> float:
    """Apply Binance extra charge on top of base price."""
    charge = get_binance_extra_charge()
    return round(base_price + charge, 2)


def get_binance_payment_data(order_id: str, base_amount: float, product_name: str,
                              product_desc: str = "", buyer_id: str = "") -> dict:
    """
    Prepare Binance Pay payment data with extra charge applied.
    Returns dict with QR, prepay_id, status etc.
    """
    if not is_binance_enabled():
        return {"success": False, "error": "Binance Pay is currently disabled"}

    # Convert INR to USDT (approximate rate)
    usdt_amount = round(base_amount / 85.0, 2)
    if usdt_amount < 0.01:
        usdt_amount = 0.01

    result = binance_api.create_order(
        order_id=order_id,
        amount=usdt_amount,
        currency="USDT",
        product_name=product_name,
        product_desc=product_desc,
        buyer_id=buyer_id,
    )

    if result.get("success"):
        qr_content = result.get("qr_content") or result.get("qr_code_url", "")
        if qr_content:
            qr_path = os.path.join(QR_CODES_DIR, f"{order_id}.png")
            generate_qr_image(qr_content, qr_path)
            result["qr_image_path"] = qr_path

    return result


def verify_binance_payment(order_id: str, prepay_id: str = "") -> dict:
    """Verify a Binance Pay payment status."""
    result = binance_api.query_order(
        prepay_id=prepay_id,
        merchant_trade_no=order_id,
    )
    return result


def get_payment_keyboard():
    """Return the inline keyboard for payment method selection."""
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(row_width=2)
    buttons = [
        InlineKeyboardButton("🏦 UPI", callback_data="pay_upi"),
        InlineKeyboardButton("💙 PhonePe", callback_data="pay_phonepe"),
        InlineKeyboardButton("🟢 Google Pay", callback_data="pay_gpay"),
        InlineKeyboardButton("🔵 Paytm", callback_data="pay_paytm"),
    ]
    # Only show Binance if enabled
    if is_binance_enabled() or binance_api.is_configured():
        buttons.append(InlineKeyboardButton("🟨 Binance Pay", callback_data="pay_binance"))
    buttons.append(InlineKeyboardButton("🔙 « Back", callback_data="back_to_product"))
    kb.add(*buttons)
    return kb
