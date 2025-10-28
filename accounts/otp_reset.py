"""
Modern OTP-Based Password Reset Implementation
Replaces email link with OTP for better mobile UX
"""
import secrets
import logging
from datetime import datetime, timezone
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


class OTPPasswordReset:
    """OTP-based password reset for mobile apps"""
    
    OTP_PREFIX = "password_reset_otp:"
    RATE_LIMIT_PREFIX = "otp_rate_limit:"
    
    # Security settings
    OTP_LENGTH = 6
    OTP_TTL = 300  # 5 minutes
    MAX_ATTEMPTS_PER_HOUR = 3
    MAX_ATTEMPTS_PER_DAY = 5
    
    @classmethod
    def generate_otp(cls):
        """Generate 6-digit OTP"""
        return str(secrets.randbelow(1000000)).zfill(6)
    
    @classmethod
    def store_otp(cls, email, otp):
        """Store OTP in Redis with TTL"""
        try:
            key = f"{cls.OTP_PREFIX}{email}"
            otp_data = {
                'otp': otp,
                'created_at': datetime.now(timezone.utc).isoformat(),
                'attempts': 0,
                'verified': False
            }
            cache.set(key, otp_data, timeout=cls.OTP_TTL)
            logger.info(f"OTP stored for {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to store OTP: {e}")
            return False
    
    @classmethod
    def verify_otp(cls, email, otp):
        """Verify OTP and mark as used"""
        try:
            key = f"{cls.OTP_PREFIX}{email}"
            otp_data = cache.get(key)
            
            if not otp_data:
                return False, "OTP not found or expired"
            
            if otp_data.get('verified', False):
                return False, "OTP already used"
            
            if otp_data.get('otp') != otp:
                # Increment attempts
                otp_data['attempts'] += 1
                cache.set(key, otp_data, timeout=cls.OTP_TTL)
                return False, "Invalid OTP"
            
            # Mark as verified
            otp_data['verified'] = True
            cache.set(key, otp_data, timeout=60)  # Keep for 1 minute for audit
            logger.info(f"OTP verified for {email}")
            return True, "OTP verified"
            
        except Exception as e:
            logger.error(f"Error verifying OTP: {e}")
            return False, "OTP verification failed"
    
    @classmethod
    def check_rate_limit(cls, email):
        """Check OTP rate limits"""
        try:
            now = datetime.now(timezone.utc)
            hour_key = f"{cls.RATE_LIMIT_PREFIX}hour:{email}:{now.hour}"
            day_key = f"{cls.RATE_LIMIT_PREFIX}day:{email}:{now.date()}"
            
            hour_attempts = cache.get(hour_key, 0)
            if hour_attempts >= cls.MAX_ATTEMPTS_PER_HOUR:
                return False, "Too many OTP requests. Please try again later."
            
            day_attempts = cache.get(day_key, 0)
            if day_attempts >= cls.MAX_ATTEMPTS_PER_DAY:
                return False, "Daily OTP limit exceeded. Please try again tomorrow."
            
            return True, "Rate limit OK"
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return True, "Rate limit check failed"
    
    @classmethod
    def increment_rate_limit(cls, email):
        """Increment OTP rate limit counters"""
        try:
            now = datetime.now(timezone.utc)
            hour_key = f"{cls.RATE_LIMIT_PREFIX}hour:{email}:{now.hour}"
            day_key = f"{cls.RATE_LIMIT_PREFIX}day:{email}:{now.date()}"
            
            cache.set(hour_key, cache.get(hour_key, 0) + 1, timeout=3600)
            cache.set(day_key, cache.get(day_key, 0) + 1, timeout=86400)
            
        except Exception as e:
            logger.error(f"Error incrementing rate limit: {e}")
    
    @classmethod
    def send_otp_email(cls, email, otp):
        """Send OTP via email"""
        try:
            subject = 'Password Reset Code'
            message = f'Your password reset code is: {otp}\n\nThis code expires in 5 minutes.\n\nIf you did not request this, please ignore this email.'
            
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                recipient_list=[email],
                fail_silently=False,
            )
            logger.info(f"OTP email sent to {email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send OTP email: {e}")
            return False


# Global instance
otp_reset = OTPPasswordReset()
