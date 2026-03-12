"""
Хендлеры администратора — управление заказами, архив, статистика, клиенты.
"""

import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import db
from utils.notifications import notify_client_status, safe_send

logger = logging.getLogger(__name__)

STATUS_LABELS = {
    "new":        "🆕 Новый",
    "accepted":   "✅ Принят",
    "confirmed":  "📋 Подтверждён",
    "delivering": "🚚 В пути",
    "done":       "🎉 Выполнен",
    "cancelled":  "❌ Отменён",
}

STATUS_FLOW = {
    # текущий статус → [(кнопка, новый_статус)]
    "new":        [("✅ Принять",          "accepted"),
                   ("❌ Отклонить",        "cancelled")],
    "accepted":   [("📋 Подтвердить заказ","confirmed"),
                   ("❌ Отменить",         "cancelled")],
    "confirmed":  [("🚚 Отправить",        "delivering"),
                   ("❌ Отменить",         "cancelled")],
    "delivering": [("✅ Доставлен",        "done"),
                   ("❌ Отменить",         "cancelled")],
}


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([
        [KeyboardButton("📦 Новые заказы"),   KeyboardButton("📋 Все активные")],
        [KeyboardButton("📊 Статистика"),     KeyboardButton("🗂 Архив")],
        [KeyboardButton("👥 Команда"),        KeyboardButton("🔍 Поиск заказа")],
    ], resize_keyboard=True)


def order_keyboard(order_id: int, client_id: int, status: str) -> InlineKeyboardMarkup:
    """Кнопки управления заказом — зависят от текущего статуса."""
    buttons = []
    actions = STATUS_FLOW.get(status, [])
    if actions:
        row = [
            InlineKeyboardButton(label, callback_data=f"order:{new_status}:{order_id}:{client_id}")
            for label, new_status in actions
        ]
        buttons.append(row)
    buttons.append([
        InlineKeyboardButton("💬 Написать клиенту", callback_data=f"msg_client:{client_id}"),
        InlineKeyboardButton("👤 Профиль",           callback_data=f"client:profile:{client_id}"),
    ])
    return InlineKeyboardMarkup(buttons)


def format_order(order, show_client: bool = True) -> str:
    status = STATUS_LABELS.get(order["status"], order["status"])
    lines = [f"<b>Заказ #{order['id']}</b> — {status}\n"]
    if show_client:
        lines.append(f"👤 {order.get('client_name', '—')}")
        if order.get("client_phone"):
            lines.append(f"📞 {order['client_phone']}")
    lines += [
        f"\n🍓 {order['item_desc']}",
        f"🔢 {order['quantity']} шт.",
        f"✨ {order['wishes']}",
        f"📍 {order['address']}",
        f"🕐 {order['delivery_time']}",
        f"💳 {order['payment_method']}",
        f"\n📅 {order['created_at'][:16]}",
    ]
    return "\n".join(lines)


# ─── /admin — главное меню ────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    await update.message.reply_text(
        "👔 <b>Панель администратора</b>\n\nВыбери раздел:",
        parse_mode="HTML",
        reply_markup=admin_keyboard(),
    )


# ─── Новые заказы ─────────────────────────────────────────────────────────────

async def show_new_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    orders = db.get_orders_by_status("new")
    if not orders:
        await update.message.reply_text("✅ Новых заказов нет!")
        return
    await update.message.reply_text(f"🆕 <b>Новых заказов: {len(orders)}</b>", parse_mode="HTML")
    for order in orders:
        await update.message.reply_text(
            format_order(order),
            parse_mode="HTML",
            reply_markup=order_keyboard(order["id"], order["client_id"], order["status"]),
        )


# ─── Все активные ─────────────────────────────────────────────────────────────

async def show_active_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    active = []
    for status in ("new", "accepted", "confirmed", "delivering"):
        active.extend(db.get_orders_by_status(status))

    if not active:
        await update.message.reply_text("✅ Активных заказов нет!")
        return

    await update.message.reply_text(
        f"📋 <b>Активных заказов: {len(active)}</b>", parse_mode="HTML"
    )
    for order in active:
        await update.message.reply_text(
            format_order(order),
            parse_mode="HTML",
            reply_markup=order_keyboard(order["id"], order["client_id"], order["status"]),
        )


