import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message as MessageType,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BusinessConnection,
    BusinessMessagesDeleted,
    Update,
    WebAppInfo,
)
from sqlmodel import SQLModel, Session as SQLSession, select, Field
from babel.dates import format_date

import db

# ------------------------
# ТОКЕН БОТА
# ------------------------
TOKEN = "8016703176:AAFU1xJESuJyCqe2gTPeNLAW0_sn56T0tvE"

# ------------------------
# Инициализация бота и диспетчера
# ------------------------
bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# ------------------------
# Админы
# ------------------------
ADMINS = [1947766225]

# ------------------------
# Модели БД
# ------------------------
class Subscription(SQLModel, table=True):
    user_id: int = Field(primary_key=True)
    active_until: datetime | None = None
    last_charge_id: str | None = None


class ChatMessage(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    unique_chat_id: str
    message_id: int
    from_user_id: int
    from_username: str
    from_name: str
    content: str
    content_type: str | None = None
    file_id: str | None = None
    caption: str | None = None
    is_deleted: bool = False
    edited_at: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.now)


# ------------------------
# Проверка подписки
# ------------------------

def is_user_active(session: SQLSession, user_id: int) -> bool:
    sub = session.get(Subscription, user_id)
    return bool(sub and sub.active_until and sub.active_until > datetime.now())


# ------------------------
# Клавиатуры
# ------------------------

def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="📖 Инструкция",
                web_app=WebAppInfo(url="https://arseniy52610.github.io/stite/"),
            ),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="💳 Периоды подписки", callback_data="periods")
        ],
        [
            InlineKeyboardButton(text="💬 Все чаты", callback_data="all_chats")
        ]
    ])


def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])


# ------------------------
# Хелперы
# ------------------------
def get_interlocutor_name(session: SQLSession, unique_chat_id: str, owner_id: int) -> str:
    try:
        other_user_id = int(unique_chat_id.split("_", 1)[1])
    except (IndexError, ValueError):
        return "Неизвестный"

    if other_user_id == owner_id:
        return "Неизвестный"

    stored_message = session.exec(
        select(ChatMessage)
        .where(ChatMessage.unique_chat_id == unique_chat_id)
        .where(ChatMessage.from_user_id == other_user_id)
        .order_by(ChatMessage.created_at.desc())
    ).first()

    if stored_message:
        return stored_message.from_name

    return f"ID {other_user_id}"


# ------------------------
# Старт
# ------------------------
@dp.message(CommandStart())
async def cmd_start(message: MessageType):
    await message.answer(
        f"👋 Привет, {html.bold(message.from_user.full_name)}!\n\n"
        "Delixor сохраняет удалённые и изменённые сообщения в чатах. Ничего лишнего — только контроль и прозрачность",
        reply_markup=start_keyboard()
    )


# ------------------------
# Профиль
# ------------------------
@dp.callback_query(lambda c: c.data == "profile")
async def cb_profile(callback: CallbackQuery):
    session = SQLSession(db.engine)
    user_id = callback.from_user.id
    user = callback.from_user
    sub = session.get(Subscription, user_id)

    text = f"<b>👤 Профиль</b>\n\n<b>🧑‍💻Имя:</b> {user.full_name}\n<b>🆔ID:</b> {user.id}\n"

    if sub and sub.active_until and sub.active_until > datetime.now():
        until = format_date(sub.active_until, "d MMMM yyyy", locale="ru")
        text += f"<b>👤Роль:</b> Тестировщик"
    else:
        text += "<b>Подписка:</b> ❌ не активна"

    await callback.message.edit_text(text, reply_markup=back_keyboard())


# ------------------------
# Периоды подписки
# ------------------------
@dp.callback_query(lambda c: c.data == "periods")
async def cb_periods(callback: CallbackQuery):
    session = SQLSession(db.engine)
    user_id = callback.from_user.id

    if is_user_active(session, user_id):
        sub = session.get(Subscription, user_id)
        await callback.message.edit_text(
            f"⚠️ У вас уже активная подписка до <b>{format_date(sub.active_until, 'd MMMM', locale='ru')}</b>.\n"
            "Новая подписка оформить нельзя пока старая активна.",
            reply_markup=back_keyboard()
        )
        return

    text = (
        "📌 Доступные подписки:\n\n"
        "- Месяц: 100 Stars ⭐\n"
        "- Квартал: 270 Stars ⭐\n"
        "- Год: 1000 Stars ⭐\n\n"
        "Выберите нужный период для оплаты:"
    )
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Месяц", callback_data="pay_month")],
        [InlineKeyboardButton(text="💳 Квартал", callback_data="pay_quarter")],
        [InlineKeyboardButton(text="💳 Год", callback_data="pay_year")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])
    await callback.message.edit_text(text, reply_markup=keyboard)


