from urllib.parse import urlparse
from config import TIKTOK_DOMAINS


def is_valid_tiktok_link(text: str) -> bool:
    """
    Возвращает True, если в тексте есть валидная ссылка на tiktok.com.
    Проверяет домен строго — только официальные домены TikTok.
    """
    if not text:
        return False

    words = text.strip().split()
    for word in words:
        if not word.startswith("http"):
            word = "https://" + word
        try:
            parsed = urlparse(word)
            host = (parsed.netloc or "").lower()
            if host in TIKTOK_DOMAINS and "/video/" in parsed.path:
                return True
        except Exception:
            continue
    return False


def extract_tiktok_url(text: str) -> str | None:
    """Достаёт саму ссылку TikTok из текста."""
    for word in text.strip().split():
        if not word.startswith("http"):
            word = "https://" + word
        try:
            parsed = urlparse(word)
            if parsed.netloc.lower() in TIKTOK_DOMAINS:
                return word
        except Exception:
            continue
    return None