# ─── Статистика ───────────────────────────────────────────────────────────────

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    stats = db.get_orders_stats()
    by_status = "\n".join(
        f"  {STATUS_LABELS.get(s, s)}: {c}"
        for s, c in stats["by_status"].items()
    )
    await update.message.reply_text(
        f"📊 <b>Статистика</b>\n\n"
        f"📅 Сегодня: <b>{stats['today']}</b>\n"
        f"📆 За 7 дней: <b>{stats['week']}</b>\n\n"
        f"По статусам:\n{by_status}",
        parse_mode="HTML",
    )


# ─── Архив ────────────────────────────────────────────────────────────────────

async def show_archive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    orders = db.get_orders_today()
    if not orders:
        await update.message.reply_text("За сегодня заказов нет.")
        return
    await update.message.reply_text(
        f"🗂 <b>Заказы за сегодня: {len(orders)}</b>", parse_mode="HTML"
    )
    for order in orders[:10]:  # максимум 10 чтобы не спамить
        await update.message.reply_text(format_order(order), parse_mode="HTML")


# ─── Поиск ────────────────────────────────────────────────────────────────────

async def search_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    context.user_data["awaiting_search"] = True
    await update.message.reply_text("🔍 Введи имя клиента или телефон:")


# ─── Команда /addadmin ────────────────────────────────────────────────────────

async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_owner(chat_id):
        return
    code = db.create_invite_code(chat_id)
    await update.message.reply_text(
        f"🔑 Одноразовый код для нового администратора:\n\n"
        f"<code>{code}</code>\n\n"
        f"Передай этот код сотруднику. Он введёт его командой:\n"
        f"<code>/join {code}</code>",
        parse_mode="HTML",
    )


async def cmd_removeadmin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_owner(chat_id):
        return
    if not context.args:
        admins = db.get_all_admins()
        lines = ["👥 <b>Список администраторов:</b>\n"]
        for a in admins:
            role = "👑 Владелец" if a["role"] == "owner" else "👔 Админ"
            lines.append(f"{role} — {a['name']} (ID: <code>{a['id']}</code>)")
        lines.append("\nДля удаления: <code>/removeadmin ID</code>")
        await update.message.reply_text("\n".join(lines), parse_mode="HTML")
        return
    try:
        target_id = int(context.args[0])
        db.remove_admin(target_id)
        await update.message.reply_text(f"✅ Администратор {target_id} удалён.")
    except ValueError:
        await update.message.reply_text("❌ Укажи числовой ID")


