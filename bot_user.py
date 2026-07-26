"""
Telegram Store Bot - User Flow Handlers
/start, Shop, Categories, Products, Buy, Payment, UTR
"""

from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os

from database import *
from payments import *
from bot_core import *
from config import QR_CODES_DIR, UPI_ID, UPI_NAME, PAYMENT_QR_DIR


# ========== /START ==========

@bot.message_handler(commands=['start'])
def cmd_start(message):
    user = message.from_user
    get_or_create_user(user.id, user.username or "", user.first_name or "", user.last_name or "")
    clear_state(user.id)

    user_name = user.first_name or "Valued Customer"
    store_name = get_config("store_name", STORE_NAME) or STORE_NAME
    total_products = len(get_products())
    total_orders = get_order_count() if callable('get_order_count') else "100+"

    welcome = (
        f"╔══════════════════════════════╗\n"
        f"║   ✨ *{store_name}* ✨   ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"👤 *Welcome, {user_name}!*\n\n"
        f"🎯 India's Most Trusted Digital Key Store\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🔐 *Instant Automated Delivery*\n"
        f"💰 *Best Market Prices*\n"
        f"🏦 *UPI | PhonePe | GPay | Paytm*\n"
        f"🤝 *24×7 Priority Support*\n"
        f"🛡️ *100% Replacement Guarantee*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 *{total_products}+ Products Available*\n"
        f"⚡ *Delivery in under 60 seconds*\n\n"
        f"👇 *Choose an option to get started:*"
    )

    if is_admin(user.id):
        welcome += "\n\n🔰 *Admin Mode: Active*"

    kb = main_menu_keyboard()
    if is_admin(user.id):
        kb.add(KeyboardButton("🔰 Admin Panel"))
    bot.send_message(message.chat.id, welcome, reply_markup=kb, parse_mode="Markdown")


# ========== MAIN MENU HANDLERS ==========

@bot.message_handler(func=lambda m: m.text == "🛍 Shop")
def shop_handler(message):
    clear_state(message.from_user.id)
    text = "🛍 *Categories*\n✨ Premium Digital Keys\n\n📂 *Select a Category:*"
    kb = shop_menu_keyboard()
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📋 My Orders")
def my_orders_handler(message):
    user_id = message.from_user.id
    orders = get_user_orders(user_id, limit=15)

    if not orders:
        bot.send_message(message.chat.id, "📋 *No orders yet!*\n\nVisit 🛍 Shop to make a purchase.", parse_mode="Markdown")
        return

    text = "📋 *Your Orders:*\n\n"
    for o in orders:
        status_emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌", "cancelled": "🚫"}.get(o['order_status'], "❓")
        text += (
            f"{status_emoji} *{o['product_name']}* — {o['plan_name']}\n"
            f"   Amount: {format_amount(o['amount'])} | ID: `{o['order_id']}`\n"
            f"   Status: {o['order_status'].title()}\n\n"
        )

    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == get_setting("support_button_text", "📞 Support") or m.text == "📞 Support")
def support_handler(message):
    support_user = get_setting("support_username", "nannu_key_store")
    support_link = get_setting("support_link", "https://t.me/nannu_key_store")
    text = (
        f"╔══════════════════════════════╗\n"
        f"║     📞 24×7 SUPPORT 📞     ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"🤝 *We're Here to Help!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Support Contact:*\n"
        f"   👉 @{support_user}\n"
        f"   🔗 {support_link}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏱ *Response Time:* Under 30 mins\n"
        f"🕐 *Available:* 24×7\n\n"
        f"📋 *For faster resolution:*\n"
        f"• Share your Order ID\n"
        f"• Screenshot of payment\n"
        f"• Your Telegram username"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == get_setting("channel_button_text", "📢 Official Channel"))
def channel_handler(message):
    channel_user = get_setting("channel_username", "Nannu_Key_Store")
    channel_link = get_setting("channel_link", "https://t.me/Nannu_Key_Store")
    text = (
        f"╔══════════════════════════════╗\n"
        f"║   📢 OFFICIAL CHANNEL 📢   ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"🔔 *Stay Updated!*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📢 *Join our channel for:*\n\n"
        f"🆕 Latest Product Launches\n"
        f"🔥 Hot Deals & Discounts\n"
        f"📦 Stock Availability Alerts\n"
        f"🎁 Exclusive Giveaways\n"
        f"📣 Important Announcements\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👉 *Join Now:* @{channel_user}\n"
        f"🔗 {channel_link}\n\n"
        f"_Don't miss out on updates! 🔥_"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == get_setting("reseller_button_text", "🤝 Reseller"))
