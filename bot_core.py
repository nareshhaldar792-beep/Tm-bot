"""
Telegram Store Bot - Main Application Part 1
Init, Helpers, Core Handlers (/start, Shop, Orders, Support, About)
"""

import os
import telebot
from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ForceReply
from io import BytesIO
from datetime import datetime

import config
from config import BOT_TOKEN, ADMIN_IDS, STORE_NAME, SUPPORT_USERNAME, CURRENCY_SYMBOL, PRODUCT_IMAGES_DIR
from database import get_config

def get_support_username():
    return get_setting("support_username", SUPPORT_USERNAME)
from database import *
from payments import *
from binance_pay import binance_api

# ========== INIT ==========
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")

# User state storage
user_states = {}
user_data = {}


def set_state(user_id, state):
    user_states[user_id] = state


def get_state(user_id):
    return user_states.get(user_id, None)


def clear_state(user_id):
    user_states.pop(user_id, None)
    if user_id in user_data:
        user_data.pop(user_id, None)


def is_admin(user_id):
    return user_id in ADMIN_IDS or get_admin_role(user_id) is not None


# ========== KEYBOARDS ==========

def main_menu_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("🛍 Shop"), KeyboardButton("📋 My Orders"))

    # Build bottom row dynamically from settings
    bottom_buttons = []
    if is_support_enabled():
        btn_text = get_setting("support_button_text", "📞 Support")
        bottom_buttons.append(KeyboardButton(btn_text))
    if is_channel_enabled():
        btn_text = get_setting("channel_button_text", "📢 Official Channel")
        bottom_buttons.append(KeyboardButton(btn_text))
    if is_reseller_enabled():
        btn_text = get_setting("reseller_button_text", "🤝 Reseller")
        bottom_buttons.append(KeyboardButton(btn_text))
    # Always show About
    bottom_buttons.append(KeyboardButton("ℹ️ About"))

    if bottom_buttons:
        kb.add(*bottom_buttons)
    return kb


def admin_menu_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(KeyboardButton("📦 Products"), KeyboardButton("📋 Plans"))
    kb.add(KeyboardButton("🔑 Stock Keys"), KeyboardButton("📊 Orders"))
    kb.add(KeyboardButton("👥 Users"), KeyboardButton("📢 Broadcast"))
    kb.add(KeyboardButton("📈 Statistics"), KeyboardButton("⚙️ Config"))
    kb.add(KeyboardButton("🗂 Categories"), KeyboardButton("👑 Admins"))
    kb.add(KeyboardButton("📝 Logs"), KeyboardButton("💾 Backup"))
    kb.add(KeyboardButton("🏠 User Mode"))
    return kb


def shop_menu_keyboard():
    kb = InlineKeyboardMarkup(row_width=1)
    categories = get_categories()
    for cat in categories:
        kb.add(InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"cat_{cat['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back to Menu", callback_data="back_to_main"))
    return kb


# ========== HELPERS ==========

def safe_delete_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass


def send_product_details(chat_id, product_id, message_id=None):
    """Send product details with plans and buy option."""
    product = get_product(product_id)
    if not product:
        bot.send_message(chat_id, "❌ Product not found.")
        return

    from reseller_api import get_product_pid
    reseller_pid = get_product_pid(product_id)
    plans = get_plans(product_id)

    text = f"╔══════════════════════════════╗\n"
    text += f"║  {product['category_emoji']} {product['name'][:25]}  ║\n"
    text += f"╚══════════════════════════════╝\n\n"
    if product['description']:
        text += f"📝 _{product['description']}_\n\n"

    text += "🟢 *In Stock* — ⚡ Instant Delivery\n"
    text += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

    if plans:
        text += "📋 *Available Plans:*\n"
        for p in plans:
            text += f"• *{p['name']}* — *{format_amount(p['price'])}*"
            if p['duration']:
                text += f" _(⏱ {p['duration']})_"
            text += "\n"

    kb = InlineKeyboardMarkup(row_width=1)
    for p in plans:
        kb.add(InlineKeyboardButton(f"🛒 Buy {p['name']} — {format_amount(p['price'])}",
            callback_data=f"buy_{product['id']}_{p['id']}"
        ))
    kb.add(InlineKeyboardButton("🔙 « Back to Products", callback_data=f"back_to_cat_{product['category_id']}"))

    safe_delete_message(chat_id, message_id) if message_id else None
    if product['image_path'] and os.path.exists(product['image_path']):
        with open(product['image_path'], 'rb') as img:
            bot.send_photo(chat_id, img, caption=text, reply_markup=kb, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="Markdown")


def deliver_order_to_user(order):
    """Send the delivered key to the user."""
    try:
        delivered_key = order.get('delivered_key', '') or 'Contact support for your key'
        reseller_response = order.get('reseller_response', '')
        support_user = get_support_username()

        text = (
            f"╔══════════════════════════════╗\n"
            f"║    🎉 ORDER DELIVERED 🎉    ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📦 *Product*\n"
            f"   `{order['product_name']}`\n"
            f"📋 *Plan*\n"
            f"   `{order['plan_name']}`\n"
            f"💳 *Order ID*\n"
            f"   `{order['order_id']}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"🔑 *YOUR KEY* 🔑\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"`{delivered_key}`\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📌 *How to use:*\n"
            f"1️⃣ Copy your key above\n"
            f"2️⃣ Open the cheat app\n"
            f"3️⃣ Paste key in login section\n"
            f"4️⃣ Start using! 🚀\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *Important:*\n"
            f"• Save this key — it won't be shown again\n"
            f"• 1 key = 1 device only\n"
            f"• Replacement available within validity\n\n"
            f"📞 *Need help?* @{support_user}\n"
            f"📢 *Updates:* @{get_config('channel_username', 'Nannu_Key_Store')}\n\n"
            f"🙏 *Thank you for your purchase!*\n"
            f"⭐ _Please share your feedback with us!_"
        )
        bot.send_message(order['user_id'], text, parse_mode="Markdown")
        add_log("key_delivered", order['user_id'], f"Key delivered for order {order['order_id']}")
    except Exception as e:
        add_log("error", order['user_id'], f"Failed to deliver key: {e}")


def notify_admins_new_order(order):
    """Send notification to all admins about new order."""
    payment_icon = {"upi": "🏦", "phonepe": "💙", "gpay": "🟢", "paytm": "🔵", "binance": "🟨"}.get(order['payment_method'], "💳")
    text = (
        f"╔══════════════════════════════╗\n"
        f"║     🔔 NEW ORDER ALERT 🔔   ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Product*\n"
        f"   `{order['product_name']}`\n"
        f"📋 *Plan*\n"
        f"   `{order['plan_name']}`\n"
        f"💰 *Amount*\n"
        f"   *{format_amount(order['amount'])}*\n"
        f"{payment_icon} *Payment*\n"
        f"   `{order['payment_method'].upper()}`\n"
        f"🏷 *UTR / Txn ID*\n"
        f"   `{order.get('utr_number', 'N/A')}`\n"
        f"👤 *Customer*\n"
        f"   {order['username'] or order['user_id']}\n"
        f"📋 *Order ID*\n"
        f"   `{order['order_id']}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚡ *Action Required:* Approve or Reject below"
    )
    for admin_id in ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(
                InlineKeyboardButton("✅ APPROVE", callback_data=f"admin_approve_{order['order_id']}"),
                InlineKeyboardButton("❌ REJECT", callback_data=f"admin_reject_{order['order_id']}"),
            )
            bot.send_message(admin_id, text, reply_markup=kb, parse_mode="Markdown")
        except:
            pass
