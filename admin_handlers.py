"""
Хендлеры для админа:
- Одобрение/отклонение TikTok-заявок
- Ответы клиентам в режиме оператора (через Reply)
- Закрытие/возобновление тикетов
"""
import logging

from aiogram import Router, F, Bot
from aiogram.filters import Filter
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext

from config import OPERATOR_CHAT_ID, SUPPORT_USERNAME
from keyboards import (
    get_welcome_keyboard,
    get_ticket_closed_keyboard,
    get_dialog_reply_keyboard,
    get_ticket_close_keyboard,
)
from states import UserState
from texts import (
    TIKTOK_APPROVED, TIKTOK_REJECTED,
    OPERATOR_REPLY_PREFIX, TICKET_CLOSED,
    TICKET_RESUMED_CLIENT, TICKET_RESUMED_ADMIN,
)
from handlers import update_user_message
import storage

logger = logging.getLogger(__name__)
router = router = Router()


# ═══════════════════════════════════════════════════════════
#  🔐 Фильтр: только админ
# ═══════════════════════════════════════════════════════════

class IsAdmin(Filter):
    async def __call__(self, event) -> bool:
        user_id = getattr(event, "from_user", None)
        if user_id is None:
            return False
        return user_id.id == OPERATOR_CHAT_ID