# ------------------------
# Оплата подписки
# ------------------------
@dp.callback_query(lambda c: c.data in {"pay_month", "pay_quarter", "pay_year"})
async def cb_pay_period(callback: CallbackQuery):
    session = SQLSession(db.engine)
    user_id = callback.from_user.id

    if is_user_active(session, user_id):
        sub = session.get(Subscription, user_id)
        await callback.message.answer(
            f"⚠️ У вас уже есть активная подписка до {format_date(sub.active_until, 'd MMMM', locale='ru')}.\n"
            "Новая подписка оформить нельзя пока старая активна."
        )
        return

    if callback.data == "pay_month":
        amount = 100
        title = "Подписка на месяц"
    elif callback.data == "pay_quarter":
        amount = 270
        title = "Подписка на квартал"
    else:
        amount = 1000
        title = "Подписка на год"

    await callback.message.bot.send_invoice(
        chat_id=user_id,
        title=title,
        description=f"<b>{title} на DelixorBOT</b>",
        payload=f"{callback.data}_{user_id}_{int(datetime.now().timestamp())}",
        currency="XTR",
        prices=[{"label": title, "amount": amount}]
    )


# ------------------------
# Gift подписка
# ------------------------
@dp.message(Command("gift"))
async def cmd_gift(message: MessageType):
    if message.from_user.id not in ADMINS:
        return await message.answer("⚠️ Эта команда доступна только админам!")

    args = message.text.split()
    if len(args) != 2:
        return await message.answer("Использование: /gift <user_id>")

    try:
        user_id = int(args[1])
    except ValueError:
        return await message.answer("⚠️ Некорректный ID пользователя!")

    session = SQLSession(db.engine)
    active_until = datetime.now() + timedelta(days=30)

    sub = session.get(Subscription, user_id)
    if not sub:
        sub = Subscription(user_id=user_id)
    sub.active_until = active_until
    session.add(sub)
    session.commit()

    try:
        await message.bot.send_message(
            chat_id=user_id,
            text=f"🧑‍💻 Вам выдали роль тестировщика до {format_date(active_until, 'd MMMM yyyy', locale='ru')}"
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Роль тестировщика успешна выдана {user_id} до {format_date(active_until, 'd MMMM yyyy', locale='ru')}"
    )


# ------------------------
# Бизнес-сообщения
# ------------------------
@dp.business_connection()
async def handle_business_connection(connection: BusinessConnection):
    user_chat_id = connection.user_chat_id
    if connection.is_enabled:
        await connection.bot.send_message(
            chat_id=user_chat_id,
            text="✅ <b>Бот успешно подключен!</b>\n\nТеперь я буду сохранять и отслеживать сообщения ✨"
        )
    else:
        await connection.bot.send_message(chat_id=user_chat_id, text="Будем вас ждать снова 💖")


