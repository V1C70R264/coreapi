"""
Admin Configuration Comparison
Simple vs. Detailed approach
"""

# ==========================================
# SIMPLE APPROACH (Basic)
# ==========================================
from django.contrib import admin
from .models import User

# This gives you basic admin with minimal features
admin.site.register(User)

"""
What you get with simple registration:
❌ No search functionality
❌ No filtering options
❌ Shows all fields in a long list
❌ No custom display
❌ Basic form layout
❌ No organization
"""

# ==========================================
# DETAILED APPROACH (Enhanced)
# ==========================================
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """Custom User Admin for our User model"""
    
    # 1. LIST DISPLAY - What columns to show in the user list
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'date_joined')
    # Shows: Username | Email | First Name | Last Name | Staff | Date Joined
    
    # 2. LIST FILTER - Filter options on the right side
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'date_joined')
    # Shows: Filter by Staff Status, Superuser Status, Active Status, Date Joined
    
    # 3. SEARCH FIELDS - Search functionality
    search_fields = ('username', 'email', 'first_name', 'last_name')
    # Shows: Search box that searches across these fields
    
    # 4. ORDERING - How to sort the list
    ordering = ('-date_joined',)
    # Shows: Newest users first
    
    # 5. FIELDSETS - Organized form sections
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    # Shows: Organized sections in the user edit form

"""
What you get with detailed configuration:
✅ Search functionality across multiple fields
✅ Filter by staff status, active status, etc.
✅ Custom display columns
✅ Organized form sections
✅ Better user experience
✅ Professional admin interface
"""

# ==========================================
# MINIMAL CUSTOM APPROACH (Middle ground)
# ==========================================
@admin.register(User)
class SimpleUserAdmin(UserAdmin):
    """Minimal custom admin"""
    list_display = ('username', 'email', 'is_staff')
    search_fields = ('username', 'email')
    # Just the essentials
