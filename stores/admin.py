from django.contrib import admin
from .models import Store, StoreStatus


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'status', 'is_active', 'created_at')
    list_filter = ('status', 'is_active')
    search_fields = ('name', 'owner__username')
    actions = ['approve_stores', 'reject_stores']

    @admin.action(description='Approve selected stores')
    def approve_stores(self, request, queryset):
        updated = queryset.update(status=StoreStatus.APPROVED, rejection_reason='')
        self.message_user(request, f'{updated} store(s) approved.')

    @admin.action(description='Reject selected stores')
    def reject_stores(self, request, queryset):
        updated = queryset.update(status=StoreStatus.REJECTED)
        self.message_user(
            request,
            f'{updated} store(s) rejected. Open each one and fill in the '
            f'rejection reason so the seller can see why.',
        )