# ------------------------
# Inline кнопки
# ------------------------
@dp.callback_query()
async def cb_handler(callback: CallbackQuery):
    session = SQLSession(db.engine)
    if callback.data == "help":
        await callback.message.edit_text(
            "<b>💫 Для подключения Delixor выполните следующие шаги:</b>\n\n"
            "▶ Откройте настройки Telegram\n"
            "▶ Перейдите в раздел «Telegram для Бизнеса»\n"
            "▶ Выберите «Чат-боты» и найдите DelixorBot\n\n"
            "<blockquote>💻 В разрешениях для бота выберите все пункты раздела Сообщения (5/5)</blockquote>\n"
            "<blockquote>⚠️ Для подключения нашего мода требуется Telegram Premium</blockquote>",
            reply_markup=back_keyboard(),
        )
    elif callback.data == "back":
        await callback.message.edit_text(
            f"👋 Привет, {html.bold(callback.from_user.full_name)}!\n\n"
            "Delixor сохраняет удалённые и изменённые сообщения в чатах. Ничего лишнего — только контроль и прозрачность",
            reply_markup=start_keyboard()
        )
    elif callback.data == "all_chats":
        user_id = callback.from_user.id
        chats = session.exec(
            select(ChatMessage.unique_chat_id)
            .where(ChatMessage.unique_chat_id.like(f"{user_id}_%"))
            .distinct()
        ).all()

        if not chats:
            await callback.message.edit_text("💬 Нет сохраненных чатов.", reply_markup=back_keyboard())
            return

        owner_name = callback.from_user.full_name
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"{owner_name} ↔ {get_interlocutor_name(session, chat, user_id)}",
                    callback_data=f"open_chat_{chat}"
                )] for chat in chats
            ] + [[InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]]
        )
        await callback.message.edit_text("💬 Ваши чаты:", reply_markup=keyboard)

    elif callback.data.startswith("open_chat_"):
        unique_chat_id = callback.data[len("open_chat_"):]
        messages = session.exec(
            select(ChatMessage)
            .where(ChatMessage.unique_chat_id == unique_chat_id)
            .order_by(ChatMessage.created_at)
        ).all()

        if not messages:
            await callback.message.edit_text("💬 Сообщения в этом чате отсутствуют.", reply_markup=back_keyboard())
            return

        owner_name = callback.from_user.full_name
        interlocutor_name = get_interlocutor_name(session, unique_chat_id, callback.from_user.id)
        text = f"<b>💬 Чат: {owner_name} ↔ {interlocutor_name}</b>\n\n"

        for msg in messages:
            deleted_flag = msg.is_deleted or "" in msg.content or msg.content.startswith("Само сообщение")
            content = msg.content.replace("", "").strip()
            if deleted_flag:
                content = f"{content} "
            text += f"<b>@{msg.from_username or msg.from_name}:</b> {content}\n\n"

        await callback.message.edit_text(text, reply_markup=back_keyboard())


# ------------------------
# Сохранение сообщений
# ------------------------
@dp.business_message()
async def save_business(message: MessageType):
    session = SQLSession(db.engine)
    bc = await message.bot.get_business_connection(message.business_connection_id)

    # Уникальный чат для 1-на-1 с конкретным собеседником
    if message.from_user.id == bc.user_chat_id:
        other_user_id = message.chat.id
    else:
        other_user_id = message.from_user.id

    unique_chat_id = f"{bc.user_chat_id}_{other_user_id}"

    if not is_user_active(session, bc.user_chat_id):
        await message.bot.send_message(
            chat_id=bc.user_chat_id,
            text="⚠️ У вас нет активной подписки! Оплатите Stars ⭐",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", callback_data="periods")]]
            )
        )
        return

    content_type = None
    file_id = None
    caption = message.caption or ""
    content = message.text or ""

    if message.photo:
        content_type = "photo"
        file_id = message.photo[-1].file_id
        content = caption or "[Фото]"
    elif message.video:
        content_type = "video"
        file_id = message.video.file_id
        content = caption or "[Видео]"
    elif message.document:
        content_type = "document"
        file_id = message.document.file_id
        content = caption or f"[Файл] {message.document.file_name or ''}".strip()
    elif message.audio:
        content_type = "audio"
        file_id = message.audio.file_id
        content = caption or f"[Аудио] {message.audio.title or ''}".strip()
    elif message.voice:
        content_type = "voice"
        file_id = message.voice.file_id
        content = caption or "[Голосовое]"
    elif message.animation:
        content_type = "animation"
        file_id = message.animation.file_id
        content = caption or "[GIF]"

    if message.text or file_id:
        session.add(
            ChatMessage(
                unique_chat_id=unique_chat_id,
                message_id=message.message_id,
                from_user_id=message.from_user.id,
                from_username=message.from_user.username or "",
                from_name=message.from_user.full_name,
                content=content,
                content_type=content_type or "text",
                file_id=file_id,
                caption=caption or None,
            )
        )
        session.commit()


# ------------------------
# Отслеживание изменений сообщений
# ------------------------
@dp.edited_business_message()
async def handle_edited_business_message(message: MessageType):
    session = SQLSession(db.engine)
    bc = await message.bot.get_business_connection(message.business_connection_id)

    if message.from_user.id == bc.user_chat_id:
        other_user_id = message.chat.id
    else:
        other_user_id = message.from_user.id

    unique_chat_id = f"{bc.user_chat_id}_{other_user_id}"
    stored_message = session.exec(
        select(ChatMessage)
        .where(ChatMessage.unique_chat_id == unique_chat_id)
        .where(ChatMessage.message_id == message.message_id)
    ).first()

    if stored_message and message.text:
        old_content = stored_message.content
        stored_message.content = message.text
        stored_message.edited_at = datetime.now()
        session.add(stored_message)
        session.commit()

        username = message.from_user.username or message.from_user.full_name
        await message.bot.send_message(
            chat_id=bc.user_chat_id,
            text=(
                f"<b>✏️@{username} изменил сообщение</b>\n"
                f"<blockquote>💬{old_content} ➜ {message.text}</blockquote>"
            )
        )


