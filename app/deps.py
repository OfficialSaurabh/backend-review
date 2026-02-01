# deps.py
import os
import redis
from fastapi import Request, HTTPException, Depends
from hashlib import sha256
import json
import time
from app.config import settings


# Upstash Redis connection (rediss://)
UPSTASH_REDIS_URL = settings.UPSTASH_REDIS_URL

r = redis.Redis.from_url(
    UPSTASH_REDIS_URL,
    decode_responses=True,
    ssl_cert_reqs=None,  # required for Upstash TLS
)

GUEST_LIMIT_PER_MIN = 5
AUTH_LIMIT_PER_MIN = 60
MAX_FILE_CHARS_GUEST = 40_000
MAX_FILE_CHARS_AUTH = 200_000
CACHE_TTL = 60 * 60 * 24  # 24h
CACHE_VERSION = "models/gemini-2.5-flash"  # bump when prompt/model changes


def get_user_context(req: Request):
    user = getattr(req.state, "user", None)
    return {
        "is_guest": user is None,
        "user_id": user.id if user else req.client.host
    }


def rate_limit(ctx=Depends(get_user_context)):
    key = f"rate:{ctx['user_id']}:{int(time.time() // 60)}"
    limit = GUEST_LIMIT_PER_MIN if ctx["is_guest"] else AUTH_LIMIT_PER_MIN

    count = r.incr(key)
    r.expire(key, 60)

    if count > limit:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    return ctx


def hash_content(content: str, user_id: str):
    # include version so old cache is invalidated when prompt/model changes
    base = f"{CACHE_VERSION}:{user_id}:{content}"
    return sha256(base.encode("utf-8")).hexdigest()


def get_cached_review(content_hash: str):
    data = r.get(f"review:{content_hash}")
    return json.loads(data) if data else None


def set_cached_review(content_hash: str, result: dict):
    r.setex(
        f"review:{content_hash}",
        CACHE_TTL,
        json.dumps(result)
    )
