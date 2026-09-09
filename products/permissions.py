from rest_framework import permissions


class IsSellerOrAdmin(permissions.BasePermission):
    """
    Custom permission to only allow sellers of a product or admin users to edit it.
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return (
            request.user
            and request.user.is_authenticated
        )

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if request.user.is_staff:
            return True

        return obj.seller == request.user