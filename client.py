"""
Хендлеры для клиентов — оформление заказа по шагам (FSM).
"""

import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters,
)
import db
from utils.notifications import safe_send

logger = logging.getLogger(__name__)

ADMIN_IDS_ENV = int(os.getenv("OWNER_ID", "0"))

# Шаги диалога
ITEM, QUANTITY, WISHES, ADDRESS, DELIVERY_TIME, PAYMENT, PHONE, CONFIRM = range(8)

PAYMENT_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("💵 Наличными при получении"),
      KeyboardButton("📱 Переводом на телефон")]],
    resize_keyboard=True, one_time_keyboard=True,
)

CONFIRM_KB = ReplyKeyboardMarkup(
    [[KeyboardButton("✅ Подтвердить"), KeyboardButton("❌ Отменить")]],
    resize_keyboard=True, one_time_keyboard=True,
)


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("📦 Новый заказ")],
         [KeyboardButton("📋 Мои заказы")]],
        resize_keyboard=True,
    )


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user = update.effective_user

    # Если это админ — не трогаем
    if db.is_admin(chat_id):
        await update.message.reply_text(
            "👔 Ты в режиме администратора. Используй /admin"
        )
        return ConversationHandler.END

    # Обновляем данные клиента
    db.upsert_client(chat_id, user.full_name, user.username)

    # Проверяем чёрный список
    if db.is_blacklisted(chat_id):
        await update.message.reply_text(
            "😔 К сожалению, мы не можем принять ваш заказ.\n"
            "Если считаете что произошла ошибка — напишите нам."
        )
        return ConversationHandler.END

    orders_count = db.get_client_orders_count(chat_id)
    greeting = "С возвращением" if orders_count > 0 else "Добро пожаловать"
    orders_text = f"\n\nУ вас уже <b>{orders_count}</b> заказов 🍓" if orders_count > 0 else ""

    await update.message.reply_text(
        f"🍓 <b>{greeting}!</b>{orders_text}\n\n"
        f"Мы делаем клубнику в шоколаде с любовью 🍫\n\n"
        f"Что хочешь сделать?",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )
    return ConversationHandler.END