async def cmd_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Новый сотрудник вводит /join КОД чтобы стать администратором."""
    chat_id = update.effective_chat.id
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("Укажи код: <code>/join КОД</code>", parse_mode="HTML")
        return
    code = context.args[0].upper()
    if db.use_invite_code(code, chat_id):
        db.add_admin(chat_id, user.full_name, role="admin")
        await update.message.reply_text(
            "✅ Ты теперь администратор! Используй /admin",
        )
        logger.info(f"Новый админ: {user.full_name} ({chat_id})")
    else:
        await update.message.reply_text("❌ Неверный или уже использованный код.")


# ─── Команда /team ────────────────────────────────────────────────────────────

async def cmd_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return
    admins = db.get_all_admins()
    lines = ["👥 <b>Команда:</b>\n"]
    for a in admins:
        role = "👑 Владелец" if a["role"] == "owner" else "👔 Админ"
        lines.append(f"{role} — {a['name']}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


# ─── Callback-обработчик заказов ──────────────────────────────────────────────

async def order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    chat_id = query.message.chat_id
    await query.answer()

    if not db.is_admin(chat_id):
        return

    data = query.data

    # order:<new_status>:<order_id>:<client_id>
    if data.startswith("order:"):
        parts = data.split(":")
        new_status = parts[1]
        order_id   = int(parts[2])
        client_id  = int(parts[3])

        db.update_order_status(order_id, new_status)
        await notify_client_status(context.bot, client_id, order_id, new_status)

        order = db.get_order(order_id)
        status_label = STATUS_LABELS.get(new_status, new_status)

        # Обновляем кнопки если ещё есть следующие шаги
        new_kb = order_keyboard(order_id, client_id, new_status)
        await query.edit_message_reply_markup(reply_markup=new_kb)
        await query.message.reply_text(
            f"✅ Заказ #{order_id} → {status_label}"
        )

    # client:profile:<client_id>
    elif data.startswith("client:profile:"):
        client_id = int(data.split(":")[2])
        client = db.get_client(client_id)
        if not client:
            await query.message.reply_text("Клиент не найден.")
            return

        orders_count = db.get_client_orders_count(client_id)
        bl = "⛔ В чёрном списке" if client["blacklisted"] else "✅ Активен"
        username = f"@{client['username']}" if client["username"] else "нет"

        text = (
            f"👤 <b>Профиль клиента</b>\n\n"
            f"Имя: {client['name']}\n"
            f"Username: {username}\n"
            f"Телефон: {client['phone'] or '—'}\n"
            f"Заказов: {orders_count}\n"
            f"Статус: {bl}\n"
            f"С нами с: {client['first_seen'][:10]}\n"
        )

        bl_btn = (
            InlineKeyboardButton("✅ Убрать из ЧС", callback_data=f"client:unban:{client_id}")
            if client["blacklisted"]
            else InlineKeyboardButton("⛔ В чёрный список", callback_data=f"client:ban:{client_id}")
        )
        kb = InlineKeyboardMarkup([[bl_btn]])
        await query.message.reply_text(text, parse_mode="HTML", reply_markup=kb)

    elif data.startswith("client:ban:"):
        client_id = int(data.split(":")[2])
        db.add_to_blacklist(client_id, reason="Заблокирован администратором")
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Убрать из ЧС", callback_data=f"client:unban:{client_id}")
            ]])
        )
        await query.message.reply_text(f"⛔ Клиент {client_id} добавлен в чёрный список.")

    elif data.startswith("client:unban:"):
        client_id = int(data.split(":")[2])
        db.remove_from_blacklist(client_id)
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⛔ В чёрный список", callback_data=f"client:ban:{client_id}")
            ]])
        )
        await query.message.reply_text(f"✅ Клиент {client_id} удалён из чёрного списка.")

    # msg_client:<client_id> — написать клиенту
    elif data.startswith("msg_client:"):
        client_id = int(data.split(":")[1])
        context.user_data["messaging_client"] = client_id
        await query.message.reply_text(
            f"💬 Напиши сообщение для клиента {client_id}:\n(следующее сообщение уйдёт ему)"
        )


async def handle_admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if not db.is_admin(chat_id):
        return False

    text = update.message.text

    # Пересылка сообщения клиенту
    if context.user_data.get("messaging_client"):
        client_id = context.user_data.pop("messaging_client")
        await safe_send(
            context.bot, client_id,
            f"💬 <b>Сообщение от магазина:</b>\n\n{text}",
            parse_mode="HTML",
        )
        await update.message.reply_text(f"✅ Сообщение отправлено клиенту {client_id}.")
        return True

    # Поиск заказа
    if context.user_data.get("awaiting_search"):
        context.user_data.pop("awaiting_search")
        results = db.search_orders(text)
        if not results:
            await update.message.reply_text(f"❌ Ничего не найдено по запросу «{text}»")
        else:
            await update.message.reply_text(f"🔍 Найдено: {len(results)}")
            for order in results[:5]:
                await update.message.reply_text(
                    format_order(order),
                    parse_mode="HTML",
                    reply_markup=order_keyboard(order["id"], order["client_id"], order["status"]),
                )
        return True

    # Кнопки меню
    menu_actions = {
        "📦 Новые заказы":  show_new_orders,
        "📋 Все активные":  show_active_orders,
        "📊 Статистика":    show_stats,
        "🗂 Архив":         show_archive,
        "👥 Команда":       cmd_team,
        "🔍 Поиск заказа":  search_prompt,
    }
    if text in menu_actions:
        await menu_actions[text](update, context)
        return True

    return False


def get_admin_handlers() -> list:
    return [
        CommandHandler("admin",        cmd_admin),
        CommandHandler("addadmin",     cmd_addadmin),
        CommandHandler("removeadmin",  cmd_removeadmin),
        CommandHandler("join",         cmd_join),
        CommandHandler("team",         cmd_team),
        CallbackQueryHandler(order_callback),
    ]