def reseller_handler(message):
    reseller_user = get_setting("reseller_username", "")
    reseller_link = get_setting("reseller_link", "")
    if not reseller_user and not reseller_link:
        text = (
            f"╔══════════════════════════════╗\n"
            f"║   🤝 RESELLER PROGRAM 🤝   ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"💼 *Grow Your Business With Us!*\n\n"
            f"Interested in becoming a reseller?\n"
            f"Contact our support team for inquiries!"
        )
    else:
        text = (
            f"╔══════════════════════════════╗\n"
            f"║   🤝 RESELLER PROGRAM 🤝   ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"💼 *Partner With Us!*\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🚀 *Benefits:*\n"
            f"💰 Wholesale Pricing\n"
            f"🔑 Bulk Key Delivery\n"
            f"📊 Dedicated Dashboard\n"
            f"🤝 Priority Support\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        if reseller_user:
            text += f"👉 *Contact:* @{reseller_user}\n"
        if reseller_link:
            text += f"🔗 {reseller_link}\n"
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "ℹ️ About")
def about_handler(message):
    store_name = get_config("store_name", STORE_NAME) or STORE_NAME
    total_orders = get_order_count() if callable('get_order_count') else "5000+"
    text = (
        f"╔══════════════════════════════╗\n"
        f"║       ℹ️ ABOUT US ℹ️       ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"🏪 *{store_name}*\n"
        f"_India's Premium Digital Key Provider_\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"✨ *Why Choose Us?*\n\n"
        f"⚡ Instant Automated Delivery\n"
        f"💰 Lowest Market Prices\n"
        f"🛡️ 100% Key Replacement\n"
        f"🤝 24×7 Priority Support\n"
        f"📦 Regular Stock Updates\n"
        f"🔐 Secure Transactions\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Our Stats:*\n"
        f"✅ {total_orders}+ Orders Delivered\n"
        f"⭐ 4.9/5 Customer Rating\n"
        f"👥 1000+ Happy Customers\n\n"
        f"📌 *Payment Methods:*\n"
        f"🏦 UPI  │  💙 PhonePe\n"
        f"🟢 GPay │ 🔵 Paytm\n"
        f"🟨 Binance Pay\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🤖 *Bot Version:* v3.0 Pro\n"
        f"🔧 *Powered by:* Telegram Bot API"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


# ========== CALLBACK HANDLERS ==========

@bot.callback_query_handler(func=lambda call: call.data == "back_to_main")
def cb_back_to_main(call):
    clear_state(call.from_user.id)
    text = "🏠 *Main Menu*\nWhat would you like to do?"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("cat_"))
def cb_category(call):
    category_id = int(call.data.split("_")[1])
    products = get_products(category_id=category_id)

    if not products:
        bot.answer_callback_query(call.id, "No products in this category yet!", show_alert=True)
        return

    text = f"📦 *{products[0]['category_emoji']} {products[0]['category_name']}*\n✨ Premium Digital Keys\n\n📋 *Select a Product:*"
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(f"🟢 {p['name']}", callback_data=f"prod_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back to Categories", callback_data="back_to_categories"))

    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_categories")
def cb_back_to_categories(call):
    text = "🛍 *Categories*\n✨ Premium Digital Keys\n\n📂 *Select a Category:*"
    kb = shop_menu_keyboard()
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("prod_"))
def cb_product(call):
    product_id = int(call.data.split("_")[1])
    send_product_details(call.message.chat.id, product_id, call.message.message_id)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("back_to_cat_"))
def cb_back_to_cat(call):
    category_id = int(call.data.split("_")[3])
    products = get_products(category_id=category_id)
    text = f"📦 *Products*\n\nSelect a product:"
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(f"🟢 {p['name']}", callback_data=f"prod_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back to Categories", callback_data="back_to_categories"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== BUY & PAYMENT ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def cb_buy(call):
    parts = call.data.split("_")
    product_id = int(parts[1])
    plan_id = int(parts[2])

    product = get_product(product_id)
    plan = get_plan(plan_id)

    if not product or not plan:
        bot.answer_callback_query(call.id, "Product or plan not found!", show_alert=True)
        return

    user_data[call.from_user.id] = {
        "product_id": product_id,
        "plan_id": plan_id,
        "product_name": product['name'],
        "plan_name": plan['name'],
        "amount": plan['price'],
        "product_desc": product['description'],
    }

    text = (
        f"╔══════════════════════════════╗\n"
        f"║      🛒 CHECKOUT 🛒      ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Product*\n"
        f"   `{product['name']}`\n"
        f"📋 *Plan*\n"
        f"   `{plan['name']}`\n"
        f"💰 *Amount*\n"
        f"   *{format_amount(plan['price'])}*\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"💳 *Select Payment Method:*"
    )
    kb = get_payment_keyboard()
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "back_to_product")
def cb_back_to_product(call):
    ud = user_data.get(call.from_user.id, {})
    product_id = ud.get("product_id")
    if product_id:
        send_product_details(call.message.chat.id, product_id, call.message.message_id)
    else:
        cb_back_to_categories(call)
    bot.answer_callback_query(call.id)


