"""
Custom JWT Authentication with Redis Blacklist
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from .redis_blacklist import redis_blacklist


class RedisJWTAuthentication(JWTAuthentication):
    """
    JWT Authentication that checks Redis blacklist
    """
    
    def get_validated_token(self, raw_token):
        """
        Validates token and checks Redis blacklist
        """
        # Get the token using parent method
        token = super().get_validated_token(raw_token)
        
        # Check if token is blacklisted in Redis
        jti = token.payload.get('jti')
        is_blacklisted = redis_blacklist.is_token_blacklisted(token)
        print(f"DEBUG: Checking token JTI: {jti}, Is blacklisted: {is_blacklisted}")
        
        if is_blacklisted:
            print(f"DEBUG: Token {jti} is blacklisted, rejecting")
            raise InvalidToken('Token is blacklisted')
        
        return token
