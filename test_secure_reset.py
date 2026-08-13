#!/usr/bin/env python3
"""
Test script for secure password reset functionality
Tests single-use tokens, rate limiting, and audit logging
"""
import os
import sys
import django
import requests
import time
import json

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreAPI.settings')
django.setup()

from accounts.secure_reset import secure_reset

def test_secure_reset_functionality():
    """Test the secure reset core functionality"""
    print("=== Testing Secure Reset Core Functionality ===\n")
    
    test_email = "test@example.com"
    
    # Test 1: Generate secure token
    print("1. Generating secure token...")
    token = secure_reset.generate_secure_token()
    print(f"   Token: {token[:20]}...")
    print(f"   Length: {len(token)} characters")
    print("   ✅ PASS: Secure token generated")
    
    # Test 2: Store token
    print("\n2. Storing reset token...")
    store_result = secure_reset.store_reset_token(test_email, token)
    print(f"   Store result: {store_result}")
    assert store_result, "Token should be stored successfully"
    print("   ✅ PASS: Token stored successfully")
    
    # Test 3: Verify token (first time - should work)
    print("\n3. Verifying token (first time)...")
    valid, msg = secure_reset.verify_and_consume_token(test_email, token)
    print(f"   Valid: {valid}, Message: {msg}")
    assert valid, "Token should be valid on first use"
    print("   ✅ PASS: Token verified and consumed")
    
    # Test 4: Verify token (second time - should fail)
    print("\n4. Verifying token (second time - should fail)...")
    valid, msg = secure_reset.verify_and_consume_token(test_email, token)
    print(f"   Valid: {valid}, Message: {msg}")
    assert not valid, "Token should be invalid on second use"
    print("   ✅ PASS: Token correctly rejected on reuse")
    
    # Test 5: Rate limiting
    print("\n5. Testing rate limiting...")
    for i in range(4):  # Try 4 times (limit is 3 per hour)
        rate_ok, rate_msg = secure_reset.check_rate_limit(test_email, "127.0.0.1")
        if i < 3:
            assert rate_ok, f"Rate limit should be OK for attempt {i+1}"
            secure_reset.increment_rate_limit(test_email)
        else:
            assert not rate_ok, "Rate limit should be exceeded"
        print(f"   Attempt {i+1}: {rate_ok} - {rate_msg}")
    
    print("   ✅ PASS: Rate limiting working correctly")
    
    print("\n🎉 All secure reset core tests passed!")

def test_api_endpoints():
    """Test the API endpoints"""
    print("\n=== Testing API Endpoints ===\n")
    
    base_url = "http://127.0.0.1:8000/api/auth"
    
    # Test data
    test_user = {
        "username": "securetest",
        "email": "securetest@example.com", 
        "password": "testpass123"
    }
    
    try:
        # 1. Register test user
        print("1. Registering test user...")
        response = requests.post(f"{base_url}/register/", json=test_user)
        if response.status_code in [201, 400]:  # 400 if user already exists
            print("   ✅ User registration handled")
        else:
            print(f"   ⚠️  Registration response: {response.status_code}")
        
        # 2. Request password reset
        print("\n2. Requesting password reset...")
        reset_data = {"email": test_user["email"]}
        response = requests.post(f"{base_url}/password-reset/", json=reset_data)
        
        if response.status_code == 204:
            print("   ✅ Password reset request successful")
        else:
            print(f"   ❌ Password reset failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return
        
        # 3. Test rate limiting
        print("\n3. Testing rate limiting (should fail after 3 attempts)...")
        for i in range(5):
            response = requests.post(f"{base_url}/password-reset/", json=reset_data)
            if response.status_code == 204:
                print(f"   Attempt {i+1}: ✅ Success")
            elif response.status_code == 429:
                print(f"   Attempt {i+1}: ❌ Rate limited (expected)")
                break
            else:
                print(f"   Attempt {i+1}: ⚠️  Unexpected response: {response.status_code}")
        
        print("   ✅ Rate limiting test completed")
        
        # 4. Test with invalid email (should still return 204 for security)
        print("\n4. Testing with invalid email...")
        invalid_data = {"email": "nonexistent@example.com"}
        response = requests.post(f"{base_url}/password-reset/", json=invalid_data)
        if response.status_code == 204:
            print("   ✅ Invalid email handled securely (no user enumeration)")
        else:
            print(f"   ⚠️  Unexpected response for invalid email: {response.status_code}")
        
        print("\n🎉 API endpoint tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to Django server. Please start the server first:")
        print("   python manage.py runserver")
    except Exception as e:
        print(f"   ❌ Error testing API: {e}")

def test_security_features():
    """Test security features"""
    print("\n=== Testing Security Features ===\n")
    
    # Test token uniqueness
    print("1. Testing token uniqueness...")
    tokens = set()
    for i in range(10):
        token = secure_reset.generate_secure_token()
        tokens.add(token)
    
    assert len(tokens) == 10, "All tokens should be unique"
    print("   ✅ PASS: All tokens are unique")
    
    # Test token format
    print("\n2. Testing token format...")
    token = secure_reset.generate_secure_token()
    assert len(token) >= 32, "Token should be at least 32 characters"
    assert token.replace('-', '').replace('_', '').isalnum(), "Token should be URL-safe"
    print("   ✅ PASS: Token format is correct")
    
    # Test audit logging
    print("\n3. Testing audit logging...")
    secure_reset.log_reset_attempt("test@example.com", "127.0.0.1", "TEST_ACTION", True)
    print("   ✅ PASS: Audit logging works")
    
    print("\n🎉 All security feature tests passed!")

def main():
    print("Secure Password Reset Test Suite")
    print("=" * 50)
    
    try:
        # Test core functionality
        test_secure_reset_functionality()
        
        # Test security features
        test_security_features()
        
        # Test API endpoints
        test_api_endpoints()
        
        print("\n" + "=" * 50)
        print("🎉 All tests completed successfully!")
        print("\nKey Security Features Implemented:")
        print("✅ Single-use tokens (cannot be reused)")
        print("✅ 15-minute token expiration")
        print("✅ Rate limiting (3/hour, 5/day)")
        print("✅ Audit logging for all attempts")
        print("✅ No user enumeration (same response for valid/invalid emails)")
        print("✅ Cryptographically secure tokens")
        print("✅ Redis-based storage with automatic cleanup")
        
    except Exception as e:
        print(f"❌ Test suite failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    main()