# ========== PAYMENT PROCESSING ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith("pay_"))
def cb_payment(call):
    method = call.data.split("_")[1]
    ud = user_data.get(call.from_user.id)

    if not ud:
        bot.answer_callback_query(call.id, "Session expired. Please start again.", show_alert=True)
        return

    user = call.from_user

    # For Binance: store base amount in order but apply extra charge for display
    base_amount = ud["amount"]
    display_amount = base_amount
    if method == "binance":
        display_amount = get_binance_amount(base_amount)

    order_id = create_order(
        user_id=user.id,
        username=user.username or "",
        product_id=ud["product_id"],
        plan_id=ud["plan_id"],
        product_name=ud["product_name"],
        plan_name=ud["plan_name"],
        amount=base_amount,  # store base price in order
        payment_method=method,
    )

    add_log("order_created", user.id, f"Order {order_id} created for {ud['product_name']} via {method}")
    safe_delete_message(call.message.chat.id, call.message.message_id)

    method_handlers = {
        "upi": ("🏦 UPI", get_upi_payment_text, UPI_QR_PATH),
        "phonepe": ("💙 PhonePe", get_phonepay_payment_text, PHONEPE_QR_PATH),
        "gpay": ("🟢 Google Pay", get_googlepay_payment_text, GPAY_QR_PATH),
        "paytm": ("🔵 Paytm", get_paytm_payment_text, PAYTM_QR_PATH),
    }

    if method in method_handlers:
        _, text_fn, qr_path = method_handlers[method]
        plan_name = ud.get("plan_name", "")
        text = text_fn(order_id, base_amount, ud["product_name"], plan_name)
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("✅ I've Paid — Submit UTR", callback_data=f"utr_{order_id}"))

        # Generate dynamic UPI QR with amount for ALL UPI-based methods
        upi_id = get_config("upi_id", UPI_ID)
        upi_name = get_config("upi_name", UPI_NAME)
        upi_uri = f"upi://pay?pa={upi_id}&pn={upi_name}&am={base_amount}&cu=INR&tn={order_id}"
        dyn_qr = os.path.join(QR_CODES_DIR, f"{order_id}.png")
        generate_qr_image(upi_uri, dyn_qr)
        with open(dyn_qr, 'rb') as qr_img:
            bot.send_photo(call.message.chat.id, qr_img, caption=text, reply_markup=kb, parse_mode="Markdown")

    elif method == "binance":
        # Use display_amount (base + extra charge) for Binance QR in INR
        binance_result = get_binance_payment_data(
            order_id=order_id,
            base_amount=display_amount,
            product_name=ud["product_name"],
            product_desc=ud.get("product_desc", ""),
            buyer_id=str(user.id),
        )

        if binance_result.get("success"):
            prepay_id = binance_result.get("prepay_id", "")
            update_order(order_id, binance_prepay_id=prepay_id)

            charge = get_binance_extra_charge()
            plan_name = ud.get("plan_name", "")
            text = (
                f"🟨 *Binance Pay*\n\n"
                f"📦 *Product:* {ud['product_name']}\n"
            )
            if plan_name:
                text += f"📋 *Plan:* {plan_name}\n"
            text += (
                f"💰 *Base Price:* {format_amount(base_amount)}\n"
                f"➕ *Binance Fee:* {format_amount(charge)}\n"
                f"💰 *Total:* {format_amount(display_amount)}\n"
                f"📋 *Order ID:* `{order_id}`\n\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📱 *Scan the QR code below with Binance App*\n\n"
                f"⏳ *Payment Status:* Waiting for payment..."
            )

            qr_path = binance_result.get("qr_image_path")
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("🔄 « Check Payment Status", callback_data=f"checkbin_{order_id}"))
            kb.add(InlineKeyboardButton("🔙 « Cancel Order", callback_data=f"cancel_{order_id}"))

            if qr_path and os.path.exists(qr_path):
                with open(qr_path, 'rb') as qr_img:
                    bot.send_photo(call.message.chat.id, qr_img, caption=text, reply_markup=kb, parse_mode="Markdown")
            else:
                qr_url = binance_result.get("qr_code_url", "")
                text += f"\n🔗 [Open Payment Link]({qr_url})"
                bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
        else:
            text = (
                f"⚠️ *Binance Pay Error*\n\n"
                f"Error: {binance_result.get('error', 'Unknown error')}\n\n"
                f"Order ID: `{order_id}`\n"
                f"Please try another payment method or contact support."
            )
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("💳 « Try Another Method", callback_data=f"change_payment_{order_id}"))
            bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
            update_order(order_id, payment_status="failed")

    bot.answer_callback_query(call.id)


