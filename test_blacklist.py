#!/usr/bin/env python3
"""
Test script for token blacklist functionality
"""
import os
import sys
import django
import requests
import json

# Add the project directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'CoreAPI.settings')
django.setup()

from rest_framework_simplejwt.tokens import RefreshToken
from accounts.redis_blacklist import redis_blacklist

def test_blacklist_functionality():
    """Test the Redis blacklist functionality"""
    print("=== Testing Token Blacklist Functionality ===\n")
    
    # Create a test token
    print("1. Creating a test refresh token...")
    refresh = RefreshToken()
    refresh_token_str = str(refresh)
    jti = refresh.payload.get('jti')
    print(f"   Token JTI: {jti}")
    print(f"   Token: {refresh_token_str[:50]}...")
    
    # Test 1: Token should not be blacklisted initially
    print("\n2. Checking if token is blacklisted (should be False)...")
    is_blacklisted = redis_blacklist.is_token_blacklisted(refresh)
    print(f"   Is blacklisted: {is_blacklisted}")
    assert not is_blacklisted, "Token should not be blacklisted initially"
    print("   ✅ PASS: Token is not blacklisted")
    
    # Test 2: Blacklist the token
    print("\n3. Blacklisting the token...")
    blacklist_result = redis_blacklist.blacklist_token(refresh)
    print(f"   Blacklist result: {blacklist_result}")
    assert blacklist_result, "Token should be successfully blacklisted"
    print("   ✅ PASS: Token blacklisted successfully")
    
    # Test 3: Token should now be blacklisted
    print("\n4. Checking if token is blacklisted (should be True)...")
    is_blacklisted = redis_blacklist.is_token_blacklisted(refresh)
    print(f"   Is blacklisted: {is_blacklisted}")
    assert is_blacklisted, "Token should be blacklisted now"
    print("   ✅ PASS: Token is correctly blacklisted")
    
    print("\n🎉 All blacklist tests passed!")
    return True

def test_api_endpoints():
    """Test the actual API endpoints"""
    print("\n=== Testing API Endpoints ===\n")
    
    base_url = "http://127.0.0.1:8000/api/auth"
    
    # Test data - use unique email to avoid conflicts
    import time
    timestamp = int(time.time())
    test_user = {
        "username": f"testuser{timestamp}",
        "email": f"test{timestamp}@example.com", 
        "password": "testpass123"
    }
    
    try:
        # 1. Register a test user
        print("1. Registering test user...")
        response = requests.post(f"{base_url}/register/", json=test_user)
        if response.status_code == 201:
            print("   ✅ User registered successfully")
        elif response.status_code == 400:
            print("   ⚠️  User might already exist, continuing with login...")
        else:
            print(f"   ⚠️  Registration response: {response.status_code}")
            print(f"   Response: {response.text}")
        
        # 2. Login to get tokens
        print("\n2. Logging in to get tokens...")
        login_data = {
            "email": test_user["email"],
            "password": test_user["password"]
        }
        response = requests.post(f"{base_url}/login/", json=login_data)
        
        if response.status_code == 200:
            tokens = response.json()
            refresh_token = tokens.get('refresh')
            access_token = tokens.get('access')
            print("   ✅ Login successful")
            print(f"   Access token: {access_token[:50]}...")
            print(f"   Refresh token: {refresh_token[:50]}...")
            
            # 3. Test token refresh (should work)
            print("\n3. Testing token refresh (should work)...")
            refresh_data = {"refresh": refresh_token}
            response = requests.post(f"{base_url}/token/refresh/", json=refresh_data)
            
            if response.status_code == 200:
                new_tokens = response.json()
                print("   ✅ Token refresh successful")
                print(f"   New access token: {new_tokens.get('access', '')[:50]}...")
            else:
                print(f"   ❌ Token refresh failed: {response.status_code}")
                print(f"   Response: {response.text}")
            
            # 4. Logout (blacklist the token)
            print("\n4. Logging out (blacklisting token)...")
            logout_data = {"refresh": refresh_token}
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.post(f"{base_url}/logout/", json=logout_data, headers=headers)
            
            if response.status_code == 205:
                print("   ✅ Logout successful - token blacklisted")
            else:
                print(f"   ❌ Logout failed: {response.status_code}")
                print(f"   Response: {response.text}")
            
            # 5. Test token refresh after logout (should fail)
            print("\n5. Testing token refresh after logout (should fail)...")
            refresh_data = {"refresh": refresh_token}
            response = requests.post(f"{base_url}/token/refresh/", json=refresh_data)
            
            if response.status_code == 401:
                print("   ✅ Token refresh correctly rejected after logout")
                print(f"   Response: {response.json()}")
            else:
                print(f"   ❌ Token refresh should have failed but got: {response.status_code}")
                print(f"   Response: {response.text}")
                
        else:
            print(f"   ❌ Login failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to Django server. Please start the server first:")
        print("   python manage.py runserver")
    except Exception as e:
        print(f"   ❌ Error testing API: {e}")

def main():
    print("Token Blacklist Test Suite")
    print("=" * 50)
    
    # Test Redis blacklist functionality
    try:
        test_blacklist_functionality()
    except Exception as e:
        print(f"❌ Blacklist functionality test failed: {e}")
        return False
    
    # Test API endpoints
    test_api_endpoints()
    
    print("\n" + "=" * 50)
    print("Test suite completed!")

if __name__ == "__main__":
    main()