# ═══════════════════════════════════════════════════════════
#  ✅ Одобрение TikTok-заявки
# ═══════════════════════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("tiktok_approve:"))
async def admin_approve_tiktok(callback: CallbackQuery, bot: Bot):
    await callback.answer("✅ Заявка одобрена!")

    notification_id = int(callback.data.split(":")[1])
    submission = storage.tiktok_submissions.pop(notification_id, None)
    storage.admin_notification_to_client.pop(notification_id, None)

    if not submission:
        await callback.message.edit_text(
            callback.message.text + "\n\n⚠️ Заявка уже обработана.",
            parse_mode="HTML",
        )
        return

    user_id = submission["user_id"]
    promo_code = submission["promo_code"]

    # Обновляем сообщение админа
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n✅ <b>ОДОБРЕНО</b> — промокод отправлен клиенту.",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass

    # Отправляем НОВОЕ сообщение клиенту
    try:
        text = TIKTOK_APPROVED.format(promo_code=promo_code)
        msg = await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 Главное меню",
                                         callback_data="action_back"),
                    InlineKeyboardButton(text="👨‍💻 Ещё вопрос",
                                         callback_data="action_operator"),
                ]
            ]),
        )
        storage.user_last_bot_message[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Не удалось отправить промокод клиенту {user_id}: {e}")
        await callback.message.answer(f"❌ Ошибка: {e}")


# ═══════════════════════════════════════════════════════════
#  ❌ Отклонение TikTok-заявки
# ═══════════════════════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("tiktok_reject:"))
async def admin_reject_tiktok(callback: CallbackQuery, bot: Bot):
    await callback.answer("❌ Заявка отклонена")

    notification_id = int(callback.data.split(":")[1])
    submission = storage.tiktok_submissions.pop(notification_id, None)
    storage.admin_notification_to_client.pop(notification_id, None)

    if not submission:
        await callback.message.edit_text(
            callback.message.text + "\n\n⚠️ Заявка уже обработана.",
            parse_mode="HTML",
        )
        return

    user_id = submission["user_id"]

    # Обновляем сообщение админа
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n❌ <b>ОТКЛОНЕНО</b> — клиент уведомлён.",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass

    # Отправляем НОВОЕ сообщение клиенту
    try:
        text = TIKTOK_REJECTED.format(support_username=SUPPORT_USERNAME)
        msg = await bot.send_message(
            chat_id=user_id,
            text=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📋 Главное меню",
                                         callback_data="action_back"),
                    InlineKeyboardButton(text="👨‍💻 Ещё вопрос",
                                         callback_data="action_operator"),
                ]
            ]),
        )
        storage.user_last_bot_message[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Не удалось отправить отказ клиенту {user_id}: {e}")


# ═══════════════════════════════════════════════════════════
#  💬 Ответ клиенту через Reply
# ═══════════════════════════════════════════════════════════

@router.message(IsAdmin(), F.reply_to_message)
async def admin_reply_to_client(message: Message, bot: Bot):
    """
    Админ отвечает Reply на сообщение клиента —
    бот пересылает ответ клиенту.
    """
    replied = message.reply_to_message
    replied_msg_id = replied.message_id

    # Ищем клиента по маппингу
    client_id = storage.admin_notification_to_client.get(replied_msg_id)

    if not client_id:
        await message.reply(
            "❌ Не удалось определить ID клиента.\n"
            "Отвечайте только на уведомления от бота."
        )
        return

    # Отправляем ответ клиенту
    try:
        reply_text = OPERATOR_REPLY_PREFIX + (message.text or "(сообщение без текста)")

        msg = await bot.send_message(
            chat_id=client_id,
            text=reply_text,
            parse_mode="HTML",
            reply_markup=get_dialog_reply_keyboard(),
        )
        storage.user_last_bot_message[client_id] = msg.message_id
        await message.reply(f"✅ Ответ доставлен клиенту (ID: {client_id})")

    except Exception as e:
        await message.reply(f"❌ Ошибка отправки: {e}")


# ═══════════════════════════════════════════════════════════
#  🔒 Закрытие тикета (админ)
# ═══════════════════════════════════════════════════════════

@router.callback_query(IsAdmin(), F.data.startswith("ticket_close:"))
async def admin_close_ticket(callback: CallbackQuery, bot: Bot):
    user_id = int(callback.data.split(":")[1])
    await callback.answer("🔒 Тикет закрыт")

    ticket = storage.active_tickets.get(user_id)
    if not ticket:
        await callback.message.edit_text(
            callback.message.text + "\n\n⚠️ Тикет уже закрыт.",
            parse_mode="HTML",
        )
        return

    # Закрываем тикет
    ticket["status"] = "closed"

    # Обновляем сообщение админа
    try:
        await callback.message.edit_text(
            callback.message.text + "\n\n🔒 <b>Диалог закрыт</b>",
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        pass

    # Отправляем клиенту уведомление о закрытии
    try:
        msg = await bot.send_message(
            chat_id=user_id,
            text=TICKET_CLOSED,
            parse_mode="HTML",
            reply_markup=get_ticket_closed_keyboard(user_id),
        )
        storage.user_last_bot_message[user_id] = msg.message_id
    except Exception as e:
        logger.error(f"Не удалось уведомить клиента о закрытии: {e}")


# ═══════════════════════════════════════════════════════════
#  🔄 Возобновление тикета (клиент нажал "Вопрос не был решён")
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data.startswith("ticket_resume:"))
async def client_resume_ticket(callback: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = int(callback.data.split(":")[1])

    # Проверка: только владелец тикета может его возобновить
    if callback.from_user.id != user_id:
        await callback.answer("❌ Это не ваш тикет", show_alert=True)
        return

    await callback.answer("🔄 Диалог возобновлён")

    ticket = storage.active_tickets.get(user_id)
    if not ticket:
        # Создаём новый тикет
        storage.active_tickets[user_id] = {
            "status": "open",
            "last_admin_msg_id": None,
        }
    else:
        ticket["status"] = "open"

    # Переводим клиента в состояние диалога
    await state.set_state(UserState.in_dialog)
    storage.operator_mode[user_id] = True

    # Уведомляем админа
    if OPERATOR_CHAT_ID:
        try:
            user = callback.from_user
            admin_msg = await bot.send_message(
                OPERATOR_CHAT_ID,
                TICKET_RESUMED_ADMIN.format(
                    full_name=user.full_name,
                    user_id=user.id,
                    username=user.username or "не указан",
                ),
                parse_mode="HTML",
            )
            storage.admin_notification_to_client[admin_msg.message_id] = user.id
            storage.active_tickets[user_id]["last_admin_msg_id"] = admin_msg.message_id

            # Добавляем кнопку "Закрыть вопрос"
            await bot.edit_message_reply_markup(
                chat_id=OPERATOR_CHAT_ID,
                message_id=admin_msg.message_id,
                reply_markup=get_ticket_close_keyboard(user_id),
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа: {e}")

    # Обновляем сообщение клиента
    await update_user_message(
        bot,
        user_id,
        TICKET_RESUMED_CLIENT,
        InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить вызов",
                                  callback_data="ticket_cancel")],
        ]),
    )