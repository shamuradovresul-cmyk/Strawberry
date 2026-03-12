"""
Уведомления — safe_send и тексты статусов для клиента.
"""

import asyncio
import logging
from telegram.error import Forbidden, RetryAfter

logger = logging.getLogger(__name__)

# Тексты которые получает клиент при смене статуса
STATUS_MESSAGES = {
    "accepted": (
        "✅ <b>Заказ #{id} принят!</b>\n\n"
        "Скоро свяжемся с вами для уточнения деталей 🍓"
    ),
    "confirmed": (
        "📋 <b>Заказ #{id} подтверждён!</b>\n\n"
        "Уже готовим вашу клубнику в шоколаде 🍫"
    ),
    "delivering": (
        "🚚 <b>Заказ #{id} в пути!</b>\n\n"
        "Курьер уже едет к вам 🍓"
    ),
    "done": (
        "🎉 <b>Заказ #{id} доставлен!</b>\n\n"
        "Спасибо за заказ! Будем рады видеть вас снова 🍓🍫"
    ),
    "cancelled": (
        "😔 <b>Заказ #{id} отменён.</b>\n\n"
        "Если есть вопросы — напишите нам."
    ),
}


async def safe_send(bot, chat_id: int, text: str, **kwargs) -> bool:
    try:
        await bot.send_message(chat_id=chat_id, text=text, **kwargs)
        return True
    except Forbidden:
        logger.warning(f"Пользователь {chat_id} заблокировал бота.")
        return False
    except RetryAfter as e:
        logger.warning(f"RetryAfter: ждём {e.retry_after} сек.")
        await asyncio.sleep(e.retry_after)
        return await safe_send(bot, chat_id, text, **kwargs)
    except Exception as e:
        logger.error(f"Ошибка отправки {chat_id}: {e}")
        return False


async def notify_client_status(bot, client_id: int, order_id: int, status: str):
    """Отправляет клиенту уведомление о смене статуса заказа."""
    template = STATUS_MESSAGES.get(status)
    if not template:
        return
    text = template.format(id=order_id)
    await safe_send(bot, client_id, text, parse_mode="HTML")
