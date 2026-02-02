import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, html
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message as MessageType,
    CallbackQuery,
    LabeledPrice,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    PreCheckoutQuery,
    BusinessConnection,
    BusinessMessagesDeleted
)
from aiogram.client.default import DefaultBotProperties
from sqlmodel import SQLModel, Session as SQLSession, select, Field
from babel.dates import format_date

import db
from db.models.message import Message

# ------------------------
# ТОКЕН БОТА (ПРЯМО В КОДЕ)
# ------------------------
TOKEN = "ВАШ_ТОКЕН_БОТА_ЗДЕСЬ"

# ------------------------
# Инициализация бота и диспетчера (aiogram 3.7+)
# ------------------------
bot = Bot(
    token=TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

# ------------------------
# Админы
# ------------------------
ADMINS = [1947766225]

# ------------------------
# Таблица подписок
# ------------------------
class Subscription(SQLModel, table=True):
    user_id: int = Field(primary_key=True)
    active_until: datetime | None = None
    last_charge_id: str | None = None

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
            InlineKeyboardButton(text="📖 Инструкция", callback_data="help"),
            InlineKeyboardButton(text="👤 Профиль", callback_data="profile")
        ],
        [
            InlineKeyboardButton(text="💳 Периоды подписки", callback_data="periods")
        ],
    ])

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])

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
        text += f"<b>✅Подписка активна до:</b> {until}"
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
        days = 30
        title = "Подписка на месяц"
    elif callback.data == "pay_quarter":
        amount = 270
        days = 90
        title = "Подписка на квартал"
    else:
        amount = 1000
        days = 365
        title = "Подписка на год"

    prices = [LabeledPrice(label=title, amount=amount)]
    await callback.message.bot.send_invoice(
        chat_id=user_id,
        title=title,
        description=f"<b>{title} на DelixorBOT</b>",
        payload=f"{callback.data}_{user_id}_{int(datetime.now().timestamp())}",
        currency="XTR",
        prices=prices
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
            text=f"🎁 Вам подарили подписку на DelixorBOT!\n✅ Подписка активна до {format_date(active_until, 'd MMMM yyyy', locale='ru')}"
        )
    except Exception:
        pass

    await message.answer(
        f"✅ Подписка успешно подарена пользователю {user_id} до {format_date(active_until, 'd MMMM yyyy', locale='ru')}"
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

# ------------------------
# PreCheckout
# ------------------------
@dp.pre_checkout_query()
async def pre_checkout(q: PreCheckoutQuery):
    await q.answer(ok=True)

# ------------------------
# Успешная оплата
# ------------------------
@dp.message()
async def on_success_pay(message: MessageType):
    payment = message.successful_payment
    if not payment:
        return

    session = SQLSession(db.engine)
    user_id = message.from_user.id
    active_until = datetime.now() + timedelta(days=30)

    sub = session.get(Subscription, user_id)
    if not sub:
        sub = Subscription(user_id=user_id)
    sub.active_until = active_until
    sub.last_charge_id = payment.telegram_payment_charge_id
    session.add(sub)
    session.commit()

    await message.answer(
        f"✅ Успешно! Ваша подписка активна до {format_date(active_until, 'd MMMM yyyy', locale='ru')}"
    )

# ------------------------
# Удаление сообщений
# ------------------------
@dp.deleted_business_messages()
async def handle_deleted(deleted: BusinessMessagesDeleted):
    session = SQLSession(db.engine)
    bc = await deleted.bot.get_business_connection(deleted.business_connection_id)
    user_chat = bc.user_chat_id

    for mid in deleted.message_ids:
        msg = session.exec(
            select(Message).where(Message.chat_id == user_chat).where(Message.id == mid)
        ).first()
        if msg:
            text = f"<b>🗑️@{msg.from_username} удалил сообщение</b>\n<blockquote>💬{msg.content}</blockquote>"
            await deleted.bot.send_message(chat_id=user_chat, text=text)

# ------------------------
# Редактирование сообщений
# ------------------------
@dp.edited_business_message()
async def handle_edit(message: MessageType):
    session = SQLSession(db.engine)
    bc = await message.bot.get_business_connection(message.business_connection_id)
    user_chat = bc.user_chat_id

    old_msg = session.exec(
        select(Message).where(Message.chat_id == user_chat).where(Message.id == message.message_id)
    ).first()
    if old_msg and old_msg.type == "text":
        text = f"<b>✏️@{old_msg.from_username} изменил сообщение</b>\n<blockquote>💬{old_msg.content} ➜ {message.text}</blockquote>"
        await message.bot.send_message(chat_id=user_chat, text=text)
        old_msg.content = message.text
        session.add(old_msg)
        session.commit()

# ------------------------
# Сохранение сообщений
# ------------------------
@dp.business_message()
async def save_business(message: MessageType):
    session = SQLSession(db.engine)
    bc = await message.bot.get_business_connection(message.business_connection_id)
    user_chat = bc.user_chat_id

    if not is_user_active(session, user_chat):
        await message.bot.send_message(
            chat_id=user_chat,
            text="⚠️ У вас нет активной подписки! Оплатите Stars ⭐",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="💳 Оплатить", callback_data="periods")]]
            )
        )
        return

    if message.text:
        session.add(
            Message(
                chat_id=user_chat,
                id=message.message_id,
                type="text",
                content=message.text,
                from_username=message.from_user.username or ""
            )
        )
        session.commit()

# ------------------------
# Запуск
# ------------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    db.init()
    SQLModel.metadata.create_all(db.engine)
    asyncio.run(main())