import redis.asyncio as redis
import json
import pickle
from typing import Optional, Any, Union
from app.core.config import settings
import logging
from pythonjsonlogger import jsonlogger

# Configure JSON logger
logger = logging.getLogger("task_manager.cache")
log_handler = logging.StreamHandler()
formatter = jsonlogger.JsonFormatter(
    fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ"
)
log_handler.setFormatter(formatter)
logger.addHandler(log_handler)
logger.setLevel(logging.INFO)

class RedisCache:
    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None

    async def connect(self):
        """Initialize Redis connection"""
        if not self.redis_client:
            self.redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=False
            )
            logger.info("Connected to Redis", extra={"url": settings.REDIS_URL})

    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            logger.info("Disconnecting from Redis")
            await self.redis_client.close()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self.redis_client:
            await self.connect()
        try:
            value = await self.redis_client.get(key)
            if value:
                try:
                    return json.loads(value.decode('utf-8'))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    return pickle.loads(value)
            return None
        except Exception as e:
            logger.error("Cache get error", extra={"key": key, "error": str(e)})
            return None

    async def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        """Set value in cache with expiration"""
        if not self.redis_client:
            await self.connect()
        try:
            try:
                serialized = json.dumps(value, default=str)
            except (TypeError, ValueError):
                serialized = pickle.dumps(value)
            await self.redis_client.setex(key, expire_seconds, serialized)
            logger.debug("Cache set", extra={"key": key, "expire_seconds": expire_seconds})
            return True
        except Exception as e:
            logger.error("Cache set error", extra={"key": key, "error": str(e)})
            return False

    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        if not self.redis_client:
            await self.connect()
        try:
            result = await self.redis_client.delete(key)
            logger.debug("Cache delete", extra={"key": key, "result": result})
            return result > 0
        except Exception as e:
            logger.error("Cache delete error", extra={"key": key, "error": str(e)})
            return False

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        if not self.redis_client:
            await self.connect()
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                result = await self.redis_client.delete(*keys)
                logger.debug("Cache delete pattern", extra={"pattern": pattern, "keys_deleted": result})
                return result
            return 0
        except Exception as e:
            logger.error("Cache delete pattern error", extra={"pattern": pattern, "error": str(e)})
            return 0

    async def get_idempotency(self, key: str) -> Optional[dict]:
        """Get idempotency response from cache"""
        return await self.get(f"idempotency:{key}")

    async def set_idempotency(self, key: str, response: dict) -> bool:
        """Set idempotency response in cache with 24-hour expiration"""
        return await self.set(f"idempotency:{key}", response, expire_seconds=86400)

cache = RedisCache()

# Cache key generators
def make_task_cache_key(user_id: int, filters: dict) -> str:
    """Generate cache key for task list"""
    filter_str = "_".join(f"{k}:{v}" for k, v in sorted(filters.items()) if v is not None)
    return f"tasks:user:{user_id}:{hash(filter_str)}"

def make_task_detail_cache_key(task_id: int) -> str:
    """Generate cache key for single task"""
    return f"task:{task_id}"

def make_user_tasks_cache_key(user_id: int) -> str:
    """Generate cache key pattern for user's tasks"""
    return f"tasks:user:{user_id}:*"