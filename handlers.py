import logging

from aiogram import Router, F, Bot
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from config import OPERATOR_CHAT_ID
from keyboards import (
    get_welcome_keyboard,
    get_back_keyboard,
    get_tiktok_keyboard,
    get_tiktok_admin_keyboard,
    get_cancel_ticket_keyboard,
)
from states import UserState
from texts import (
    WELCOME, OUTSIDE_WORK_HOURS, TIKTOK_PROMPT, TIKTOK_RECEIVED,
    TIKTOK_INVALID, OPERATOR_NOTIFIED, OPERATOR_CALLED,
    OPERATOR_CANCELLED, FAQ_NOT_UNDERSTOOD,
    FAQ, KEYWORDS_MAP, CLIENT_MESSAGE_PREFIX,
    TICKET_CANCELLED_ADMIN,
)
from utils import (
    is_work_hours, is_valid_tiktok_url, extract_url_from_text,
    extract_promo_from_url,
)
import storage

logger = logging.getLogger(__name__)
router = Router()


# ═══════════════════════════════════════════════════════════
#  🔑 УМНАЯ ОТПРАВКА: редактирует ОДНО сообщение
# ═══════════════════════════════════════════════════════════

async def smart_edit_or_send(
    bot: Bot,
    chat_id: int,
    message_id: int | None,
    text: str,
    reply_markup=None,
) -> tuple[int, int]:
    """
    Пытается отредактировать сообщение. Если нельзя — отправляет новое.
    Возвращает (chat_id, message_id) итогового сообщения.
    """
    if message_id:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return chat_id, message_id
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "message is not modified" in err:
                return chat_id, message_id

    msg = await bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    return msg.chat.id, msg.message_id


async def update_user_message(
    bot: Bot,
    user_id: int,
    text: str,
    reply_markup=None,
) -> tuple[int, int]:
    """Обновляет последнее сообщение бота у пользователя."""
    last_msg_id = storage.user_last_bot_message.get(user_id)
    chat_id, msg_id = await smart_edit_or_send(
        bot, user_id, last_msg_id, text, reply_markup
    )
    storage.user_last_bot_message[user_id] = msg_id
    return chat_id, msg_id


# 🆕 ИСПРАВЛЕНО: show_menu теперь принимает user_id явно
async def show_menu(bot: Bot, user_id: int, state: FSMContext):
    """Показывает/обновляет главное меню."""
    await state.set_state(UserState.idle)
    storage.active_tickets.pop(user_id, None)
    storage.operator_mode.pop(user_id, None)
    await update_user_message(bot, user_id, WELCOME, get_welcome_keyboard())


def _find_faq_answer(text: str) -> str | None:
    text_lower = text.lower()
    for keyword, faq_key in KEYWORDS_MAP.items():
        if keyword in text_lower:
            return FAQ.get(faq_key)
    return None


# ═══════════════════════════════════════════════════════════
#  /start и /menu
# ═══════════════════════════════════════════════════════════

@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not is_work_hours():
        await update_user_message(bot, message.from_user.id, OUTSIDE_WORK_HOURS)
        return
    # 🆕 ИСПРАВЛЕНО: передаём user_id
    await show_menu(bot, message.from_user.id, state)


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext, bot: Bot):
    await show_menu(bot, message.from_user.id, state)


