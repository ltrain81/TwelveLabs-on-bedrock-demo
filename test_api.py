#!/usr/bin/env python3
"""
Simple test script for the Video Understanding API
"""

import requests
import json
import sys
import os

def test_api(api_url):
    """Test the deployed API endpoints"""
    
    print(f"🧪 Testing API at: {api_url}")
    
    # Test 1: Upload endpoint (should return error without proper payload)
    print("\n1. Testing /upload endpoint...")
    try:
        response = requests.post(f"{api_url}/upload", 
                               json={"filename": "test.mp4", "contentType": "video/mp4"})
        if response.status_code == 200:
            print("✅ Upload endpoint working")
            data = response.json()
            print(f"   Response keys: {list(data.keys())}")
        else:
            print(f"❌ Upload endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Upload endpoint error: {e}")
    
    # Test 2: Search endpoint (should work even without data)
    print("\n2. Testing /search endpoint...")
    try:
        response = requests.get(f"{api_url}/search?q=test")
        if response.status_code == 200:
            print("✅ Search endpoint working")
            data = response.json()
            print(f"   Found {data.get('total', 0)} results")
        else:
            print(f"❌ Search endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
    except Exception as e:
        print(f"❌ Search endpoint error: {e}")
    
    # Test 3: Analyze endpoint (should return error without S3 URI)
    print("\n3. Testing /analyze endpoint...")
    try:
        response = requests.post(f"{api_url}/analyze", 
                               json={"prompt": "test"})
        if response.status_code == 400:
            print("✅ Analyze endpoint working (expected 400 error)")
        else:
            print(f"⚠️  Analyze endpoint unexpected response: {response.status_code}")
    except Exception as e:
        print(f"❌ Analyze endpoint error: {e}")
    
    print("\n🎉 API testing completed!")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python test_api.py <API_URL>")
        print("Example: python test_api.py https://abc123.execute-api.ap-northeast-2.amazonaws.com/prod")
        sys.exit(1)
    
    api_url = sys.argv[1].rstrip('/')
    test_api(api_url)