async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    if db.is_blacklisted(chat_id):
        await update.message.reply_text("😔 К сожалению, мы не можем принять ваш заказ.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📝 <b>Оформление заказа</b>\n\n"
        "Что хочешь заказать?\n\n"
        "Можешь написать текстом или прислать ссылку/скриншот из Instagram 👇",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ITEM


async def got_item(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Принимаем текст или фото
    if update.message.photo:
        context.user_data["item_desc"] = "📸 Скриншот из Instagram"
        context.user_data["item_photo"] = update.message.photo[-1].file_id
    elif update.message.text:
        context.user_data["item_desc"] = update.message.text
    else:
        await update.message.reply_text("Пожалуйста, отправь текст или фото 👇")
        return ITEM

    await update.message.reply_text("🔢 Сколько штук хочешь?")
    return QUANTITY


async def got_quantity(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["quantity"] = update.message.text
    await update.message.reply_text(
        "✨ Есть пожелания?\n\n"
        "Например: орехи, посыпка, особая упаковка, без горького шоколада...\n\n"
        "Или напиши <b>нет</b> если всё стандартно",
        parse_mode="HTML",
    )
    return WISHES


async def got_wishes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["wishes"] = update.message.text
    await update.message.reply_text("📍 Напиши адрес доставки:")
    return ADDRESS


async def got_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["address"] = update.message.text
    await update.message.reply_text(
        "🕐 Удобное время доставки?\n\n"
        "Например: сегодня после 18:00, завтра с 12 до 15"
    )
    return DELIVERY_TIME


async def got_delivery_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["delivery_time"] = update.message.text
    await update.message.reply_text(
        "💳 Как будешь оплачивать?",
        reply_markup=PAYMENT_KB,
    )
    return PAYMENT


async def got_payment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["payment"] = update.message.text
    client = db.get_client(update.effective_chat.id)

    # Если телефон уже есть — пропускаем шаг
    if client and client["phone"]:
        context.user_data["phone"] = client["phone"]
        return await show_confirm(update, context)

    await update.message.reply_text(
        "📞 Укажи номер телефона для связи:",
        reply_markup=ReplyKeyboardRemove(),
    )
    return PHONE


async def got_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["phone"] = update.message.text
    db.set_client_phone(update.effective_chat.id, update.message.text)
    return await show_confirm(update, context)


async def show_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = context.user_data
    text = (
        "📋 <b>Проверь заказ:</b>\n\n"
        f"🍓 Что: {d.get('item_desc', '—')}\n"
        f"🔢 Количество: {d.get('quantity', '—')}\n"
        f"✨ Пожелания: {d.get('wishes', '—')}\n"
        f"📍 Адрес: {d.get('address', '—')}\n"
        f"🕐 Время: {d.get('delivery_time', '—')}\n"
        f"💳 Оплата: {d.get('payment', '—')}\n"
        f"📞 Телефон: {d.get('phone', '—')}\n"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=CONFIRM_KB)
    return CONFIRM


async def got_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text

    if text == "❌ Отменить":
        context.user_data.clear()
        await update.message.reply_text(
            "Заказ отменён. Возвращайся когда будешь готов! 🍓",
            reply_markup=main_keyboard(),
        )
        return ConversationHandler.END

    if text != "✅ Подтвердить":
        await update.message.reply_text("Нажми одну из кнопок 👇", reply_markup=CONFIRM_KB)
        return CONFIRM

    d = context.user_data
    order_id = db.create_order(
        client_id=chat_id,
        item_desc=d.get("item_desc", "—"),
        quantity=d.get("quantity", "—"),
        wishes=d.get("wishes", "—"),
        address=d.get("address", "—"),
        delivery_time=d.get("delivery_time", "—"),
        payment_method=d.get("payment", "—"),
    )

    await update.message.reply_text(
        f"✅ <b>Заказ #{order_id} оформлен!</b>\n\n"
        f"Скоро свяжемся с вами 🍓",
        parse_mode="HTML",
        reply_markup=main_keyboard(),
    )

    # Уведомляем всех админов
    await notify_admins_new_order(context.bot, order_id, chat_id, d)
    context.user_data.clear()
    return ConversationHandler.END


async def notify_admins_new_order(bot, order_id: int, client_id: int, d: dict):
    """Отправляет уведомление о новом заказе всем админам."""
    from telegram import InlineKeyboardMarkup, InlineKeyboardButton

    client = db.get_client(client_id)
    orders_count = db.get_client_orders_count(client_id)

    repeat_text = f"⚠️ Заказывает <b>{orders_count}</b> раз\n" if orders_count > 1 else "🆕 Новый клиент\n"

    username_text = f"@{client['username']}" if client and client["username"] else "нет"

    text = (
        f"🆕 <b>Новый заказ #{order_id}</b>\n\n"
        f"👤 {client['name'] if client else '—'} ({username_text})\n"
        f"{repeat_text}"
        f"📞 {d.get('phone', '—')}\n\n"
        f"🍓 Что: {d.get('item_desc', '—')}\n"
        f"🔢 Количество: {d.get('quantity', '—')}\n"
        f"✨ Пожелания: {d.get('wishes', '—')}\n"
        f"📍 Адрес: {d.get('address', '—')}\n"
        f"🕐 Время: {d.get('delivery_time', '—')}\n"
        f"💳 Оплата: {d.get('payment', '—')}\n"
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Принять",    callback_data=f"order:accept:{order_id}:{client_id}"),
            InlineKeyboardButton("❌ Отклонить",  callback_data=f"order:cancel:{order_id}:{client_id}"),
        ],
        [InlineKeyboardButton("👤 Профиль клиента", callback_data=f"client:profile:{client_id}")],
    ])

    for admin in db.get_all_admins():
        await safe_send(bot, admin["id"], text, parse_mode="HTML", reply_markup=keyboard)


async def my_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    with db.get_conn() as conn:
        orders = conn.execute("""
            SELECT * FROM orders WHERE client_id = ?
            ORDER BY created_at DESC LIMIT 10
        """, (chat_id,)).fetchall()

    if not orders:
        await update.message.reply_text("У тебя пока нет заказов 🍓")
        return

    STATUS_LABELS = {
        "new": "🆕 Новый",
        "accepted": "✅ Принят",
        "confirmed": "📋 Подтверждён",
        "delivering": "🚚 В пути",
        "done": "🎉 Выполнен",
        "cancelled": "❌ Отменён",
    }

    lines = ["📦 <b>Твои заказы:</b>\n"]
    for o in orders:
        status = STATUS_LABELS.get(o["status"], o["status"])
        lines.append(
            f"<b>Заказ #{o['id']}</b> — {status}\n"
            f"  {o['item_desc'][:50]}, {o['quantity']} шт.\n"
            f"  📅 {o['created_at'][:10]}\n"
        )

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


def get_client_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.Regex("^📦 Новый заказ$"), start_order),
            MessageHandler(filters.Regex("^📋 Мои заказы$"), my_orders),
        ],
        states={
            ITEM:          [MessageHandler(filters.TEXT | filters.PHOTO, got_item)],
            QUANTITY:      [MessageHandler(filters.TEXT, got_quantity)],
            WISHES:        [MessageHandler(filters.TEXT, got_wishes)],
            ADDRESS:       [MessageHandler(filters.TEXT, got_address)],
            DELIVERY_TIME: [MessageHandler(filters.TEXT, got_delivery_time)],
            PAYMENT:       [MessageHandler(filters.TEXT, got_payment)],
            PHONE:         [MessageHandler(filters.TEXT, got_phone)],
            CONFIRM:       [MessageHandler(filters.TEXT, got_confirm)],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
    )
