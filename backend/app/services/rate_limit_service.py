from datetime import datetime, timezone
from typing import Any

import redis

from app.config import get_settings

settings = get_settings()

redis_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)

RATE_LIMIT_EXPIRATION_SECONDS = 48 * 60 * 60


def get_current_day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _increment_daily_counter(key: str) -> int:
    count = redis_client.incr(key)

    if count == 1:
        redis_client.expire(key, RATE_LIMIT_EXPIRATION_SECONDS)

    return count


def check_chat_rate_limit(ip_address: str) -> dict[str, Any]:
    date = get_current_day_key()
    ip_key = f"rate_limit:smartdocs:ip:{date}:{ip_address}"
    global_key = f"rate_limit:smartdocs:global:{date}"

    ip_count = _increment_daily_counter(ip_key)
    global_count = _increment_daily_counter(global_key)

    ip_limit = settings.chat_rate_limit_per_ip_daily
    global_limit = settings.chat_rate_limit_global_daily

    allowed = ip_count <= ip_limit and global_count <= global_limit
    reason = None

    if ip_count > ip_limit:
        reason = "ip_daily_limit_exceeded"
    elif global_count > global_limit:
        reason = "global_daily_limit_exceeded"

    return {
        "allowed": allowed,
        "reason": reason,
        "ip_count": ip_count,
        "ip_limit": ip_limit,
        "global_count": global_count,
        "global_limit": global_limit,
    }
