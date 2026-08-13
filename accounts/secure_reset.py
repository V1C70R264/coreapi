"""
Secure Password Reset with Redis
Implements single-use, time-limited tokens for maximum security
"""
import secrets
import logging
from datetime import datetime, timezone
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone as django_timezone

logger = logging.getLogger(__name__)


class SecurePasswordReset:
    """Secure password reset using Redis with single-use tokens"""
    
    RESET_PREFIX = "password_reset:"
    RATE_LIMIT_PREFIX = "reset_rate_limit:"
    AUDIT_PREFIX = "reset_audit:"
    
    # Security settings
    TOKEN_LENGTH = 32  # 256-bit token
    TOKEN_TTL = 900    # 15 minutes
    RATE_LIMIT_WINDOW = 3600  # 1 hour
    MAX_ATTEMPTS_PER_HOUR = 3
    MAX_ATTEMPTS_PER_DAY = 5
    
    @classmethod
    def generate_secure_token(cls):
        """Generate a cryptographically secure random token"""
        return secrets.token_urlsafe(cls.TOKEN_LENGTH)
    
    @classmethod
    def store_reset_token(cls, email, token):
        """Store reset token in Redis with TTL"""
        try:
            key = f"{cls.RESET_PREFIX}{email}"
            token_data = {
                'token': token,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'used': False
            }
            cache.set(key, token_data, timeout=cls.TOKEN_TTL)
            logger.info(f"Reset token stored for {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to store reset token: {e}")
            return False
    
    @classmethod
    def verify_and_consume_token(cls, email, token):
        """Verify token and consume it (single-use)"""
        try:
            key = f"{cls.RESET_PREFIX}{email}"
            token_data = cache.get(key)
            
            if not token_data:
                logger.warning(f"Reset token not found for {email}")
                return False, "Token not found or expired"
            
            if token_data.get('used', False):
                logger.warning(f"Reset token already used for {email}")
                return False, "Token already used"
            
            if token_data.get('token') != token:
                logger.warning(f"Invalid reset token for {email}")
                return False, "Invalid token"
            
            # Consume the token (mark as used)
            token_data['used'] = True
            cache.set(key, token_data, timeout=60)  # Keep for 1 minute for audit
            logger.info(f"Reset token consumed for {email}")
            return True, "Token valid"
            
        except Exception as e:
            logger.error(f"Error verifying reset token: {e}")
            return False, "Token verification failed"
    
    @classmethod
    def check_rate_limit(cls, email, ip_address=None):
        """Check if user has exceeded rate limits"""
        try:
            now = datetime.now(timezone.utc)
            hour_key = f"{cls.RATE_LIMIT_PREFIX}hour:{email}:{now.hour}"
            day_key = f"{cls.RATE_LIMIT_PREFIX}day:{email}:{now.date()}"
            
            # Check hourly limit
            hour_attempts = cache.get(hour_key, 0)
            if hour_attempts >= cls.MAX_ATTEMPTS_PER_HOUR:
                logger.warning(f"Hourly rate limit exceeded for {email}")
                return False, "Too many reset attempts. Please try again later."
            
            # Check daily limit
            day_attempts = cache.get(day_key, 0)
            if day_attempts >= cls.MAX_ATTEMPTS_PER_DAY:
                logger.warning(f"Daily rate limit exceeded for {email}")
                return False, "Daily reset limit exceeded. Please try again tomorrow."
            
            return True, "Rate limit OK"
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True, "Rate limit check failed"  # Allow on error
    
    @classmethod
    def increment_rate_limit(cls, email):
        """Increment rate limit counters"""
        try:
            now = datetime.now(timezone.utc)
            hour_key = f"{cls.RATE_LIMIT_PREFIX}hour:{email}:{now.hour}"
            day_key = f"{cls.RATE_LIMIT_PREFIX}day:{email}:{now.date()}"
            
            # Increment counters
            cache.set(hour_key, cache.get(hour_key, 0) + 1, timeout=3600)
            cache.set(day_key, cache.get(day_key, 0) + 1, timeout=86400)
            
        except Exception as e:
            logger.error(f"Error incrementing rate limit: {e}")
    
    @classmethod
    def log_reset_attempt(cls, email, ip_address, action, success=True):
        """Log password reset attempts for audit"""
        try:
            audit_data = {
                'email': email,
                'ip_address': ip_address,
                'action': action,
                'success': success,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }
            
            # Store in Redis for 30 days
            audit_key = f"{cls.AUDIT_PREFIX}{email}:{int(datetime.now().timestamp())}"
            cache.set(audit_key, audit_data, timeout=2592000)  # 30 days
            
            logger.info(f"Reset audit: {action} for {email} from {ip_address} - {'SUCCESS' if success else 'FAILED'}")
            
        except Exception as e:
            logger.error(f"Error logging reset attempt: {e}")
    
    @classmethod
    def cleanup_expired_tokens(cls):
        """Clean up expired tokens (called periodically)"""
        try:
            # Redis TTL handles this automatically, but we can add manual cleanup if needed
            pass
        except Exception as e:
            logger.error(f"Error cleaning up expired tokens: {e}")


# Global instance
secure_reset = SecurePasswordReset()
