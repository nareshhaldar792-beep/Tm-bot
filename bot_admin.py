"""
Telegram Store Bot - Admin Panel 
(Products, Plans, Orders, Keys, Users, Broadcast, Stats, Config, Logs, Backup)
"""

from telebot import types
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup
import os

from database import *
from payments import *
from bot_core import *



# ========== ADMIN PANEL ENTRY ==========

@bot.message_handler(func=lambda m: m.text == "🔰 Admin Panel" and is_admin(m.from_user.id))
def admin_panel_handler(message):
    clear_state(message.from_user.id)
    text = (
        f"╔══════════════════════════════╗\n"
        f"║    🔰 ADMIN PANEL 🔰    ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"Welcome back, Admin! 👑\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Select a section to manage:"
    )
    kb = admin_menu_keyboard()
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🏠 User Mode" and is_admin(m.from_user.id))
def user_mode_handler(message):
    clear_state(message.from_user.id)
    kb = main_menu_keyboard()
    kb.add(KeyboardButton("🔰 Admin Panel"))
    bot.send_message(message.chat.id, "🏠 Switched to User Mode.", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data == "admin_back")
def cb_admin_back(call):
    text = "🔰 *Admin Panel*\n\nSelect a section to manage:"
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== APPROVE / REJECT FROM NOTIFICATION ==========

@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_approve_"))
def cb_admin_approve(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return
    order_id = call.data.replace("admin_approve_", "")
    order = get_order(order_id)
    if not order or order['order_status'] != 'pending':
        bot.answer_callback_query(call.id, "Order already processed!", show_alert=True)
        return
    success, result = approve_order(order_id)
    if success:
        order = get_order(order_id)
        deliver_order_to_user(order)
        text = f"✅ *Order Approved!*\n\n📦 `{order['product_name']}`\n📋 `{order['plan_name']}`\n👤 {order['username'] or order['user_id']}\n🔑 `{result}`\n\n_Key delivered automatically_ 🤖"
        try:
            safe_delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
        except: pass
        bot.answer_callback_query(call.id, "Order approved & key delivered!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, f"Error: {result}", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_reject_"))
