"""
Хранилище данных в памяти.
В продакшене лучше заменить на Redis/SQLite.
"""

# user_id -> message_id последнего сообщения бота (для редактирования)
user_last_bot_message: dict[int, int] = {}

# notification_message_id -> {user_id, url, promo_code, username}
tiktok_submissions: dict[int, dict] = {}

# user_id -> True, если пользователь ждёт ответа оператора
operator_mode: dict[int, bool] = {}

# admin_notification_id -> user_id (для Reply-ответов)
admin_notification_to_client: dict[int, int] = {}

# 🆕 user_id -> ticket_info
# Активные тикеты диалога с оператором
# ticket_info = {
#   "status": "open" | "closed",
#   "last_admin_msg_id": int | None,
# }
active_tickets: dict[int, dict] = {}