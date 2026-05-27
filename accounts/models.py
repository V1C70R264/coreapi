from django.contrib.auth.models import AbstractUser, UserManager as DjangoUserManager
from django.db import models
from django.core.exceptions import ValidationError
import re


class UserManager(DjangoUserManager):
    """Custom user manager: Django's create_user/superuser plus email-centric helpers."""

    use_in_migrations = True
    
    def create_user_from_email(self, email, password=None, **extra_fields):
        """Create user from email (for Google OAuth, etc.)."""
        if not email:
            raise ValueError('Email must be provided')
        
        # Auto-generate username from email if not provided
        if 'username' not in extra_fields:
            base = email.split('@')[0]
            username = base
            counter = 1
            while self.model.objects.filter(username=username).exists():
                username = f"{base}{counter}"
                counter += 1
            extra_fields['username'] = username
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user
    
    def authenticate_by_email(self, email, password):
        """Authenticate user by email instead of username."""
        try:
            user = self.get(email=email)
            if user.check_password(password) and user.is_active:
                return user
        except self.model.DoesNotExist:
            pass
        return None


class User(AbstractUser):
    """Custom User model with business logic in model layer."""

    class AuthProvider(models.TextChoices):
        EMAIL = 'email', 'Email'
        GOOGLE = 'google', 'Google'
        APPLE = 'apple', 'Apple'
        FACEBOOK = 'facebook', 'Facebook'
        GITHUB = 'github', 'GitHub'

    email = models.EmailField(unique=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)

    auth_provider = models.CharField(
        max_length=32,
        choices=AuthProvider.choices,
        default=AuthProvider.EMAIL,
        db_index=True,
    )
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    email_verified = models.BooleanField(default=False)
    last_login_provider = models.CharField(max_length=32, blank=True, default='', db_index=True)

    objects = UserManager()

    @property
    def full_name(self):
        """Returns the full name by combining first_name and last_name."""
        parts = [self.first_name, self.last_name]
        return ' '.join(part for part in parts if part).strip() or self.username

    @property
    def initials(self):
        """Returns initials from first letter of first_name and last_name."""
        initials_list = []
        if self.first_name:
            initials_list.append(self.first_name[0].upper())
        if self.last_name:
            initials_list.append(self.last_name[0].upper())
        # If no names, fallback to first letter of username or email
        if not initials_list:
            fallback = self.username or self.email or 'U'
            initials_list.append(fallback[0].upper())
        return ''.join(initials_list)

    def clean(self):
        """Model-level validation (called by Django forms/admin)."""
        super().clean()
        if self.username:
            self.validate_username(self.username)
        if self.phone:
            self.validate_phone(self.phone)
        if self.first_name:
            self.validate_first_name(self.first_name)
        if self.last_name:
            self.validate_last_name(self.last_name)

    def validate_username(self, value):
        """Validate username format and uniqueness (business logic in model)."""
        if not value:
            raise ValidationError('Username cannot be empty')
        
        if len(value) < 3:
            raise ValidationError('Username must be at least 3 characters long')
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', value):
            raise ValidationError('Username can only contain letters, numbers, underscores, and hyphens')
        
        # Check uniqueness (excluding current user)
        qs = self.__class__.objects.filter(username=value)
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        if qs.exists():
            raise ValidationError('This username is already taken')
        
        return value

    def validate_phone(self, value):
        """Validate phone number format (business logic in model)."""
        if value:
            cleaned = ''.join(filter(str.isdigit, value))
            if len(cleaned) < 10:
                raise ValidationError('Phone number must contain at least 10 digits')
        return value

    def validate_first_name(self, value):
        """Validate first name format (business logic in model)."""
        if value and len(value.strip()) < 1:
            raise ValidationError('First name cannot be empty')
        return value.strip() if value else value

    def validate_last_name(self, value):
        """Validate last name format (business logic in model)."""
        if value and len(value.strip()) < 1:
            raise ValidationError('Last name cannot be empty')
        return value.strip() if value else value

    def delete_old_avatar(self):
        """Delete old avatar file (business logic in model)."""
        if self.avatar:
            try:
                self.avatar.delete(save=False)
            except Exception:
                pass  # Best effort cleanup

    def update_profile(self, username=None, first_name=None, last_name=None, phone=None, avatar=None, clear_avatar=False):
        """Update user profile (business logic in model)."""
        old_avatar = self.avatar
        
        if username is not None:
            self.validate_username(username)
            self.username = username
        
        if first_name is not None:
            self.first_name = self.validate_first_name(first_name)
        
        if last_name is not None:
            self.last_name = self.validate_last_name(last_name)
        
        if phone is not None:
            self.phone = self.validate_phone(phone)
        
        # Handle avatar
        if clear_avatar:
            if old_avatar:
                self.delete_old_avatar()
            self.avatar = None
        elif avatar is not None:
            # If new avatar uploaded and old one exists, delete old one
            if avatar and old_avatar and old_avatar != avatar:
                self.delete_old_avatar()
            self.avatar = avatar
        
        self.save()
        return self

    def change_password(self, current_password, new_password):
        """Change user password (business logic in model)."""
        if not self.check_password(current_password):
            raise ValidationError('Current password is incorrect')
        
        self.set_password(new_password)
        self.save()
        return self

    def __str__(self) -> str:
        return self.full_name or self.username or self.email 