def cb_admin_reject(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return
    order_id = call.data.replace("admin_reject_", "")
    set_state(call.from_user.id, f"admin_reject_reason_{order_id}")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "❌ *Reject Reason?*\nPlease type the reason:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== ORDERS ==========

@bot.message_handler(func=lambda m: m.text == "📊 Orders" and is_admin(m.from_user.id))
def admin_orders_handler(message):
    pending = get_orders(status="pending", limit=30)
    if not pending:
        kb = InlineKeyboardMarkup()
        kb.add(InlineKeyboardButton("📋 View All Orders", callback_data="admin_orders_all"))
        bot.send_message(message.chat.id, "📊 *No pending orders!*", reply_markup=kb, parse_mode="Markdown")
        return
    text = f"📊 *Pending Orders ({len(pending)})*\n\n"
    for o in pending[:10]:
        text += f"📋 `{o['order_id']}`\n📦 {o['product_name']} - {o['plan_name']}\n💰 {format_amount(o['amount'])} | 💳 {o['payment_method']}\n👤 {o['username'] or o['user_id']}"
        if o.get('utr_number'): text += f" | UTR: `{o['utr_number']}`"
        text += "\n\n"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📋 « All Orders", callback_data="admin_orders_all"), InlineKeyboardButton("✅ « Approved", callback_data="admin_orders_approved"))
    kb.add(InlineKeyboardButton("❌ « Rejected", callback_data="admin_orders_rejected"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_orders_"))
def cb_admin_orders(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Admin only!", show_alert=True)
        return
    ft = call.data.replace("admin_orders_", "")
    sm = {"all": None, "approved": "approved", "rejected": "rejected"}
    orders = get_orders(status=sm.get(ft), limit=50) if sm.get(ft) else get_orders(limit=50)
    text = f"📊 *Orders ({ft.title()})*\n\n"
    if not orders: text += "No orders found."
    for o in orders[:20]:
        se = {"pending": "⏳", "approved": "✅", "rejected": "❌", "cancelled": "🚫"}.get(o['order_status'], "❓")
        text += f"{se} `{o['order_id']}`\n📦 {o['product_name']} - {o['plan_name']} | 💰 {format_amount(o['amount'])}\n👤 {o['username'] or o['user_id']} | 💳 {o['payment_method']}\n"
        if o.get('utr_number'): text += f"🏷 UTR: `{o['utr_number']}`\n"
        text += "\n"
    kb = InlineKeyboardMarkup()
    if ft != "all": kb.add(InlineKeyboardButton("📋 « View All", callback_data="admin_orders_all"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    try:
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    except: bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== PRODUCTS ==========

@bot.message_handler(func=lambda m: m.text == "📦 Products" and is_admin(m.from_user.id))
def admin_products_handler(message):
    clear_state(message.from_user.id)
    products = get_products(active_only=False)
    text = "📦 *Product Management*\n\n"
    for p in products:
        sb = "🟢 Active" if p['is_active'] else "🔴 Inactive"
        text += f"{p['category_emoji']} *{p['name']}* ({p['category_name']}) - {sb}\n   ID: `{p['id']}`\n\n"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ « Add Product", callback_data="admin_add_product"), InlineKeyboardButton("✏️ « Edit Product", callback_data="admin_edit_product_select"))
    kb.add(InlineKeyboardButton("🗑 « Delete Product", callback_data="admin_del_product_select"), InlineKeyboardButton("🖼 « Upload Image", callback_data="admin_upload_image_select"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_product")
def cb_admin_add_product(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    set_state(call.from_user.id, "admin_add_product_name")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "➕ *Add Product*\nSend the *product name*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_product_select")
def cb_admin_edit_product_select(call):
    products = get_products(active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(f"{p['name']} (ID:{p['id']})", callback_data=f"edit_prod_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✏️ Select product to edit:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("edit_prod_"))
def cb_edit_prod(call):
    pid = int(call.data.split("_")[2])
    user_data[call.from_user.id] = {"product_id": pid}
    set_state(call.from_user.id, "admin_edit_product_field")
    p = get_product(pid)
    reseller_pid = p.get('product_pid', 0) if p else 0
    pid_info = f"\n🔌 *Reseller PID:* `{reseller_pid}`" if reseller_pid else "\n🔌 *Reseller PID:* _Not set_"
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✏️ Editing: *{p['name']}*{pid_info}\nSend *name*, *description*, *pid*, or *toggle*.",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_del_product_select")
def cb_admin_del_product_select(call):
    products = get_products(active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(f"🗑 {p['name']} (ID:{p['id']})", callback_data=f"del_prod_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🗑 Select product to delete:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("del_prod_"))
def cb_del_prod(call):
    pid = int(call.data.split("_")[2])
    delete_product(pid)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✅ Product `{pid}` deleted!")
    bot.answer_callback_query(call.id, "Deleted!")


@bot.callback_query_handler(func=lambda call: call.data == "admin_upload_image_select")
def cb_upload_image_select(call):
    products = get_products(active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(f"{p['name']} (ID:{p['id']})", callback_data=f"uploadimg_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🖼 Select product:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("uploadimg_"))
def cb_upload_img(call):
    pid = int(call.data.split("_")[1])
    user_data[call.from_user.id] = {"product_id": pid}
    set_state(call.from_user.id, "admin_add_product_name")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"🖼 Send the *image* for product `{pid}`:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("pick_cat_"))
def cb_pick_cat(call):
    cat_id = int(call.data.split("_")[2])
    ud = user_data.get(call.from_user.id, {})
    pid = add_product(cat_id, ud.get("name", ""), ud.get("description", ""))
    if pid:
        # After adding, prompt for reseller PID
        user_data[call.from_user.id] = {"product_id": pid}
        set_state(call.from_user.id, "admin_set_product_pid")
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, 
            f"✅ Product added!\nID: `{pid}`\n\n"
            f"🔌 *Reseller API*\n"
            f"Send the *Product PID* from xyzcheats.com reseller panel,\n"
            f"or send `skip` to skip.",  parse_mode="Markdown"
        )
    else:
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "❌ Product already exists!")
    bot.answer_callback_query(call.id)


# ========== PLANS ==========

@bot.message_handler(func=lambda m: m.text == "📋 Plans" and is_admin(m.from_user.id))
def admin_plans_handler(message):
    clear_state(message.from_user.id)
    all_plans = get_plans(active_only=False)
    text = "📋 *Plan Management*\n\n"
    for pl in all_plans:
        st = "🟢" if pl['is_active'] else "🔴"
        text += f"{st} ID:{pl['id']} | {pl['name']} | {format_amount(pl['price'])} | {pl.get('duration','')}\n"
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ « Add Plan", callback_data="admin_add_plan"), InlineKeyboardButton("✏️ « Edit Plan", callback_data="admin_edit_plan_select"))
    kb.add(InlineKeyboardButton("🗑 « Delete Plan", callback_data="admin_del_plan_select"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_plan")
def cb_admin_add_plan(call):
    products = get_products(active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        kb.add(InlineKeyboardButton(f"{p['name']} (ID:{p['id']})", callback_data=f"addplan_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "📋 Select product:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("addplan_"))
def cb_addplan(call):
    pid = int(call.data.split("_")[1])
    user_data[call.from_user.id] = {"product_id": pid}
    set_state(call.from_user.id, "admin_add_plan_name")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "📋 Send *plan name*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_plan_select")
def cb_admin_edit_plan_select(call):
    plans = get_plans(active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in plans:
        kb.add(InlineKeyboardButton(f"ID:{p['id']} | {p['name']} | {format_amount(p['price'])}", callback_data=f"editplan_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✏️ Select plan to edit:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("editplan_"))
def cb_editplan(call):
    pid = int(call.data.split("_")[1])
    user_data[call.from_user.id] = {"plan_id": pid}
    set_state(call.from_user.id, "admin_edit_plan_field")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✏️ Send *name*, *price*, *duration*, or *toggle*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_del_plan_select")
def cb_admin_del_plan_select(call):
    plans = get_plans(active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in plans:
        kb.add(InlineKeyboardButton(f"🗑 ID:{p['id']} | {p['name']}", callback_data=f"delplan_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🗑 Select plan to delete:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delplan_"))
def cb_delplan(call):
    pid = int(call.data.split("_")[1])
    delete_plan(pid)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✅ Plan `{pid}` deleted!")
    bot.answer_callback_query(call.id, "Deleted!")

# ========== STOCK KEY MANAGER ==========

@bot.message_handler(func=lambda m: m.text == "🔑 Stock Keys" and is_admin(m.from_user.id))
def admin_keys_handler(message):
    clear_state(message.from_user.id)
    categories = get_categories()
    kb = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        kb.add(InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"skm_cat_{cat['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, "🔑 *Stock Key Manager*\n\nSelect category:", reply_markup=kb, parse_mode="Markdown")


# ===== CATEGORY → PRODUCT SELECTION =====

@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_cat_"))
def cb_skm_cat(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    cat_id = int(call.data.split("_")[2])
    products = get_products(category_id=cat_id, active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for p in products:
        counts = get_stock_keys_count(product_id=p['id'])
        kb.add(InlineKeyboardButton(f"{p['name']} (🔑{counts['available']}/{counts['total']})", callback_data=f"skm_prod_{p['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Select Category", callback_data="skm_back_cat"))
    cat = get_category(cat_id)
    cat_label = f"{cat['emoji']} {cat['name']}" if cat else "Category"
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"🔑 *Stock Key Manager*\n{cat_label}\n\nSelect product:",  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "skm_back_cat")
def cb_skm_back_cat(call):
    categories = get_categories()
    kb = InlineKeyboardMarkup(row_width=1)
    for cat in categories:
        kb.add(InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"skm_cat_{cat['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🔑 *Stock Key Manager*\n\nSelect category:",  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== PRODUCT → PLAN SELECTION =====

@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_prod_"))
def cb_skm_prod(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    pid = int(call.data.split("_")[2])
    product = get_product(pid)
    if not product: bot.answer_callback_query(call.id, "Product not found!", show_alert=True); return
    plans = get_plans(pid, active_only=False)
    kb = InlineKeyboardMarkup(row_width=1)
    for pl in plans:
        counts = get_stock_keys_count(product_id=pid, plan_id=pl['id'])
        kb.add(InlineKeyboardButton(f"{pl['name']} — {format_amount(pl['price'])} (🔑{counts['available']})", callback_data=f"skm_plan_{pid}_{pl['id']}_{pl['name']}"))
    # Also add "All Plans" option
    all_counts = get_stock_keys_count(product_id=pid)
    kb.add(InlineKeyboardButton(f"📦 All Plans (🔑{all_counts['available']}/{all_counts['total']})", callback_data=f"skm_plan_{pid}_0_All Plans"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data=f"skm_cat_{product['category_id']}"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"🔑 *Stock Key Manager*\n📦 {product['name']}\n\nSelect plan:",  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== PLAN → ACTIONS =====

def _build_plan_label(plan_name):
    # Replace special chars for callback data
    return plan_name.replace(" ", "_").replace("/", "-")[:30]

def _decode_plan_label(label):
    return label.replace("_", " ")


def _get_price_for_plan(pid, plid):
    """Resolve the price for a plan. Returns 0 if 'All Plans' or plan not found."""
    if plid <= 0:
        return 0
    plan = get_plan(plid)
    return plan["price"] if plan else 0


@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_plan_"))
def cb_skm_plan(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    parts = call.data.split("_", 4)
    pid = int(parts[2])
    plid = int(parts[3])
    plan_name = parts[4] if len(parts) > 4 else "All Plans"

    product = get_product(pid)
    plan = get_plan(plid) if plid > 0 else None
    price = plan["price"] if plan else 0
    counts = get_stock_keys_count(product_id=pid, plan_id=(plid if plid > 0 else None), price=(price if plid > 0 else None))

    plan_display = plan['name'] if plan else "All Plans"
    price_display = format_amount(price) if plan else "N/A"

    text = (
        f"🔑 *Stock Key Manager*\n\n"
        f"📦 *Product:* {product['name']}\n"
        f"📋 *Plan:* {plan_display}\n"
    )
    if plan:
        text += f"💰 *Price:* {price_display}\n"
    text += (
        f"━━━━━━━━━━━━━━━━\n"
        f"🟢 Available: *{counts['available']}*\n"
        f"🔒 Used: *{counts['used']}*\n"
        f"📦 Total: *{counts['total']}*\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"Choose an action:"
    )

    # Store in user_data — price is critical for exact matching
    user_data[call.from_user.id] = {
        "product_id": pid,
        "plan_id": plid if plid > 0 else None,
        "plan_name": plan_display,
        "product_name": product['name'],
        "price": price,
    }

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Add Keys", callback_data=f"skm_action_{pid}_{plid}_add"))
    kb.add(InlineKeyboardButton("📋 View Keys", callback_data=f"skm_action_{pid}_{plid}_view"))
    kb.add(InlineKeyboardButton("🗑 Delete Keys", callback_data=f"skm_action_{pid}_{plid}_del"))
    kb.add(InlineKeyboardButton("📂 Import TXT", callback_data=f"skm_action_{pid}_{plid}_import"))
    kb.add(InlineKeyboardButton("📤 Export TXT", callback_data=f"skm_action_{pid}_{plid}_export"))
    kb.add(InlineKeyboardButton("🔙 « Select Plan", callback_data=f"skm_prod_{pid}"))

    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== ACTION DISPATCHER =====

@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_action_"))
def cb_skm_action(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    parts = call.data.split("_", 4)
    pid = int(parts[2])
    plid = int(parts[3])
    action = parts[4]

    ud = user_data.get(call.from_user.id, {})
    product_name = ud.get("product_name", "N/A")
    plan_name = ud.get("plan_name", "All Plans")
    price = ud.get("price", 0)
    price_display = f"💰 *Price:* {CURRENCY_SYMBOL}{int(price)}" if price > 0 else ""

    if action == "add":
        set_state(call.from_user.id, f"skm_add_keys_{pid}_{plid}")
        text = (
            f"➕ *Add Keys*\n\n"
            f"📦 *Product:* {product_name}\n"
            f"📋 *Plan:* {plan_name}\n"
        )
        if price_display:
            text += f"{price_display}\n"
        text += (
            f"\nPaste keys below (*one per line*):\n"
            f"```\n675556777\n123456789\n987654321\n456789123\n```"
        )
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, text,  parse_mode="Markdown")

    elif action == "view":
        _show_keys_view(call.message, pid, plid, price, product_name, plan_name, page=0, edit=True)

    elif action == "del":
        _show_delete_menu(call.message, pid, plid, price, product_name, plan_name, edit=True)

    elif action == "import":
        set_state(call.from_user.id, f"skm_import_keys_{pid}_{plid}")
        text = (
            f"📂 *Import Keys from TXT*\n\n"
            f"📦 *Product:* {product_name}\n"
            f"📋 *Plan:* {plan_name}\n"
        )
        if price_display:
            text += f"{price_display}\n"
        text += f"\nSend a *.txt file* or paste text with keys (*one per line*):"
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, text,  parse_mode="Markdown")

    elif action == "export":
        _do_export_keys(call, pid, plid, price, product_name, plan_name)

    bot.answer_callback_query(call.id)


# ===== VIEW KEYS =====

PAGE_SIZE = 10

def _show_keys_view(message, pid, plid, price, product_name, plan_name, page=0, edit=False):
    plan_filter = plid if plid > 0 else None
    price_filter = price if plid > 0 else None
    keys = get_stock_keys(product_id=pid, plan_id=plan_filter, price=price_filter)
    total = len(keys)
    start = page * PAGE_SIZE
    page_keys = keys[start:start + PAGE_SIZE]
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)

    text = (
        f"📋 *View Keys* — Page {page+1}/{total_pages}\n\n"
        f"📦 *Product:* {product_name}\n"
        f"📋 *Plan:* {plan_name}\n"
    )
    if price > 0:
        text += f"💰 *Price:* {format_amount(price)}\n"
    text += f"━━━━━━━━━━━━━━━━\n"

    if not page_keys:
        text += "\n_No keys found._\n"
    else:
        for i, k in enumerate(page_keys, start=start+1):
            emoji = "🟢" if k['status'] == 'available' else "🔒"
            key_display = str(k['key_value'])[:40]
            text += f"{emoji} `{k['id']}`: `{key_display}`\n"
        text += f"\n━━━━━━━━━━━━━━━━\n"

    kb = InlineKeyboardMarkup(row_width=2)
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ « Previous", callback_data=f"skm_view_{pid}_{plid}_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton("Next »  ", callback_data=f"skm_view_{pid}_{plid}_{page+1}"))
    if nav_buttons:
        kb.add(*nav_buttons)
    kb.add(InlineKeyboardButton("🔙 « Actions", callback_data=f"skm_plan_{pid}_{plid}_{plan_name.replace(' ', '_')}"))

    if edit:
        safe_delete_message(message.chat.id, message.message_id)
        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_view_"))
def cb_skm_view(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    parts = call.data.split("_")
    pid = int(parts[2])
    plid = int(parts[3])
    page = int(parts[4])
    ud = user_data.get(call.from_user.id, {})
    _show_keys_view(call.message, pid, plid, ud.get("price", 0), ud.get("product_name", "N/A"), ud.get("plan_name", "All Plans"), page=page, edit=True)
    bot.answer_callback_query(call.id)


# ===== DELETE KEYS =====

def _show_delete_menu(message, pid, plid, price, product_name, plan_name, edit=False):
    plan_filter = plid if plid > 0 else None
    price_filter = price if plid > 0 else None
    keys = get_stock_keys(product_id=pid, plan_id=plan_filter, price=price_filter)
    total = len(keys)
    counts = get_stock_keys_count(product_id=pid, plan_id=plan_filter, price=price_filter)

    text = (
        f"🗑 *Delete Keys*\n\n"
        f"📦 *Product:* {product_name}\n"
        f"📋 *Plan:* {plan_name}\n"
    )
    if price > 0:
        text += f"💰 *Price:* {format_amount(price)}\n"
    text += (
        f"━━━━━━━━━━━━━━━━\n"
        f"🟢 Available: *{counts['available']}*\n"
        f"🔒 Used: *{counts['used']}*\n"
        f"📦 Total: *{counts['total']}*\n"
        f"━━━━━━━━━━━━━━━━\n\n"
        f"Choose delete mode:"
    )

    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔢 Delete One Key (by ID)", callback_data=f"skm_delone_{pid}_{plid}"))
    if total > 0:
        kb.add(InlineKeyboardButton(f"🗑 Delete ALL Keys ({total} keys)", callback_data=f"skm_delall_{pid}_{plid}"))
    kb.add(InlineKeyboardButton("🔙 « Actions", callback_data=f"skm_plan_{pid}_{plid}_{plan_name.replace(' ', '_')}"))

    if edit:
        safe_delete_message(message.chat.id, message.message_id)
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_delone_"))
def cb_skm_delone(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    parts = call.data.split("_")
    pid = int(parts[2])
    plid = int(parts[3])
    set_state(call.from_user.id, f"skm_del_key_{pid}_{plid}")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🗑 *Delete One Key*\n\nSend the *Key ID* to delete (e.g. `5`):",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_delall_"))
def cb_skm_delall(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    parts = call.data.split("_")
    pid = int(parts[2])
    plid = int(parts[3])
    ud = user_data.get(call.from_user.id, {})
    price = ud.get("price", 0)
    plan_filter = plid if plid > 0 else None
    price_filter = price if plid > 0 else None
    total = get_stock_keys_count(product_id=pid, plan_id=plan_filter, price=price_filter)["total"]

    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ YES, DELETE ALL", callback_data=f"skm_confirm_delall_{pid}_{plid}"),
        InlineKeyboardButton("❌ CANCEL", callback_data=f"skm_action_{pid}_{plid}_del")
    )
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"⚠️ *Confirm Delete ALL*\n\nThis will delete *{total} keys* for this product+plan.\nThis cannot be undone!\n\nAre you sure?",  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("skm_confirm_delall_"))
def cb_skm_confirm_delall(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    parts = call.data.split("_")
    pid = int(parts[3])
    plid = int(parts[4])
    ud = user_data.get(call.from_user.id, {})
    price = ud.get("price", 0)
    plan_filter = plid if plid > 0 else None
    price_filter = price if plid > 0 else None
    deleted = delete_keys_by_product_plan(pid, plan_filter, price_filter)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✅ Deleted *{deleted}* keys!",  parse_mode="Markdown")
    bot.answer_callback_query(call.id, f"Deleted {deleted} keys!", show_alert=True)


# ===== EXPORT KEYS =====

def _do_export_keys(call, pid, plid, price, product_name, plan_name):
    plan_filter = plid if plid > 0 else None
    price_filter = price if plid > 0 else None
    keys = get_stock_keys(product_id=pid, plan_id=plan_filter, price=price_filter)
    if not keys:
        bot.answer_callback_query(call.id, "No keys to export!", show_alert=True)
        return

    available_text = export_stock_keys_text(pid, plan_filter, price_filter, status="available")
    counts = get_stock_keys_count(product_id=pid, plan_id=plan_filter, price=price_filter)

    # Send available keys
    if available_text:
        safe_name = product_name.replace(" ", "_").replace("/", "-")[:40]
        from io import BytesIO
        buf = BytesIO(available_text.encode('utf-8'))
        buf.name = f"keys_{safe_name}_available.txt"
        cap = f"🟢 *Available Keys*\n📦 {product_name}\n📋 {plan_name}\n"
        if price > 0:
            cap += f"💰 {format_amount(price)}\n"
        cap += f"🔑 {counts['available']} keys"
        bot.send_document(call.message.chat.id, buf, caption=cap, parse_mode="Markdown")

    # Send used keys if any
    used_text = export_stock_keys_text(pid, plan_filter, price_filter, status="used")
    if used_text:
        from io import BytesIO
        safe_name = product_name.replace(" ", "_").replace("/", "-")[:40]
        buf = BytesIO(used_text.encode('utf-8'))
        buf.name = f"keys_{safe_name}_used.txt"
        cap = f"🔒 *Used Keys*\n📦 {product_name}\n📋 {plan_name}\n"
        if price > 0:
            cap += f"💰 {format_amount(price)}\n"
        cap += f"🔑 {counts['used']} keys"
        bot.send_document(call.message.chat.id, buf, caption=cap, parse_mode="Markdown")

    bot.answer_callback_query(call.id, f"Exported {counts['total']} keys!", show_alert=True)


# ========== USERS ==========

@bot.message_handler(func=lambda m: m.text == "👥 Users" and is_admin(m.from_user.id))
def admin_users_handler(message):
    users = get_users(limit=50)
    total = get_user_count()
    text = f"👥 *Users ({total})*\n\n_Recent:_\n"
    for u in users[:20]:
        badge = "🚫" if u['is_banned'] else "👤"
        name = u['first_name'] or f"ID:{u['user_id']}"
        if u['username']: name += f" (@{u['username']})"
        text += f"{badge} {name}\n"
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🚫 Banned Users", callback_data="admin_users_banned"), InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_users_banned")
def cb_admin_users_banned(call):
    users = get_users(banned_only=True, limit=50)
    lines = [f"👤 {u['first_name'] or u['user_id']} (@{u.get('username','N/A')})" for u in users]
    text = "🚫 *Banned Users*\n\n" + "\n".join(lines) if lines else "No banned users."
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    try:
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    except: pass
    bot.answer_callback_query(call.id)


# ========== BROADCAST ==========

@bot.message_handler(func=lambda m: m.text == "📢 Broadcast" and is_admin(m.from_user.id))
def admin_broadcast_handler(message):
    set_state(message.from_user.id, "admin_broadcast_text")
    bot.send_message(message.chat.id, "📢 *Broadcast*\nSend the message to all users:", parse_mode="Markdown")


# ========== STATISTICS ==========

@bot.message_handler(func=lambda m: m.text == "📈 Statistics" and is_admin(m.from_user.id))
def admin_stats_handler(message):
    s = get_stats()
    text = (
        f"📈 *Bot Statistics*\n\n"
        f"👥 Users: {s['total_users']}\n"
        f"📦 Products: {s['total_products']}\n"
        f"📋 Orders: {s['total_orders']}\n"
        f"⏳ Pending: {s['pending_orders']}\n"
        f"✅ Approved: {s['approved_orders']}\n"
        f"❌ Rejected: {s['rejected_orders']}\n"
        f"🔑 Avail Keys: {s['available_keys']}\n"
        f"🔒 Used Keys: {s['used_keys']}\n"
        f"💰 Revenue: {CURRENCY_SYMBOL}{s['total_revenue']:.2f}"
    )
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


# ========== CONFIG ==========

@bot.message_handler(func=lambda m: m.text == "⚙️ Config" and is_admin(m.from_user.id))
def admin_config_handler(message):
    from reseller_api import is_reseller_api_configured
    bcfg = "✅ Configured" if binance_api.is_configured() else "❌ Not Configured"
    bena = "🟢 Enabled" if is_binance_enabled() else "🔴 Disabled"
    bcharge = get_binance_extra_charge()
    reseller_status = "🟢 Configured" if is_reseller_api_configured() else "🔴 Not Configured"
    text = (
        f"⚙️ *Bot Config*\n\n"
        f"🟨 Binance: {bcfg} ({bena})\n"
        f"   Extra Charge: {format_amount(bcharge)}\n"
        f"🔌 Reseller API: {reseller_status}\n"
        f"🏦 UPI: `{get_config('upi_id', config.UPI_ID)}`\n"
        f"   Name: {get_config('upi_name', config.UPI_NAME)}\n"
        f"💙 PhonePe: `{get_config('phonepe_number', config.PHONEPE_NUMBER)}`\n"
        f"🟢 GPay: `{get_config('gpay_number', config.GOOGLEPAY_NUMBER)}`\n"
        f"🔵 Paytm: `{get_config('paytm_number', config.PAYTM_NUMBER)}`"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("💳 « Payment Settings", callback_data="admin_config_payment"),
           InlineKeyboardButton("🟨 « Binance Settings", callback_data="admin_config_binance"))
    kb.add(InlineKeyboardButton("📸 « Payment QR Codes", callback_data="admin_config_payment_qr"))
    kb.add(InlineKeyboardButton("🔔 « Support & Channels", callback_data="admin_config_sc"))
    kb.add(InlineKeyboardButton("🗂 « Categories", callback_data="admin_config_categories"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


# ---- Payment Settings (UPI ID, PhonePe, GPay, Paytm) ----

@bot.callback_query_handler(func=lambda call: call.data == "admin_config_payment")
def cb_admin_config_payment(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    upi_id = get_config("upi_id", config.UPI_ID)
    upi_name = get_config("upi_name", config.UPI_NAME)
    phonepe = get_config("phonepe_number", config.PHONEPE_NUMBER) or "Not set"
    gpay = get_config("gpay_number", config.GOOGLEPAY_NUMBER) or "Not set"
    paytm = get_config("paytm_number", config.PAYTM_NUMBER) or "Not set"
    support = get_config("support_username", config.SUPPORT_USERNAME)

    text = (
        f"💳 *Payment Settings*\n\n"
        f"🏦 *UPI ID:* `{upi_id}`\n"
        f"   *Name:* {upi_name}\n"
        f"💙 *PhonePe:* `{phonepe}`\n"
        f"🟢 *GPay:* `{gpay}`\n"
        f"🔵 *Paytm:* `{paytm}`\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📞 *Support:* @{support}\n\n"
        f"Tap a field to update:"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🏦 Change UPI ID", callback_data="payset_upi_id"))
    kb.add(InlineKeyboardButton("👤 Change UPI Name", callback_data="payset_upi_name"))
    kb.add(InlineKeyboardButton("💙 Change PhonePe Number", callback_data="payset_phonepe"))
    kb.add(InlineKeyboardButton("🟢 Change GPay Number", callback_data="payset_gpay"))
    kb.add(InlineKeyboardButton("🔵 Change Paytm Number", callback_data="payset_paytm"))
    kb.add(InlineKeyboardButton("📞 Change Support Username", callback_data="payset_support"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("payset_"))
def cb_payset_field(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    field = call.data.replace("payset_", "")
    field_labels = {
        "upi_id": "UPI ID", "upi_name": "UPI Name",
        "phonepe": "PhonePe Number", "gpay": "GPay Number", "paytm": "Paytm Number",
        "support": "Support Username"
    }
    set_state(call.from_user.id, f"admin_payset_{field}")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"Send new *{field_labels.get(field, field)}*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ---- Binance Settings ----

@bot.callback_query_handler(func=lambda call: call.data == "admin_config_binance")
def cb_admin_config_binance(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    enabled = is_binance_enabled()
    charge = get_binance_extra_charge()
    text = (
        f"🟨 *Binance Pay Settings*\n\n"
        f"Status: {'🟢 Enabled' if enabled else '🔴 Disabled'}\n"
        f"Extra Charge: {format_amount(charge)}"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("🔑 Set API Key", callback_data="config_binance_apikey"))
    kb.add(InlineKeyboardButton("🔐 Set Secret Key", callback_data="config_binance_secret"))
    kb.add(InlineKeyboardButton("🏪 Set Merchant ID", callback_data="config_binance_merchant"))
    kb.add(InlineKeyboardButton("🔗 Set Webhook Secret", callback_data="config_binance_webhook_secret"))
    kb.add(InlineKeyboardButton("💰 Set Extra Charge", callback_data="config_binance_extra_charge"))
    kb.add(InlineKeyboardButton(
        "🔴 Disable Binance" if enabled else "🟢 Enable Binance",
        callback_data="config_binance_toggle"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("config_binance_"))
def cb_config_binance_field(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    field = call.data.replace("config_binance_", "")
    if field == "toggle":
        current = is_binance_enabled()
        set_binance_enabled(not current)
        bot.answer_callback_query(call.id, f"Binance {'Disabled' if current else 'Enabled'}!", show_alert=True)
        cb_admin_config_binance(call)
        return
    if field == "extra_charge":
        set_state(call.from_user.id, "admin_config_binance_extra_charge")
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, f"💰 Send new *Binance Extra Charge* (current: {format_amount(get_binance_extra_charge())}):",  parse_mode="Markdown")
        bot.answer_callback_query(call.id)
        return
    set_state(call.from_user.id, f"admin_config_binance_{field}")
    prompt_map = {
        "apikey": "API Key",
        "secret": "Secret Key",
        "merchant": "Merchant ID",
        "webhook_secret": "Webhook Secret",
    }
    prompt = prompt_map.get(field, field)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"Send the Binance *{prompt}*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ---- Payment QR Code Management ----

@bot.callback_query_handler(func=lambda call: call.data == "admin_config_payment_qr")
def cb_admin_config_payment_qr(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    qr_status = {}
    for m, path in [("upi", UPI_QR_PATH), ("phonepe", PHONEPE_QR_PATH), ("gpay", GPAY_QR_PATH), ("paytm", PAYTM_QR_PATH)]:
        qr_status[m] = "✅" if os.path.exists(path) else "❌"
    text = (
        f"📸 *Payment QR Codes*\n\n"
        f"Upload a static QR code image for each method.\n"
        f"These will be shown to customers during payment.\n\n"
        f"{qr_status['upi']} 🏦 UPI QR\n"
        f"{qr_status['phonepe']} 💙 PhonePe QR\n"
        f"{qr_status['gpay']} 🟢 Google Pay QR\n"
        f"{qr_status['paytm']} 🔵 Paytm QR\n\n"
        f"Tap a method to upload its QR code:"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton(f"{qr_status['upi']} Upload UPI QR", callback_data="uploadqr_upi"))
    kb.add(InlineKeyboardButton(f"{qr_status['phonepe']} Upload PhonePe QR", callback_data="uploadqr_phonepe"))
    kb.add(InlineKeyboardButton(f"{qr_status['gpay']} Upload GPay QR", callback_data="uploadqr_gpay"))
    kb.add(InlineKeyboardButton(f"{qr_status['paytm']} Upload Paytm QR", callback_data="uploadqr_paytm"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("uploadqr_"))
def cb_uploadqr(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    method = call.data.split("_")[1]
    user_data[call.from_user.id] = {"qr_method": method}
    set_state(call.from_user.id, f"admin_upload_qr_{method}")
    method_names = {"upi": "UPI", "phonepe": "PhonePe", "gpay": "Google Pay", "paytm": "Paytm"}
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"📸 Send the *{method_names.get(method, method)} QR code image* (photo):",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== SUPPORT & CHANNEL SETTINGS ==========

@bot.callback_query_handler(func=lambda call: call.data == "admin_config_sc")
def cb_admin_config_sc(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    s = get_all_support_channel_settings()

    sup_ena = "🟢 ON" if s["support_enabled"] == "true" else "🔴 OFF"
    ch_ena = "🟢 ON" if s["channel_enabled"] == "true" else "🔴 OFF"
    res_ena = "🟢 ON" if s["reseller_enabled"] == "true" else "🔴 OFF"

    text = (
        f"🔔 *Support & Channel Settings*\n\n"
        f"📞 *Support* — {sup_ena}\n"
        f"   Username: @{s['support_username']}\n"
        f"   Link: {s['support_link']}\n"
        f"   Button: {s['support_button_text']}\n\n"
        f"📢 *Official Channel* — {ch_ena}\n"
        f"   Username: @{s['channel_username']}\n"
        f"   Link: {s['channel_link']}\n"
        f"   Button: {s['channel_button_text']}\n\n"
        f"🤝 *Reseller Channel* — {res_ena}\n"
        f"   Username: @{s['reseller_username'] or 'Not set'}\n"
        f"   Link: {s['reseller_link'] or 'Not set'}\n"
        f"   Button: {s['reseller_button_text']}\n\n"
        f"Select a section to manage:"
    )
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("📞 Support Settings", callback_data="sc_sub_support"))
    kb.add(InlineKeyboardButton("📢 Channel Settings", callback_data="sc_sub_channel"))
    kb.add(InlineKeyboardButton("🤝 Reseller Settings", callback_data="sc_sub_reseller"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== SUPPORT SUB-MENU =====

@bot.callback_query_handler(func=lambda call: call.data == "sc_sub_support")
def cb_sc_sub_support(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    s = get_all_support_channel_settings()
    ena = "🟢 Enabled" if s["support_enabled"] == "true" else "🔴 Disabled"
    text = (
        f"📞 *Support Settings* — {ena}\n\n"
        f"Username: @{s['support_username']}\n"
        f"Link: {s['support_link']}\n"
        f"Button Text: {s['support_button_text']}"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    toggle_text = "🔴 Disable" if s["support_enabled"] == "true" else "🟢 Enable"
    kb.add(InlineKeyboardButton(f"{toggle_text} Support", callback_data="sc_toggle_support"))
    kb.add(InlineKeyboardButton("✏️ Change Username", callback_data="sc_set_support_username"))
    kb.add(InlineKeyboardButton("✏️ Change Link", callback_data="sc_set_support_link"))
    kb.add(InlineKeyboardButton("✏️ Change Button Text", callback_data="sc_set_support_btn"))
    kb.add(InlineKeyboardButton("🔙 « Back to S&C", callback_data="admin_config_sc"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== CHANNEL SUB-MENU =====

@bot.callback_query_handler(func=lambda call: call.data == "sc_sub_channel")
def cb_sc_sub_channel(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    s = get_all_support_channel_settings()
    ena = "🟢 Enabled" if s["channel_enabled"] == "true" else "🔴 Disabled"
    text = (
        f"📢 *Official Channel Settings* — {ena}\n\n"
        f"Username: @{s['channel_username']}\n"
        f"Link: {s['channel_link']}\n"
        f"Button Text: {s['channel_button_text']}"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    toggle_text = "🔴 Disable" if s["channel_enabled"] == "true" else "🟢 Enable"
    kb.add(InlineKeyboardButton(f"{toggle_text} Channel", callback_data="sc_toggle_channel"))
    kb.add(InlineKeyboardButton("✏️ Change Username", callback_data="sc_set_channel_username"))
    kb.add(InlineKeyboardButton("✏️ Change Link", callback_data="sc_set_channel_link"))
    kb.add(InlineKeyboardButton("✏️ Change Button Text", callback_data="sc_set_channel_btn"))
    kb.add(InlineKeyboardButton("🔙 « Back to S&C", callback_data="admin_config_sc"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== RESELLER SUB-MENU =====

@bot.callback_query_handler(func=lambda call: call.data == "sc_sub_reseller")
def cb_sc_sub_reseller(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    s = get_all_support_channel_settings()
    ena = "🟢 Enabled" if s["reseller_enabled"] == "true" else "🔴 Disabled"
    text = (
        f"🤝 *Reseller Channel Settings* — {ena}\n\n"
        f"Username: @{s['reseller_username'] or 'Not set'}\n"
        f"Link: {s['reseller_link'] or 'Not set'}\n"
        f"Button Text: {s['reseller_button_text']}"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    toggle_text = "🔴 Disable" if s["reseller_enabled"] == "true" else "🟢 Enable"
    kb.add(InlineKeyboardButton(f"{toggle_text} Reseller", callback_data="sc_toggle_reseller"))
    kb.add(InlineKeyboardButton("✏️ Change Username", callback_data="sc_set_reseller_username"))
    kb.add(InlineKeyboardButton("✏️ Change Link", callback_data="sc_set_reseller_link"))
    kb.add(InlineKeyboardButton("✏️ Change Button Text", callback_data="sc_set_reseller_btn"))
    kb.add(InlineKeyboardButton("🔙 « Back to S&C", callback_data="admin_config_sc"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ===== TOGGLE HANDLERS =====

@bot.callback_query_handler(func=lambda call: call.data == "sc_toggle_support")
def cb_sc_toggle_support(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    current = is_support_enabled()
    set_setting("support_enabled", "false" if current else "true")
    bot.answer_callback_query(call.id, f"Support {'Disabled' if current else 'Enabled'}!", show_alert=True)
    cb_sc_sub_support(call)


@bot.callback_query_handler(func=lambda call: call.data == "sc_toggle_channel")
def cb_sc_toggle_channel(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    current = is_channel_enabled()
    set_setting("channel_enabled", "false" if current else "true")
    bot.answer_callback_query(call.id, f"Channel {'Disabled' if current else 'Enabled'}!", show_alert=True)
    cb_sc_sub_channel(call)


@bot.callback_query_handler(func=lambda call: call.data == "sc_toggle_reseller")
def cb_sc_toggle_reseller(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    current = is_reseller_enabled()
    set_setting("reseller_enabled", "false" if current else "true")
    bot.answer_callback_query(call.id, f"Reseller {'Disabled' if current else 'Enabled'}!", show_alert=True)
    cb_sc_sub_reseller(call)


# ===== FIELD SET PROMPTS =====

@bot.callback_query_handler(func=lambda call: call.data.startswith("sc_set_"))
def cb_sc_set_field(call):
    if not is_admin(call.from_user.id): bot.answer_callback_query(call.id, "Admin only!", show_alert=True); return
    field = call.data.replace("sc_set_", "")
    field_labels = {
        "support_username": "Support Username (without @)",
        "support_link": "Support Telegram Link (e.g. https://t.me/...)",
        "support_btn": "Support Button Text",
        "channel_username": "Channel Username (without @)",
        "channel_link": "Channel Telegram Link (e.g. https://t.me/...)",
        "channel_btn": "Channel Button Text",
        "reseller_username": "Reseller Username (without @)",
        "reseller_link": "Reseller Telegram Link (e.g. https://t.me/...)",
        "reseller_btn": "Reseller Button Text",
    }
    set_state(call.from_user.id, f"admin_sc_set_{field}")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✏️ Send new *{field_labels.get(field, field)}*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== CATEGORIES ==========

@bot.message_handler(func=lambda m: m.text == "🗂 Categories" and is_admin(m.from_user.id))
def admin_categories_direct_handler(message):
    """Direct access to Categories from admin keyboard"""
    clear_state(message.from_user.id)
    categories = get_categories()
    lines = [f"{c['emoji']} *{c['name']}* (ID:`{c['id']}`)" for c in categories]
    text = "🗂 *Categories*\n\n" + "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Add Category", callback_data="admin_add_category"))
    kb.add(InlineKeyboardButton("🗑 Delete Category", callback_data="admin_del_category"))
    kb.add(InlineKeyboardButton("✏️ Edit Category", callback_data="admin_edit_category_select"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_config_categories")
def cb_admin_config_categories(call):
    categories = get_categories()
    lines = [f"{c['emoji']} *{c['name']}* (ID:`{c['id']}`)" for c in categories]
    text = "🗂 *Categories*\n\n" + "\n".join(lines)
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("➕ Add Category", callback_data="admin_add_category"))
    kb.add(InlineKeyboardButton("🗑 Delete Category", callback_data="admin_del_category"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text,  reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_category")
def cb_admin_add_category(call):
    set_state(call.from_user.id, "admin_add_category_name")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "Send the *category name*:",  parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_del_category")
def cb_admin_del_category(call):
    categories = get_categories()
    kb = InlineKeyboardMarkup(row_width=1)
    for c in categories:
        kb.add(InlineKeyboardButton(f"🗑 {c['emoji']} {c['name']}", callback_data=f"delcat_{c['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_config_categories"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "🗑 Select category to delete:",  reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_edit_category_select")
def cb_admin_edit_category_select(call):
    """Edit category — select which one"""
    categories = get_categories()
    kb = InlineKeyboardMarkup(row_width=1)
    for c in categories:
        kb.add(InlineKeyboardButton(f"✏️ {c['emoji']} {c['name']}", callback_data=f"editcat_{c['id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_config_categories"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✏️ Select category to edit:", reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("editcat_"))
def cb_editcat(call):
    """Edit category — choose what to edit"""
    cat_id = int(call.data.split("_")[1])
    cat = get_category(cat_id)
    if not cat:
        bot.answer_callback_query(call.id, "Category not found!", show_alert=True)
        return
    user_data[call.from_user.id] = {"cat_id": cat_id}
    text = f"✏️ *Edit Category*\n\n{cat['emoji']} *{cat['name']}* (ID:`{cat_id}`)\n\nWhat do you want to change?"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📛 Change Name", callback_data=f"editcat_name_{cat_id}"))
    kb.add(InlineKeyboardButton("😀 Change Emoji", callback_data=f"editcat_emoji_{cat_id}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_config_categories"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("editcat_name_"))
def cb_editcat_name(call):
    cat_id = int(call.data.split("_")[2])
    set_state(call.from_user.id, f"admin_edit_category_name_{cat_id}")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "📛 Send the *new category name*:", parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("editcat_emoji_"))
def cb_editcat_emoji(call):
    cat_id = int(call.data.split("_")[2])
    set_state(call.from_user.id, f"admin_edit_category_emoji_{cat_id}")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "😀 Send the *new emoji* (e.g. 🎮, 📱, 💻):", parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("delcat_"))
def cb_delcat(call):
    delete_category(int(call.data.split("_")[1]))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✅ Category deleted!")
    bot.answer_callback_query(call.id, "Deleted!")


# ========== ADMIN ACCESS CONTROL (Multi-Admin) ==========

@bot.message_handler(func=lambda m: m.text == "👑 Admins" and is_admin(m.from_user.id))
def admin_roles_handler(message):
    if not is_super_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Only *Super Admin* can manage admin access!", parse_mode="Markdown")
        return
    clear_state(message.from_user.id)
    admins = get_admin_roles()
    text = "👑 *Admin Access Control*\n\n"
    if not admins:
        text += "_No additional admins._\n\n"
    else:
        for a in admins:
            status = "🟢" if a['is_active'] else "🔴"
            role_emoji = {"super_admin": "⭐", "admin": "👑", "editor": "✏️"}.get(a['role'], "👤")
            name = a.get('first_name') or a.get('username') or str(a['user_id'])
            text += f"{status} {role_emoji} *{name}*\n   Role: `{a['role']}` | ID: `{a['user_id']}`\n   Permissions: `{a.get('permissions', 'default')}`\n\n"
    text += "Select an action:"
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("➕ Add Admin", callback_data="admin_access_add"))
    if admins:
        kb.add(InlineKeyboardButton("✏️ Manage Admin", callback_data="admin_access_manage"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


@bot.callback_query_handler(func=lambda call: call.data == "admin_access_add")
def cb_admin_access_add(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    set_state(call.from_user.id, "admin_access_add_user_id")
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "➕ *Add Admin*\n\nSend the *User ID* of the person you want to add as admin:", parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_access_manage")
def cb_admin_access_manage(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    admins = get_admin_roles()
    kb = InlineKeyboardMarkup(row_width=1)
    for a in admins:
        status = "🟢" if a['is_active'] else "🔴"
        role_emoji = {"super_admin": "⭐", "admin": "👑", "editor": "✏️"}.get(a['role'], "👤")
        name = a.get('first_name') or a.get('username') or str(a['user_id'])
        kb.add(InlineKeyboardButton(f"{status} {role_emoji} {name} (ID:{a['user_id']})", callback_data=f"adm_mgmt_{a['user_id']}"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "✏️ *Manage Admins*\n\nSelect an admin to manage:", reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_mgmt_"))
def cb_adm_mgmt(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    aid = int(call.data.split("_")[2])
    role_info = get_admin_role(aid)
    if not role_info:
        bot.answer_callback_query(call.id, "Admin not found!", show_alert=True)
        return
    user_data[call.from_user.id] = {"manage_admin_id": aid}
    status = "🟢 Active" if role_info['is_active'] else "🔴 Inactive"
    text = (
        f"✏️ *Manage Admin*\n\n"
        f"👤 ID: `{role_info['user_id']}`\n"
        f"📛 Name: {role_info.get('first_name') or 'N/A'}\n"
        f"📎 Username: @{role_info.get('username') or 'N/A'}\n"
        f"⭐ Role: `{role_info['role']}`\n"
        f"🔐 Permissions: `{role_info.get('permissions', 'default')}`\n"
        f"📊 Status: {status}\n\n"
        f"Choose action:"
    )
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⭐ Change Role", callback_data=f"adm_chrole_{aid}"))
    kb.add(InlineKeyboardButton("🔐 Change Permissions", callback_data=f"adm_chperm_{aid}"))
    toggle_text = "🔴 Disable" if role_info['is_active'] else "🟢 Enable"
    kb.add(InlineKeyboardButton(f"{toggle_text} Admin", callback_data=f"adm_toggle_{aid}"))
    kb.add(InlineKeyboardButton("🗑 Remove Admin", callback_data=f"adm_remove_{aid}"))
    kb.add(InlineKeyboardButton("🔙 « Back to Admin List", callback_data="admin_access_manage"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_chrole_"))
def cb_adm_chrole(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    aid = int(call.data.split("_")[2])
    user_data[call.from_user.id] = {"manage_admin_id": aid}
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("⭐ Super Admin (Full Access)", callback_data=f"adm_setrole_{aid}_super_admin"))
    kb.add(InlineKeyboardButton("👑 Admin (Manage Store)", callback_data=f"adm_setrole_{aid}_admin"))
    kb.add(InlineKeyboardButton("✏️ Editor (Products + Orders Only)", callback_data=f"adm_setrole_{aid}_editor"))
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data=f"adm_mgmt_{aid}"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, "⭐ *Change Role*\n\nSelect new role:", reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_setrole_"))
def cb_adm_setrole(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    parts = call.data.split("_")
    aid = int(parts[2])
    role = parts[3]
    update_admin_role(aid, role=role)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✅ Role updated to `{role}`!", parse_mode="Markdown")
    bot.answer_callback_query(call.id, f"Role set to {role}!", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_toggle_"))
def cb_adm_toggle(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    aid = int(call.data.split("_")[2])
    role_info = get_admin_role(aid)
    if role_info:
        new_status = 0 if role_info['is_active'] else 1
        update_admin_role(aid, is_active=new_status)
        status_text = "enabled" if new_status else "disabled"
        safe_delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, f"✅ Admin `{aid}` {status_text}!", parse_mode="Markdown")
        bot.answer_callback_query(call.id, f"Admin {status_text}!", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "Admin not found!", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_remove_"))
def cb_adm_remove(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    aid = int(call.data.split("_")[2])
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(InlineKeyboardButton("✅ YES, Remove", callback_data=f"adm_confirm_remove_{aid}"))
    kb.add(InlineKeyboardButton("❌ Cancel", callback_data=f"adm_mgmt_{aid}"))
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"⚠️ *Remove Admin*\n\nAre you sure you want to remove admin `{aid}`?", reply_markup=kb, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_confirm_remove_"))
def cb_adm_confirm_remove(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    aid = int(call.data.split("_")[3])
    remove_admin_role(aid)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, f"✅ Admin `{aid}` removed!", parse_mode="Markdown")
    bot.answer_callback_query(call.id, "Admin removed!", show_alert=True)


@bot.callback_query_handler(func=lambda call: call.data.startswith("adm_chperm_"))
def cb_adm_chperm(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    aid = int(call.data.split("_")[2])
    set_state(call.from_user.id, f"admin_access_set_perm_{aid}")
    role_info = get_admin_role(aid)
    current = role_info.get("permissions", "default") if role_info else "default"
    text = (
        f"🔐 *Set Custom Permissions*\n\n"
        f"Current: `{current}`\n\n"
        f"Available permissions:\n"
        f"• `products` — Add/Edit/Delete products\n"
        f"• `plans` — Manage plans\n"
        f"• `keys` — Stock key manager\n"
        f"• `orders` — Approve/Reject orders\n"
        f"• `users` — View users & ban\n"
        f"• `broadcast` — Send broadcast\n"
        f"• `stats` — View statistics\n"
        f"• `config` — Change config\n"
        f"• `logs` — View logs\n"
        f"• `backup` — Create backup\n"
        f"• `categories` — Manage categories\n\n"
        f"Send comma-separated list (e.g. `products,orders,stats`)\n"
        f"Or send `all` for full access:"
    )
    safe_delete_message(call.message.chat.id, call.message.message_id)
    bot.send_message(call.message.chat.id, text, parse_mode="Markdown")
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("addadm_role_"))
def cb_addadm_role(call):
    if not is_super_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Super Admin only!", show_alert=True)
        return
    parts = call.data.split("_")
    aid = int(parts[2])
    role = parts[3]
    ud = user_data.get(call.from_user.id, {})
    success = add_admin_role(
        user_id=aid,
        username=ud.get("new_admin_username", ""),
        first_name=ud.get("new_admin_name", ""),
        role=role,
        added_by=call.from_user.id
    )
    clear_state(call.from_user.id)
    safe_delete_message(call.message.chat.id, call.message.message_id)
    if success:
        role_display = {"super_admin": "⭐ Super Admin", "admin": "👑 Admin", "editor": "✏️ Editor"}.get(role, role)
        bot.send_message(call.message.chat.id, f"✅ *Admin Added!*\n\n👤 ID: `{aid}`\n⭐ Role: {role_display}\n\nThey can now access the Admin Panel.", parse_mode="Markdown")
        add_log("admin_added", call.from_user.id, f"Added admin {aid} as {role}")
    else:
        bot.send_message(call.message.chat.id, "❌ This user is already an admin!", parse_mode="Markdown")
    bot.answer_callback_query(call.id)


# ========== LOGS ==========

@bot.message_handler(func=lambda m: m.text == "📝 Logs" and is_admin(m.from_user.id))
def admin_logs_handler(message):
    logs = get_logs(limit=30)
    lines = [f"[{l['created_at'][:19]}] {l['event_type']}: {str(l['message'])[:80]}" for l in logs]
    text = "📝 *Recent Logs*\n\n" + "\n".join(lines)
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, text, reply_markup=kb, parse_mode="Markdown")


# ========== BACKUP ==========

@bot.message_handler(func=lambda m: m.text == "💾 Backup" and is_admin(m.from_user.id))
def admin_backup_handler(message):
    path = backup_database()
    try:
        with open(path, 'rb') as f:
            bot.send_document(message.chat.id, f, caption="💾 Database Backup")
    except:
        bot.send_message(message.chat.id, f"💾 Backup saved to:\n`{path}`", parse_mode="Markdown")
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔙 « Back", callback_data="admin_back"))
    bot.send_message(message.chat.id, "✅ Backup complete!", reply_markup=kb)

# ========== UNIFIED ADMIN STATE HANDLER ==========

@bot.message_handler(func=lambda m: is_admin(m.from_user.id) and get_state(m.from_user.id),
                     content_types=['text', 'photo', 'document'])
def admin_state_handler(message):
    state = get_state(message.from_user.id)
    uid = message.from_user.id

    # --- REJECT REASON ---
    if state.startswith("admin_reject_reason_"):
        order_id = state.replace("admin_reject_reason_", "")
        reason = message.text.strip() if message.text else ""
        success, msg = reject_order(order_id, reason)
        clear_state(uid)
        if success:
            order = get_order(order_id)
            try:
                bot.send_message(order['user_id'], f"❌ *Order Rejected*\n📋 ID: `{order_id}`\n📝 Reason: {reason}\nContact @{get_config('support_username', SUPPORT_USERNAME)}", parse_mode="Markdown")
            except: pass
            bot.send_message(message.chat.id, f"✅ Order `{order_id}` rejected.\nReason: {reason}", parse_mode="Markdown")
            add_log("order_rejected", uid, f"Order {order_id} rejected: {reason}")
        else:
            bot.send_message(message.chat.id, f"❌ Error: {msg}")

    # --- ADD PRODUCT: Image upload or name ---
    elif state == "admin_add_product_name":
        if message.photo:
            pid = user_data.get(uid, {}).get("product_id")
            if pid:
                fi = bot.get_file(message.photo[-1].file_id)
                dl = bot.download_file(fi.file_path)
                ext = fi.file_path.split(".")[-1] if "." in fi.file_path else "jpg"
                ip = os.path.join(PRODUCT_IMAGES_DIR, f"product_{pid}.{ext}")
                os.makedirs(os.path.dirname(ip), exist_ok=True)
                with open(ip, 'wb') as f: f.write(dl)
                update_product(pid, image_path=ip)
                clear_state(uid)
                bot.send_message(message.chat.id, f"✅ Image uploaded for product `{pid}`!")
        elif message.text:
            user_data[uid] = {"name": message.text.strip()}
            set_state(uid, "admin_add_product_desc")
            bot.send_message(message.chat.id, "📝 Send *product description*:")

    # --- ADD PRODUCT: description ---
    elif state == "admin_add_product_desc":
        user_data[uid]["description"] = message.text.strip()
        set_state(uid, "admin_add_product_category")
        categories = get_categories()
        kb = InlineKeyboardMarkup(row_width=1)
        for cat in categories:
            kb.add(InlineKeyboardButton(f"{cat['emoji']} {cat['name']}", callback_data=f"pick_cat_{cat['id']}"))
        bot.send_message(message.chat.id, "📂 Select *category*:", reply_markup=kb)

    # --- EDIT PRODUCT ---
    elif state == "admin_edit_product_field":
        val = message.text.strip().lower()
        pid = user_data.get(uid, {}).get("product_id")
        if not pid: clear_state(uid); bot.send_message(message.chat.id, "Session expired."); return
        if val == "toggle":
            p = get_product(pid)
            update_product(pid, is_active=0 if p['is_active'] else 1)
            bot.send_message(message.chat.id, f"Product {'enabled ✅' if not p['is_active'] else 'disabled 🔴'}.")
        elif val == "name":
            set_state(uid, "admin_edit_product_name")
            bot.send_message(message.chat.id, "Send new *name*:")
        elif val == "description":
            set_state(uid, "admin_edit_product_desc")
            bot.send_message(message.chat.id, "Send new *description*:")
        elif val == "pid":
            set_state(uid, "admin_edit_product_pid")
            p = get_product(pid)
            current_pid = p.get('product_pid', 0) if p else 0
            bot.send_message(message.chat.id, f"Send new *Reseller PID*\n(current: `{current_pid}`):", parse_mode="Markdown")
        else:
            bot.send_message(message.chat.id, "Send *name*, *description*, *pid*, or *toggle*.")

    elif state == "admin_edit_product_name":
        pid = user_data.get(uid, {}).get("product_id")
        if pid: update_product(pid, name=message.text.strip())
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Product name updated!")

    elif state == "admin_edit_product_desc":
        pid = user_data.get(uid, {}).get("product_id")
        if pid: update_product(pid, description=message.text.strip())
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Product description updated!")

    elif state == "admin_edit_product_pid":
        pid = user_data.get(uid, {}).get("product_id")
        if pid:
            try:
                new_pid = int(message.text.strip())
                with get_db() as conn:
                    conn.execute("UPDATE products SET product_pid=? WHERE id=?", (new_pid, pid))
                clear_state(uid)
                bot.send_message(message.chat.id, f"✅ Reseller PID updated to `{new_pid}`!", parse_mode="Markdown")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Invalid PID. Send a number.")

    # --- SET PRODUCT PID AFTER ADD ---
    elif state == "admin_set_product_pid":
        pid = user_data.get(uid, {}).get("product_id")
        val = message.text.strip().lower()
        if val == "skip" or val == "no":
            clear_state(uid)
            bot.send_message(message.chat.id, f"✅ Product `{pid}` saved (no PID).")
        else:
            try:
                new_pid = int(val)
                with get_db() as conn:
                    conn.execute("UPDATE products SET product_pid=? WHERE id=?", (new_pid, pid))
                clear_state(uid)
                bot.send_message(message.chat.id, f"✅ Product `{pid}` saved with Reseller PID: `{new_pid}`!")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Invalid. Send a number or `skip`.")

    # --- ADD PLAN ---
    elif state == "admin_add_plan_name":
        user_data[uid]["plan_name"] = message.text.strip()
        set_state(uid, "admin_add_plan_price")
        bot.send_message(message.chat.id, "💰 Send *price* (number only):")

    elif state == "admin_add_plan_price":
        try:
            price = float(message.text.strip())
            user_data[uid]["plan_price"] = price
            set_state(uid, "admin_add_plan_duration")
            bot.send_message(message.chat.id, "⏱ Send *duration* (e.g. '30 Days'):")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid price. Send a number.")

    elif state == "admin_add_plan_duration":
        ud = user_data.get(uid, {})
        add_plan(ud["product_id"], ud["plan_name"], ud["plan_price"], message.text.strip())
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Plan added!")

    # --- EDIT PLAN ---
    elif state == "admin_edit_plan_field":
        val = message.text.strip().lower()
        pid = user_data.get(uid, {}).get("plan_id")
        if not pid: clear_state(uid); return
        if val == "toggle":
            p = get_plan(pid)
            update_plan(pid, is_active=0 if p['is_active'] else 1)
            bot.send_message(message.chat.id, f"Plan {'enabled ✅' if not p['is_active'] else 'disabled 🔴'}.")
        elif val == "name":
            set_state(uid, "admin_edit_plan_name")
            bot.send_message(message.chat.id, "Send new *name*:")
        elif val == "price":
            set_state(uid, "admin_edit_plan_price")
            bot.send_message(message.chat.id, "Send new *price*:")
        elif val == "duration":
            set_state(uid, "admin_edit_plan_duration")
            bot.send_message(message.chat.id, "Send new *duration*:")
        else:
            bot.send_message(message.chat.id, "Send *name*, *price*, *duration*, or *toggle*.")

    elif state == "admin_edit_plan_name":
        pid = user_data.get(uid, {}).get("plan_id")
        if pid: update_plan(pid, name=message.text.strip())
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Plan name updated!")

    elif state == "admin_edit_plan_price":
        pid = user_data.get(uid, {}).get("plan_id")
        try:
            update_plan(pid, price=float(message.text.strip()))
            bot.send_message(message.chat.id, "✅ Plan price updated!")
        except: bot.send_message(message.chat.id, "❌ Invalid price.")
        clear_state(uid)

    elif state == "admin_edit_plan_duration":
        pid = user_data.get(uid, {}).get("plan_id")
        if pid: update_plan(pid, duration=message.text.strip())
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Plan duration updated!")

    # --- STOCK KEY MANAGER: Add Keys ---
    elif state.startswith("skm_add_keys_"):
        parts = state.split("_")
        pid, plid = int(parts[3]), int(parts[4])
        plan_filter = plid if plid > 0 else None
        price = user_data.get(uid, {}).get("price", 0) if plid > 0 else 0

        if message.document and message.document.file_name.endswith('.txt'):
            fi = bot.get_file(message.document.file_id)
            dl = bot.download_file(fi.file_path)
            content = dl.decode('utf-8', errors='ignore')
        elif message.text:
            content = message.text
        else:
            bot.send_message(message.chat.id, "❌ Please send text or a .txt file.")
            return

        added, skipped = import_stock_keys(pid, content, plan_filter, price)
        clear_state(uid)
        counts = get_stock_keys_count(product_id=pid, plan_id=plan_filter, price=(price if plid > 0 else None))
        bot.send_message(message.chat.id,
            f"✅ *Keys Imported!*\n\n"
            f"➕ Added: *{added}*\n"
            f"⏭ Skipped (duplicates): *{skipped}*\n\n"
            f"📊 Total now: *{counts['total']}* keys",
            parse_mode="Markdown")
        add_log("keys_added", uid, f"Added {added} keys to product {pid} plan {plid} price {price}")

    # --- STOCK KEY MANAGER: Delete One Key ---
    elif state.startswith("skm_del_key_"):
        parts = state.split("_")
        pid, plid = int(parts[3]), int(parts[4])
        price = user_data.get(uid, {}).get("price", 0) if plid > 0 else 0
        try:
            key_id = int(message.text.strip())
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid key ID. Send a number.")
            return

        # Verify key belongs to this product/plan/price
        plan_filter = plid if plid > 0 else None
        price_filter = price if plid > 0 else None
        keys = get_stock_keys(product_id=pid, plan_id=plan_filter, price=price_filter)
        key = next((k for k in keys if k['id'] == key_id), None)
        if not key:
            bot.send_message(message.chat.id, f"❌ Key ID `{key_id}` not found for this product/plan/price.", parse_mode="Markdown")
            clear_state(uid)
            return

        delete_stock_key(key_id)
        clear_state(uid)
        counts = get_stock_keys_count(product_id=pid, plan_id=plan_filter, price=price_filter)
        bot.send_message(message.chat.id,
            f"✅ Key `{key_id}` deleted!\n📊 Remaining: *{counts['total']}* keys",
            parse_mode="Markdown")
        add_log("key_deleted", uid, f"Deleted key {key_id} from product {pid} plan {plid}")

    # --- STOCK KEY MANAGER: Import from TXT ---
    elif state.startswith("skm_import_keys_"):
        parts = state.split("_")
        pid, plid = int(parts[3]), int(parts[4])
        plan_filter = plid if plid > 0 else None
        price = user_data.get(uid, {}).get("price", 0) if plid > 0 else 0

        if message.document and message.document.file_name.endswith('.txt'):
            fi = bot.get_file(message.document.file_id)
            dl = bot.download_file(fi.file_path)
            content = dl.decode('utf-8', errors='ignore')
        elif message.text:
            content = message.text
        else:
            bot.send_message(message.chat.id, "❌ Please send text or a .txt file.")
            return

        added, skipped = import_stock_keys(pid, content, plan_filter, price)
        clear_state(uid)
        counts = get_stock_keys_count(product_id=pid, plan_id=plan_filter, price=(price if plid > 0 else None))
        bot.send_message(message.chat.id,
            f"✅ *Keys Imported!*\n\n"
            f"➕ Added: *{added}*\n"
            f"⏭ Skipped (duplicates): *{skipped}*\n\n"
            f"📊 Total now: *{counts['total']}* keys",
            parse_mode="Markdown")
        add_log("keys_imported", uid, f"Imported {added} keys to product {pid} plan {plid} price {price}")

    # --- BROADCAST ---
    elif state == "admin_broadcast_text":
        text_to_send = message.text.strip()
        users = get_users(limit=10000)
        sent, failed = 0, 0
        for u in users:
            try:
                bot.send_message(u['user_id'], text_to_send, parse_mode="Markdown")
                sent += 1
            except: failed += 1
        clear_state(uid)
        bot.send_message(message.chat.id, f"📢 Broadcast complete!\n✅ Sent: {sent}\n❌ Failed: {failed}")

    # --- PAYMENT SETTINGS ---
    elif state.startswith("admin_payset_"):
        field = state.replace("admin_payset_", "")
        val = message.text.strip()
        if field == "upi_id":
            set_config("upi_id", val)
        elif field == "upi_name":
            set_config("upi_name", val)
        elif field == "phonepe":
            set_config("phonepe_number", val)
        elif field == "gpay":
            set_config("gpay_number", val)
        elif field == "paytm":
            set_config("paytm_number", val)
        elif field == "support":
            set_config("support_username", val)
        field_labels = {"upi_id": "UPI ID", "upi_name": "UPI Name", "phonepe": "PhonePe Number", "gpay": "GPay Number", "paytm": "Paytm Number", "support": "Support Username"}
        clear_state(uid)
        bot.send_message(message.chat.id, f"✅ {field_labels.get(field, field)} updated!")

    # --- BINANCE CONFIG ---
    elif state.startswith("admin_config_binance_"):
        field = state.replace("admin_config_binance_", "")
        val = message.text.strip()
        if field == "extra_charge":
            try:
                charge = float(val)
                set_binance_extra_charge(charge)
                clear_state(uid)
                bot.send_message(message.chat.id, f"✅ Binance extra charge updated to {format_amount(charge)}!")
            except ValueError:
                bot.send_message(message.chat.id, "❌ Invalid number.")
        elif field == "webhook_secret":
            set_config("binance_webhook_secret", val)
            clear_state(uid)
            bot.send_message(message.chat.id, "✅ Binance webhook secret updated!")
        else:
            set_config(f"binance_{field}", val)
            clear_state(uid)
            bot.send_message(message.chat.id, f"✅ Binance `{field}` updated!")

    # --- PAYMENT QR UPLOAD ---
    elif state.startswith("admin_upload_qr_"):
        method = state.replace("admin_upload_qr_", "")
        if message.photo:
            fi = bot.get_file(message.photo[-1].file_id)
            dl = bot.download_file(fi.file_path)
            ext = fi.file_path.split(".")[-1] if "." in fi.file_path else "png"
            path_map = {
                "upi": UPI_QR_PATH,
                "phonepe": PHONEPE_QR_PATH,
                "gpay": GPAY_QR_PATH,
                "paytm": PAYTM_QR_PATH,
            }
            save_path = path_map.get(method)
            if save_path:
                os.makedirs(os.path.dirname(save_path), exist_ok=True)
                with open(save_path, 'wb') as f:
                    f.write(dl)
                method_names = {"upi": "UPI", "phonepe": "PhonePe", "gpay": "Google Pay", "paytm": "Paytm"}
                clear_state(uid)
                bot.send_message(message.chat.id, f"✅ {method_names.get(method, method)} QR code updated!")
            else:
                clear_state(uid)
                bot.send_message(message.chat.id, "❌ Invalid payment method.")
        else:
            bot.send_message(message.chat.id, "❌ Please send a photo/image.")

    # --- SUPPORT & CHANNEL SETTINGS ---
    elif state.startswith("admin_sc_set_"):
        raw_field = state.replace("admin_sc_set_", "")
        val = message.text.strip()
        # Map button fields to their db keys
        field_map = {
            "support_username": "support_username",
            "support_link": "support_link",
            "support_btn": "support_button_text",
            "channel_username": "channel_username",
            "channel_link": "channel_link",
            "channel_btn": "channel_button_text",
            "reseller_username": "reseller_username",
            "reseller_link": "reseller_link",
            "reseller_btn": "reseller_button_text",
        }
        db_key = field_map.get(raw_field, raw_field)
        # Auto-strip @ from usernames
        if "username" in db_key and val.startswith("@"):
            val = val[1:]
        set_setting(db_key, val)
        clear_state(uid)
        label_map = {
            "support_username": "Support Username", "support_link": "Support Link", "support_button_text": "Support Button Text",
            "channel_username": "Channel Username", "channel_link": "Channel Link", "channel_button_text": "Channel Button Text",
            "reseller_username": "Reseller Username", "reseller_link": "Reseller Link", "reseller_button_text": "Reseller Button Text",
        }
        bot.send_message(message.chat.id, f"✅ {label_map.get(db_key, db_key)} updated!")

    # --- CATEGORY ---
    elif state == "admin_add_category_name":
        user_data[uid] = {"cat_name": message.text.strip()}
        set_state(uid, "admin_add_category_emoji")
        bot.send_message(message.chat.id, "Send the *emoji* for this category (e.g. 🎮):")

    elif state == "admin_add_category_emoji":
        ud = user_data.get(uid, {})
        result = add_category(ud.get("cat_name", ""), message.text.strip())
        clear_state(uid)
        if result:
            bot.send_message(message.chat.id, f"✅ Category added!")
        else:
            bot.send_message(message.chat.id, "❌ Category already exists or error.")

    # --- EDIT CATEGORY STATE HANDLERS ---
    elif state.startswith("admin_edit_category_name_"):
        cat_id = int(state.replace("admin_edit_category_name_", ""))
        with get_db() as conn:
            conn.execute("UPDATE categories SET name=? WHERE id=?", (message.text.strip(), cat_id))
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Category name updated!")

    elif state.startswith("admin_edit_category_emoji_"):
        cat_id = int(state.replace("admin_edit_category_emoji_", ""))
        with get_db() as conn:
            conn.execute("UPDATE categories SET emoji=? WHERE id=?", (message.text.strip(), cat_id))
        clear_state(uid)
        bot.send_message(message.chat.id, "✅ Category emoji updated!")

    # --- ADMIN ACCESS: Add Admin ---
    elif state == "admin_access_add_user_id":
        try:
            new_admin_id = int(message.text.strip())
            user_data[uid] = {"new_admin_id": new_admin_id}
            set_state(uid, "admin_access_add_username")
            bot.send_message(message.chat.id, "📛 Send *username* (without @) or send `skip`:", parse_mode="Markdown")
        except ValueError:
            bot.send_message(message.chat.id, "❌ Invalid User ID. Send a number.")

    elif state == "admin_access_add_username":
        username = message.text.strip()
        if username.lower() == "skip":
            username = ""
        user_data[uid]["new_admin_username"] = username
        set_state(uid, "admin_access_add_name")
        bot.send_message(message.chat.id, "👤 Send *first name* or send `skip`:", parse_mode="Markdown")

    elif state == "admin_access_add_name":
        first_name = message.text.strip()
        if first_name.lower() == "skip":
            first_name = ""
        ud = user_data.get(uid, {})
        user_data[uid]["new_admin_name"] = first_name
        set_state(uid, "admin_access_add_role")
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("⭐ Super Admin", callback_data=f"addadm_role_{ud['new_admin_id']}_super_admin"))
        kb.add(InlineKeyboardButton("👑 Admin", callback_data=f"addadm_role_{ud['new_admin_id']}_admin"))
        kb.add(InlineKeyboardButton("✏️ Editor", callback_data=f"addadm_role_{ud['new_admin_id']}_editor"))
        bot.send_message(message.chat.id, "⭐ Select *role* for this admin:", reply_markup=kb, parse_mode="Markdown")

    elif state == "admin_access_set_perm_":
        pass  # handled below
    elif state.startswith("admin_access_set_perm_"):
        aid = int(state.replace("admin_access_set_perm_", ""))
        perms = message.text.strip().lower()
        update_admin_role(aid, permissions=perms)
        clear_state(uid)
        bot.send_message(message.chat.id, f"✅ Permissions for admin `{aid}` updated to: `{perms}`!", parse_mode="Markdown")

