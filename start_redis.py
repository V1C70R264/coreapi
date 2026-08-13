#!/usr/bin/env python3
"""
Script to start Redis with Docker and test the connection
"""
import subprocess
import sys
import time
import redis

def start_redis():
    """Start Redis using Docker Compose"""
    try:
        print("Starting Redis with Docker...")
        result = subprocess.run(['docker-compose', 'up', '-d', 'redis'], 
                              capture_output=True, text=True, check=True)
        print("Redis started successfully!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error starting Redis: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False
    except FileNotFoundError:
        print("Docker or docker-compose not found. Please install Docker first.")
        return False

def test_redis_connection():
    """Test Redis connection"""
    try:
        print("Testing Redis connection...")
        client = redis.Redis(host='127.0.0.1', port=6379, db=1, decode_responses=True)
        client.ping()
        print("✅ Redis connection successful!")
        
        # Test basic operations
        client.set('test_key', 'test_value', ex=10)
        value = client.get('test_key')
        print(f"✅ Redis read/write test successful: {value}")
        
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False

def main():
    print("=== Redis Setup for CoreAPI Token Blacklist ===")
    
    # Start Redis
    if not start_redis():
        sys.exit(1)
    
    # Wait a moment for Redis to be ready
    print("Waiting for Redis to be ready...")
    time.sleep(3)
    
    # Test connection
    if test_redis_connection():
        print("\n🎉 Redis is ready for token blacklist functionality!")
        print("You can now run your Django server and test the logout/refresh flow.")
    else:
        print("\n❌ Redis setup failed. Please check Docker installation.")
        sys.exit(1)

if __name__ == "__main__":
    main()
