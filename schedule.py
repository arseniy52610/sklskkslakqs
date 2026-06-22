from datetime import datetime
import pytz
from config import WORK_START_HOUR, WORK_END_HOUR, TIMEZONE


def is_work_hours() -> bool:
    """True, если сейчас рабочее время (09:00–24:00 МСК)."""
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    return WORK_START_HOUR <= now.hour < WORK_END_HOUR