from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

# Register your models here.

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Production-grade User Admin for millions of users"""
    
    # 1. PERFORMANCE OPTIMIZED DISPLAY
    # Using model properties (full_name, initials) - reusable business logic!
    list_display = ('username', 'email', 'full_name', 'initials', 'is_staff', 'is_active', 'date_joined')
    list_display_links = ('username', 'email')  # Clickable links for quick access
    
    # 2. ADVANCED FILTERING (Critical for millions of users)
    list_filter = (
        'is_staff', 
        'is_superuser', 
        'is_active', 
        'date_joined',
        'last_login',
    )
    
    # 3. POWERFUL SEARCH (Essential for large datasets)
    # Note: Can't search on properties directly, but can search on underlying fields
    search_fields = ('username', 'email', 'first_name', 'last_name')
    
    # 4. PERFORMANCE OPTIMIZATIONS
    list_per_page = 50  # Show 50 users per page (not all at once)
    list_max_show_all = 200  # Limit bulk operations
    ordering = ('-date_joined',)  # Newest first
    
    # 5. ORGANIZED FORM SECTIONS (Professional interface)
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)  # Collapsible section
        }),
        ('OAuth / IdP', {
            'fields': ('auth_provider', 'google_sub', 'email_verified', 'last_login_provider'),
            'classes': ('collapse',),
        }),
        ('Important dates', {
            'fields': ('last_login', 'date_joined'),
            'classes': ('collapse',),
        }),
    )
    
    # 6. BULK ACTIONS (For managing large numbers of users)
    actions = ['make_staff', 'make_non_staff', 'activate_users', 'deactivate_users']
    
    def make_staff(self, request, queryset):
        """Bulk action: Make users staff"""
        updated = queryset.update(is_staff=True)
        self.message_user(request, f'{updated} users made staff.')
    make_staff.short_description = "Make selected users staff"
    
    def make_non_staff(self, request, queryset):
        """Bulk action: Remove staff status"""
        updated = queryset.update(is_staff=False)
        self.message_user(request, f'{updated} users removed from staff.')
    make_non_staff.short_description = "Remove staff status"
    
    def activate_users(self, request, queryset):
        """Bulk action: Activate users"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} users activated.')
    activate_users.short_description = "Activate selected users"
    
    def deactivate_users(self, request, queryset):
        """Bulk action: Deactivate users"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} users deactivated.')
    deactivate_users.short_description = "Deactivate selected users"

