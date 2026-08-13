"""
Redis-based JWT Blacklist Implementation
Provides faster token blacklisting using Redis instead of database.
Uses django-redis when the default cache is Redis; otherwise connects via
settings.REDIS_URL (works when cache is LocMemCache in development).
Lazily acquires the Redis client to prevent errors during import/migrations.
"""
import json
import logging
from datetime import datetime, timezone
from django.conf import settings

logger = logging.getLogger(__name__)

def _get_redis_client():
    # Prefer django-redis when the cache backend is actually Redis.
    try:
        from django_redis import get_redis_connection

        return get_redis_connection("default")
    except Exception as e:
        logger.debug("django-redis not available for cache 'default': %s", e)

    # Fallback: connect directly using a dedicated REDIS_URL setting.
    # This works even when the Django cache uses LocMemCache (e.g. in dev).
    try:
        import redis

        url = getattr(settings, "REDIS_URL", None) or "redis://127.0.0.1:6379/1"
        return redis.from_url(url, decode_responses=True)
    except Exception as e:
        logger.error("Unable to initialize Redis client from REDIS_URL: %s", e)
        return None


class RedisBlacklist:
    blacklist_prefix = "blacklist:"
    user_set_prefix = "user_tokens:"

    def blacklist_token(self, token):
        """Add token to Redis blacklist with TTL matching remaining lifetime."""
        client = _get_redis_client()
        if client is None:
            return False
        try:
            jti = token.payload.get('jti')
            if not jti:
                return False
            key = f"{self.blacklist_prefix}{jti}"
            token_data = {
                'jti': jti,
                'user_id': token.payload.get('user_id'),
                'token_type': token.payload.get('token_type'),
                'exp': token.payload.get('exp')
            }
            exp_time = int(token.payload.get('exp', 0) or 0)
            now_ts = int(datetime.now(timezone.utc).timestamp())
            ttl = exp_time - now_ts
            if ttl <= 0:
                # Token already expired; nothing to store
                return True
            # Store blacklist entry with TTL
            client.setex(key, ttl, json.dumps(token_data))

            # Maintain per-user index of JTIs for fast bulk revoke
            user_id = token.payload.get('user_id')
            if user_id is not None:
                user_set_key = f"{self.user_set_prefix}{user_id}"
                client.sadd(user_set_key, jti)
                # Ensure the user set does not outlive all member tokens
                # If no TTL or shorter TTL, extend to at least this token's TTL
                try:
                    current_ttl = client.ttl(user_set_key)
                    if current_ttl is None or current_ttl < 0 or current_ttl < ttl:
                        client.expire(user_set_key, ttl)
                except Exception:
                    # Best-effort; ignore TTL extension failures
                    pass
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False

    def is_token_blacklisted(self, token):
        """Check if token is blacklisted in Redis."""
        client = _get_redis_client()
        if client is None:
            return False
        try:
            jti = token.payload.get('jti')
            if not jti:
                return False
            key = f"{self.blacklist_prefix}{jti}"
            return bool(client.exists(key))
        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return False

    def clear_user_tokens(self, user_id):
        """Clear all blacklisted tokens for a specific user using per-user JTI set."""
        client = _get_redis_client()
        if client is None:
            return False
        try:
            user_set_key = f"{self.user_set_prefix}{user_id}"
            jtis = client.smembers(user_set_key) or []
            if jtis:
                # Pipeline deletions for efficiency
                pipeline = client.pipeline(transaction=False)
                for jti in jtis:
                    pipeline.delete(f"{self.blacklist_prefix}{jti}")
                pipeline.delete(user_set_key)
                pipeline.execute()
            else:
                # Nothing indexed; no-op
                pass
            return True
        except Exception as e:
            logger.error(f"Error clearing user tokens: {e}")
            return False


# Global instance
redis_blacklist = RedisBlacklist()
