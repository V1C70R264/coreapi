# Token Blacklist Setup Guide

This guide will help you set up Redis-based token blacklisting for your Django CoreAPI project.

## Problem Solved

Previously, after logout, the token refresh endpoint would still return new access and refresh tokens. Now, blacklisted tokens are properly rejected during refresh.

## Setup Steps

### 1. Install Dependencies

```bash
pip install django-redis redis
```

### 2. Start Redis with Docker

```bash
# Option 1: Use the provided script
python start_redis.py

# Option 2: Manual Docker commands
docker-compose up -d redis
```

### 3. Verify Redis Connection

```bash
# Test Redis connection
python -c "import redis; r = redis.Redis(host='127.0.0.1', port=6379, db=1); print('Redis OK:', r.ping())"
```

### 4. Start Django Server

```bash
python manage.py runserver
```

## Testing the Blacklist Functionality

### Automated Testing

```bash
# Run the comprehensive test suite
python test_blacklist.py
```

### Manual Testing

1. **Register a user:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/register/ \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "email": "test@example.com", "password": "testpass123"}'
   ```

2. **Login to get tokens:**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/login/ \
     -H "Content-Type: application/json" \
     -d '{"username": "testuser", "password": "testpass123"}'
   ```

3. **Test token refresh (should work):**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
     -H "Content-Type: application/json" \
     -d '{"refresh": "YOUR_REFRESH_TOKEN"}'
   ```

4. **Logout (blacklist token):**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/logout/ \
     -H "Content-Type: application/json" \
     -d '{"refresh": "YOUR_REFRESH_TOKEN"}'
   ```

5. **Test token refresh after logout (should fail):**
   ```bash
   curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
     -H "Content-Type: application/json" \
     -d '{"refresh": "YOUR_REFRESH_TOKEN"}'
   ```
   Expected response: `{"detail": "Token is blacklisted"}` with status 401

## Key Changes Made

### 1. Fixed TokenRefresh View
- Added blacklist check before issuing new tokens
- Returns 401 with "Token is blacklisted" message for blacklisted refresh tokens

### 2. Redis Configuration
- Added Redis cache configuration in `settings.py`
- Uses database 1 to avoid conflicts with other Redis usage

### 3. Docker Setup
- Created `docker-compose.yml` for easy Redis deployment
- Redis runs on port 6379 with persistent storage

## Debug Information

The implementation includes debug logging. Check your Django console for messages like:
- `DEBUG: TokenRefresh - Checking refresh token JTI: ...`
- `DEBUG: TokenRefresh - Refresh token is blacklisted, rejecting`
- `DEBUG: Blacklist result: True`

## Troubleshooting

### Redis Connection Issues
```bash
# Check if Redis is running
docker ps | grep redis

# Check Redis logs
docker logs coreapi_redis

# Restart Redis
docker-compose restart redis
```

### Django Cache Issues
```bash
# Test Django cache connection
python manage.py shell
>>> from django.core.cache import cache
>>> cache.set('test', 'value')
>>> cache.get('test')
```

### Token Issues
- Ensure JTI (JWT ID) is present in token payload
- Check that `SIMPLE_JWT['JTI_CLAIM'] = 'jti'` is set in settings
- Verify token expiration times are reasonable

## Files Modified

1. `accounts/views.py` - Fixed TokenRefresh view
2. `CoreAPI/settings.py` - Added Redis cache configuration
3. `docker-compose.yml` - Redis Docker setup
4. `start_redis.py` - Redis startup script
5. `test_blacklist.py` - Comprehensive test suite

## Expected Behavior

✅ **Before Fix:** Logout → Token refresh still works (BAD)  
✅ **After Fix:** Logout → Token refresh returns 401 "Token is blacklisted" (GOOD)

The token blacklist now properly prevents refresh token reuse after logout!