# ------------------------
# Отслеживание удалений сообщений
# ------------------------
@dp.deleted_business_messages()
async def handle_deleted_business_messages(deleted: BusinessMessagesDeleted):
    session = SQLSession(db.engine)
    bc = await deleted.bot.get_business_connection(deleted.business_connection_id)

    unique_chat_id = f"{bc.user_chat_id}_{deleted.chat.id}"
    stored_messages = session.exec(
        select(ChatMessage)
        .where(ChatMessage.unique_chat_id == unique_chat_id)
        .where(ChatMessage.message_id.in_(deleted.message_ids))
    ).all()

    if not stored_messages:
        stored_messages = session.exec(
            select(ChatMessage)
            .where(ChatMessage.unique_chat_id.like(f"{bc.user_chat_id}_%"))
            .where(ChatMessage.message_id.in_(deleted.message_ids))
        ).all()
        if not stored_messages:
            return

    for stored_message in stored_messages:
        if stored_message.is_deleted:
            continue
        original_content = stored_message.content
        stored_message.content = f"❌{original_content}"
        stored_message.is_deleted = True
        session.add(stored_message)
        username = stored_message.from_username or stored_message.from_name
        media_caption = f"🗑️ @{username} удалил медиа"
        await deleted.bot.send_message(
            chat_id=bc.user_chat_id,
            text=(
                f"<b>🗑️@{username} удалил сообщение</b>\n"
                f"<blockquote>💬{original_content}</blockquote>"
            )
        )

        if stored_message.file_id and stored_message.content_type:
            if stored_message.content_type == "photo":
                await deleted.bot.send_photo(
                    chat_id=bc.user_chat_id,
                    photo=stored_message.file_id,
                    caption=f"{media_caption}\n{stored_message.caption}".strip()
                    if stored_message.caption
                    else media_caption,
                )
            elif stored_message.content_type == "video":
                await deleted.bot.send_video(
                    chat_id=bc.user_chat_id,
                    video=stored_message.file_id,
                    caption=f"{media_caption}\n{stored_message.caption}".strip()
                    if stored_message.caption
                    else media_caption,
                )
            elif stored_message.content_type == "document":
                await deleted.bot.send_document(
                    chat_id=bc.user_chat_id,
                    document=stored_message.file_id,
                    caption=f"{media_caption}\n{stored_message.caption}".strip()
                    if stored_message.caption
                    else media_caption,
                )
            elif stored_message.content_type == "audio":
                await deleted.bot.send_audio(
                    chat_id=bc.user_chat_id,
                    audio=stored_message.file_id,
                    caption=f"{media_caption}\n{stored_message.caption}".strip()
                    if stored_message.caption
                    else media_caption,
                )
            elif stored_message.content_type == "voice":
                await deleted.bot.send_voice(
                    chat_id=bc.user_chat_id,
                    voice=stored_message.file_id,
                    caption=f"{media_caption}\n{stored_message.caption}".strip()
                    if stored_message.caption
                    else media_caption,
                )
            elif stored_message.content_type == "animation":
                await deleted.bot.send_animation(
                    chat_id=bc.user_chat_id,
                    animation=stored_message.file_id,
                    caption=f"{media_caption}\n{stored_message.caption}".strip()
                    if stored_message.caption
                    else media_caption,
                )

    session.commit()


# ------------------------
# Очистка старых сообщений (3 дня)
# ------------------------
async def cleanup_old_messages():
    while True:
        session = SQLSession(db.engine)
        threshold = datetime.now() - timedelta(days=3)
        old_msgs = session.exec(
            select(ChatMessage).where(ChatMessage.created_at < threshold)
        ).all()
        for msg in old_msgs:
            session.delete(msg)
        session.commit()
        await asyncio.sleep(3600)  # раз в час


# ------------------------
# Запуск
# ------------------------
async def main():
    db.init()
    SQLModel.metadata.create_all(db.engine)
    asyncio.create_task(cleanup_old_messages())
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    asyncio.run(main())
