#!/usr/bin/env python3
"""
Test script to check what fields the PasswordResetConfirmSerializer expects
"""
import os
import sys
import django

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreAPI.settings')
django.setup()

from accounts.serializers import PasswordResetConfirmSerializer

def test_serializer_fields():
    """Test what fields the serializer expects"""
    print("=== PasswordResetConfirmSerializer Fields ===")
    
    # Create a serializer instance
    serializer = PasswordResetConfirmSerializer()
    
    # Get the fields
    fields = serializer.get_fields()
    
    print("Expected fields:")
    for field_name, field in fields.items():
        print(f"  - {field_name}: {type(field).__name__}")
    
    print(f"\nTotal fields: {len(fields)}")
    
    # Test with sample data
    print("\n=== Testing with sample data ===")
    
    # Test data with email, token, new_password
    test_data = {
        'email': 'test@example.com',
        'token': 'abc123',
        'new_password': 'newpass123'
    }
    
    serializer = PasswordResetConfirmSerializer(data=test_data)
    if serializer.is_valid():
        print("✅ Valid data accepted")
        print(f"Validated data: {serializer.validated_data}")
    else:
        print("❌ Data validation failed")
        print(f"Errors: {serializer.errors}")
    
    # Test with uid (old format)
    test_data_old = {
        'uid': 'abc123',
        'token': 'def456',
        'new_password': 'newpass123'
    }
    
    print("\n=== Testing with old format (uid) ===")
    serializer_old = PasswordResetConfirmSerializer(data=test_data_old)
    if serializer_old.is_valid():
        print("✅ Old format accepted")
    else:
        print("❌ Old format rejected")
        print(f"Errors: {serializer_old.errors}")

if __name__ == "__main__":
    test_serializer_fields()
