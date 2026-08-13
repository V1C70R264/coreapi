# Production Password Reset Guide

## API Endpoints

- `POST /api/auth/password-reset/request/`
- `POST /api/auth/password-reset/confirm/`

## Request Flow (Dynamic for Any User Email)

1. Client sends `email` to request endpoint.
2. Backend validates request format and applies rate limiting.
3. Backend always returns the same generic success message (prevents user enumeration).
4. If a matching account exists:
   - Generate `uid` + signed Django token.
   - Build frontend URL using `FRONTEND_URL`.
   - Send a professional HTML email to that user email address.
5. User opens frontend link and submits `uid`, `token`, `new_password`, `confirm_password`.
6. Backend validates token + expiration, updates password, and invalidates active refresh tokens.

## Environment Variables

Required:

- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `FRONTEND_URL`

Optional but recommended:

- `PASSWORD_RESET_TIMEOUT` (default 900 seconds)
- `USE_LOC_MEM_CACHE=0` and `REDIS_URL` in staging/production

## Postman Testing (Production-like)

### 1) Request Password Reset

`POST /api/auth/password-reset/request/`

```json
{
  "email": "real-user@example.com"
}
```

Expected: `200 OK` with generic response.

### 2) Use Real Email

- Check recipient inbox for reset message.
- Confirm:
  - recipient is the requested user email
  - sender is your authenticated SMTP account (`DEFAULT_FROM_EMAIL`)
  - reset link points to your frontend domain

### 3) Confirm Password Reset

`POST /api/auth/password-reset/confirm/`

```json
{
  "uid": "from-email-link",
  "token": "from-email-link",
  "new_password": "NewStrongPassword123!",
  "confirm_password": "NewStrongPassword123!"
}
```

Expected: `200 OK`.

### 4) Invalid Token Test

- Change one character in `token` and retry.
- Expected: `400 Bad Request`, `Invalid or expired reset link.`

### 5) Expired Token Test

- Temporarily set `PASSWORD_RESET_TIMEOUT=60`.
- Request reset, wait >60 seconds, then confirm.
- Expected: `400 Bad Request`, token rejected.

### 6) Multiple Users Test

- Repeat reset requests for different existing users.
- Verify each user receives their own unique link.
- Confirm one user's token cannot reset another user's password.

### 7) Frontend Flow Test

- Frontend route should parse `uid` and `token` from URL query params.
- Frontend posts those values with new password to confirm endpoint.
- Frontend should not trust the link alone; always wait for backend confirm response.

## Rate Limiting Recommendations

- Keep DRF scoped throttles enabled:
  - `password_reset_request`: `5/hour`
  - `password_reset_confirm`: `20/hour`
- Keep per-email Redis counters enabled (`secure_reset`).
- In production, add edge/CDN rate limiting by IP.
- Alert on repeated failures from same IP/email patterns.

## Security Best Practices

- Never reveal whether an email exists.
- Use short token TTL (`PASSWORD_RESET_TIMEOUT`).
- Enforce strong password validation.
- Invalidate active sessions/tokens after reset.
- Use HTTPS-only frontend/backend URLs.
- Store secrets in environment variables only.
- Monitor and alert on SMTP failures and abuse spikes.

## Upgrading Beyond Gmail SMTP

Gmail works for low-to-medium traffic and early-stage SaaS. For higher deliverability and scale:

- SendGrid
- Resend
- Mailgun
- AWS SES

Upgrade path with current architecture:

1. Keep `accounts.password_reset_service` unchanged (business logic layer).
2. Swap `accounts.email_service` implementation (provider SDK/API).
3. Keep API contracts and serializers unchanged.
4. Add async queue (Celery/RQ) for high-volume email dispatch.
5. Add provider webhooks (bounce/complaint handling) without changing reset endpoints.
