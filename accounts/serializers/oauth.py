"""OAuth / social IdP request serializers (Google, Apple, …)."""

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers


class GoogleIdTokenSerializer(serializers.Serializer):
    """
    Request body for POST /api/auth/google/.

    Signature, audience, expiration, and issuer are enforced in ``GoogleIdentityProvider``
    via ``google.oauth2.id_token.verify_oauth2_token`` (not in this serializer).
    """

    id_token = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_id_token(self, value: str) -> str:
        if not value or not str(value).strip():
            raise serializers.ValidationError(_('ID token is required.'))
        return value
