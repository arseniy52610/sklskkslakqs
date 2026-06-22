from aiogram.fsm.state import State, StatesGroup


class UserState(StatesGroup):
    idle = State()                       # Главное меню
    waiting_for_tiktok = State()         # Ожидание TikTok-ссылки
    in_dialog = State()                  # 🆕 В диалоге с оператором