# ═══════════════════════════════════════════════════════════
#  Callback-кнопки
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "action_tiktok")
async def cb_tiktok(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    if not is_work_hours():
        await update_user_message(
            bot, callback.from_user.id, OUTSIDE_WORK_HOURS, get_welcome_keyboard()
        )
        return
    await state.set_state(UserState.waiting_for_tiktok)
    await update_user_message(
        bot, callback.from_user.id, TIKTOK_PROMPT, get_tiktok_keyboard()
    )


@router.callback_query(F.data == "action_operator")
async def cb_operator(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    user = callback.from_user

    if not is_work_hours():
        await update_user_message(
            bot, user.id, OUTSIDE_WORK_HOURS, get_welcome_keyboard()
        )
        return

    await state.set_state(UserState.in_dialog)
    storage.active_tickets[user.id] = {
        "status": "open",
        "last_admin_msg_id": None,
    }
    storage.operator_mode[user.id] = True

    if OPERATOR_CHAT_ID:
        try:
            admin_msg = await bot.send_message(
                OPERATOR_CHAT_ID,
                f"🔔 <b>Клиент зовёт оператора!</b>\n\n"
                f"👤 {user.full_name}\n"
                f"🆔 ID: <code>{user.id}</code>\n"
                f"🔗 @{user.username or 'не указан'}\n\n"
                f"💬 <b>Чтобы ответить:</b> ответьте Reply на сообщение клиента.\n"
                f"🔒 <b>Чтобы закрыть:</b> нажмите кнопку ниже.",
                parse_mode="HTML",
            )
            storage.admin_notification_to_client[admin_msg.message_id] = user.id
            storage.active_tickets[user.id]["last_admin_msg_id"] = admin_msg.message_id

            from keyboards import get_ticket_close_keyboard
            await bot.edit_message_reply_markup(
                chat_id=OPERATOR_CHAT_ID,
                message_id=admin_msg.message_id,
                reply_markup=get_ticket_close_keyboard(user.id),
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить оператора: {e}")

    await update_user_message(
        bot, user.id, OPERATOR_CALLED, get_cancel_ticket_keyboard()
    )


# 🆕 ИСПРАВЛЕНО: теперь используем callback.from_user.id
@router.callback_query(F.data == "action_back")
async def cb_back(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer()
    # 🆕 ВАЖНО: используем from_user.id, а не message.from_user.id
    await show_menu(bot, callback.from_user.id, state)


# ═══════════════════════════════════════════════════════════
#  Кнопка "Отменить вызов" у клиента
# ═══════════════════════════════════════════════════════════

@router.callback_query(F.data == "ticket_cancel")
async def cb_ticket_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    await callback.answer("Вызов отменён")

    user = callback.from_user
    ticket = storage.active_tickets.pop(user.id, None)
    storage.operator_mode.pop(user.id, None)
    await state.set_state(UserState.idle)

    if OPERATOR_CHAT_ID and ticket:
        try:
            await bot.send_message(
                OPERATOR_CHAT_ID,
                TICKET_CANCELLED_ADMIN.format(
                    full_name=user.full_name,
                    user_id=user.id,
                ),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.warning(f"Не удалось уведомить админа: {e}")

    await update_user_message(
        bot, user.id, OPERATOR_CANCELLED, get_welcome_keyboard()
    )


# ═══════════════════════════════════════════════════════════
#  ПЕРЕСЫЛКА: клиент пишет → админу
# ═══════════════════════════════════════════════════════════

@router.message(StateFilter(UserState.in_dialog), F.text)
async def forward_client_message(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    ticket = storage.active_tickets.get(user_id)

    if not ticket or ticket["status"] != "open":
        return

    if not OPERATOR_CHAT_ID:
        return

    username = message.from_user.username or "не указан"
    full_name = message.from_user.full_name

    try:
        admin_msg = await bot.send_message(
            OPERATOR_CHAT_ID,
            CLIENT_MESSAGE_PREFIX.format(
                full_name=full_name,
                user_id=user_id,
                username=username,
            ) + message.text,
            parse_mode="HTML",
        )
        storage.admin_notification_to_client[admin_msg.message_id] = user_id

        from keyboards import get_ticket_close_keyboard
        await bot.edit_message_reply_markup(
            chat_id=OPERATOR_CHAT_ID,
            message_id=admin_msg.message_id,
            reply_markup=get_ticket_close_keyboard(user_id),
        )
    except Exception as e:
        logger.warning(f"Не удалось переслать сообщение админу: {e}")
        return

    await update_user_message(
        bot, user_id,
        "📤 <b>Сообщение передано оператору</b>\n\n"
        "⏳ Ожидайте ответа...",
        None,
    )


# ═══════════════════════════════════════════════════════════
#  Ожидание TikTok-ссылки
# ═══════════════════════════════════════════════════════════

@router.message(StateFilter(UserState.waiting_for_tiktok), F.text)
async def process_tiktok(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id

    if not is_work_hours():
        await state.set_state(UserState.idle)
        await update_user_message(bot, user_id, OUTSIDE_WORK_HOURS)
        return

    url = extract_url_from_text(message.text)

    if url and is_valid_tiktok_url(url):
        await state.set_state(UserState.idle)
        promo_code = extract_promo_from_url(url)
        username = message.from_user.username or "не указан"
        full_name = message.from_user.full_name

        try:
            await bot.delete_message(chat_id=user_id, message_id=message.message_id)
        except Exception:
            pass

        if OPERATOR_CHAT_ID:
            try:
                admin_msg = await bot.send_message(
                    OPERATOR_CHAT_ID,
                    f"🎬 <b>Новая TikTok-заявка</b>\n\n"
                    f"👤 {full_name}\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"🔗 @{username}\n\n"
                    f"📎 Ссылка: {url}\n"
                    f"🎟 Промокод: <code>{promo_code}</code>",
                    parse_mode="HTML",
                )
                storage.tiktok_submissions[admin_msg.message_id] = {
                    "user_id": user_id,
                    "url": url,
                    "promo_code": promo_code,
                    "username": full_name,
                }
                storage.admin_notification_to_client[admin_msg.message_id] = user_id

                await bot.edit_message_reply_markup(
                    chat_id=OPERATOR_CHAT_ID,
                    message_id=admin_msg.message_id,
                    reply_markup=get_tiktok_admin_keyboard(admin_msg.message_id),
                )
            except Exception as e:
                logger.warning(f"Ошибка уведомления админа: {e}")

        await update_user_message(
            bot, user_id, TIKTOK_RECEIVED, get_back_keyboard()
        )
    else:
        try:
            await bot.delete_message(chat_id=user_id, message_id=message.message_id)
        except Exception:
            pass
        await update_user_message(
            bot, user_id, TIKTOK_INVALID, get_tiktok_keyboard()
        )


# ═══════════════════════════════════════════════════════════
#  Обычные сообщения (FAQ)
# ═══════════════════════════════════════════════════════════

@router.message(F.text)
async def handle_text(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id

    if await state.get_state() is not None:
        return

    if user_id == OPERATOR_CHAT_ID:
        return

    if not is_work_hours():
        await update_user_message(bot, user_id, OUTSIDE_WORK_HOURS)
        return

    faq_answer = _find_faq_answer(message.text)
    text = faq_answer if faq_answer else FAQ_NOT_UNDERSTOOD

    try:
        await bot.delete_message(chat_id=user_id, message_id=message.message_id)
    except Exception:
        pass

    await update_user_message(bot, user_id, text, get_back_keyboard())