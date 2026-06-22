from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_welcome_keyboard() -> InlineKeyboardMarkup:
    """Главное меню."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=" Отправить ссылку на TikTok", icon_custom_emoji_id="5940686918583849152", style="primary",
            callback_data="action_tiktok")],
        [InlineKeyboardButton(
            text="Связаться с оператором", icon_custom_emoji_id="5307746710682869587",
            callback_data="action_operator")],
    ])


def get_back_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Назад в меню»."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Назад в меню", icon_custom_emoji_id="5807737309742763644", style="primary",
            callback_data="action_back")],
    ])


def get_tiktok_keyboard() -> InlineKeyboardMarkup:
    """На экране ожидания TikTok-ссылки."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Назад в меню", icon_custom_emoji_id="5807737309742763644", style="primary",
            callback_data="action_back")],
    ])


def get_tiktok_admin_keyboard(notification_id: int) -> InlineKeyboardMarkup:
    """Кнопки для админа при TikTok-заявке."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Одобрить", style="success",
                callback_data=f"tiktok_approve:{notification_id}"),
            InlineKeyboardButton(
                text="❌ Отклонить", style="danger",
                callback_data=f"tiktok_reject:{notification_id}"),
        ]
    ])


# ═══════════════════════════════════════════════════════════
#  🆕 Клавиатуры для диалога с оператором
# ═══════════════════════════════════════════════════════════

def get_cancel_ticket_keyboard() -> InlineKeyboardMarkup:
    """Кнопка «Отменить вызов» для клиента."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Отменить вызов", icon_custom_emoji_id="5017122105011995219", style="danger",
            callback_data="ticket_cancel")],
    ])


def get_ticket_close_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка «Закрыть вопрос» для админа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="🔒 Закрыть вопрос",
            callback_data=f"ticket_close:{user_id}")],
    ])


def get_ticket_closed_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Кнопка «Вопрос не был решён» для клиента (после закрытия)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=" Вопрос не был решён", icon_custom_emoji_id="5231311454048636466", style="danger",
            callback_data=f"ticket_resume:{user_id}")],
        [InlineKeyboardButton(
            text="📋 Главное меню",
            callback_data="action_back")],
    ])


def get_post_promo_keyboard() -> InlineKeyboardMarkup:
    """Кнопки после получения промокода или отказа."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text=" Главное меню", icon_custom_emoji_id="5298727751807680461", style="primary",
                callback_data="action_back"),
            InlineKeyboardButton(
                text=" Ещё вопрос", icon_custom_emoji_id="5359844337565866557", style="primary",
                callback_data="action_operator"),
        ]
    ])


def get_dialog_reply_keyboard() -> InlineKeyboardMarkup:
    """Кнопки у ответа оператора (для клиента)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📋 Главное меню",
            callback_data="action_back")],
    ])