# ========== BINANCE PAYMENT VERIFICATION ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith("checkbin_"))
def cb_check_binance(call):
    order_id = call.data.split("_", 1)[1]
    order = get_order(order_id)

    if not order:
        bot.answer_callback_query(call.id, "Order not found.", show_alert=True)
        return

    if order['order_status'] in ('approved', 'rejected'):
        bot.answer_callback_query(call.id, f"Order already {order['order_status']}!", show_alert=True)
        return

    result = verify_binance_payment(order_id, order.get("binance_prepay_id", ""))

    if result.get("success"):
        status = result.get("status", "").upper()
        if status in ("SUCCESS", "PAID", "COMPLETED", "FINISHED"):
            update_order(order_id, payment_status="completed")
            bot.answer_callback_query(call.id, "✅ Payment verified! Your order is pending admin approval.", show_alert=True)
            notify_admins_new_order(order)
            text = (
                f"✅ *Payment Confirmed!*\n\n"
                f"📦 *Product:* {order['product_name']}\n"
                f"💰 *Amount:* {format_amount(order['amount'])}\n"
                f"📋 *Order ID:* `{order_id}`\n\n"
                f"⏳ Your order is now pending admin approval.\n"
                f"You'll receive your key automatically!"
            )
            try:
                bot.edit_message_caption(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
            except:
                pass
        elif status in ("PENDING", "INITIAL", "CREATED"):
            bot.answer_callback_query(call.id, "⏳ Payment still pending. Try again in a moment.", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"Status: {status}. Contact support if needed.", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "⏳ Still waiting for payment. Scan the QR with Binance App.", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("cancel_"))
def cb_cancel_order(call):
    order_id = call.data.split("_", 1)[1]
    update_order(order_id, order_status="cancelled", payment_status="cancelled")
    try:
        bot.edit_message_caption("❌ Order cancelled.", call.message.chat.id, call.message.message_id)
    except:
        try:
            bot.edit_message_text("❌ Order cancelled.", call.message.chat.id, call.message.message_id)
        except:
            pass
    bot.answer_callback_query(call.id, "Order cancelled.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("change_payment_"))
def cb_change_payment(call):
    order_id = call.data.split("_", 2)[2]
    update_order(order_id, order_status="cancelled", payment_status="cancelled")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    text = "💳 *Select a different payment method:*"
    kb = get_payment_keyboard()
    bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== UTR HANDLING ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith("utr_"))
def cb_utr_prompt(call):
    order_id = call.data.split("_", 1)[1]
    set_state(call.from_user.id, f"waiting_utr_{order_id}")
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🧾 *Payment Verification*\n\n"
        f"🇮🇳 कृपया अपना UTR नंबर दर्ज करें।\n"
        f"🇬🇧 Please enter your UTR Number.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"ℹ️ सुनिश्चित करें कि आपने सही UTR नंबर दर्ज किया है।\n"
        f"ℹ️ Please make sure the UTR Number is correct.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"✍️ *Enter UTR Number*\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: get_state(m.from_user.id) and get_state(m.from_user.id).startswith("waiting_utr_"))
def handle_utr_input(message):
    state = get_state(message.from_user.id)
    order_id = state.replace("waiting_utr_", "")
    utr = message.text.strip()

    if len(utr) < 4:
        bot.reply_to(message, "⚠️ Please enter a valid Transaction ID (at least 4 characters).")
        return

    update_order(order_id, utr_number=utr, payment_status="submitted")
    clear_state(message.from_user.id)

    order = get_order(order_id)

    text = (
        f"╔══════════════════════════════╗\n"
        f"║   ✅ PAYMENT SUBMITTED ✅   ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 *Product*\n"
        f"   `{order['product_name']}`\n"
        f"💰 *Amount*\n"
        f"   *{format_amount(order['amount'])}*\n"
        f"📋 *Order ID*\n"
        f"   `{order_id}`\n"
        f"🏷 *UTR / Txn ID*\n"
        f"   `{utr}`\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⏳ *Verification in Progress...*\n\n"
        f"🇮🇳 आपका भुगतान सत्यापन के लिए भेज दिया गया है।\n"
        f"कृपया 5-10 मिनट प्रतीक्षा करें।\n\n"
        f"🇬🇧 Your payment has been submitted for verification.\n"
        f"Please allow 5-10 minutes for processing.\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📞 *Support:* @{get_config('support_username', SUPPORT_USERNAME)}\n"
        f"📢 *Channel:* @{get_config('channel_username', 'Nannu_Key_Store')}"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

    notify_admins_new_order(order)
    add_log("payment_submitted", message.from_user.id, f"UTR {utr} for order {order_id}")
