from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from config import WORK_START_HOUR, TIKTOK_DOMAINS

MSK = ZoneInfo("Europe/Moscow")


def is_work_hours() -> bool:
    now = datetime.now(MSK)
    return WORK_START_HOUR <= now.hour < 24


def is_valid_tiktok_url(url: str) -> bool:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").lower()
        if hostname in TIKTOK_DOMAINS:
            return True
        if hostname.endswith(".tiktok.com"):
            return True
        return False
    except Exception:
        return False


def extract_url_from_text(text: str) -> str | None:
    if not text:
        return None
    for word in text.split():
        word = word.strip()
        if word.startswith(("http://", "https://", "www.", "vm.", "vt.")):
            return word
        if "tiktok.com" in word:
            return word
    return None


def extract_promo_from_url(url: str) -> str:
    """
    Извлекает промокод из TikTok-ссылки — последнюю часть пути.
    Пример: https://vt.tiktok.com/ZSQoJtAXF/ → ZSQoJtAXF
    """
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        parsed = urlparse(url)
        path = parsed.path.rstrip("/")
        return path.split("/")[-1]
    except Exception:
        return "PROMO" + str(hash(url))[-6:].upper()