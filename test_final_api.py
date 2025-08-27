#!/usr/bin/env python3
"""
Final test script for hybrid sync/async Twelve Labs models
"""

import requests
import json
import time
import os
import sys

# API Gateway URL from deployment - use environment variables for dynamic deployment
API_BASE_URL = os.environ.get('API_BASE_URL', "https://your-api-gateway-url/prod")
AWS_ACCOUNT_ID = os.environ.get('AWS_ACCOUNT_ID')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Generate dynamic S3 URI based on deployment
if not AWS_ACCOUNT_ID:
    print("ERROR: AWS_ACCOUNT_ID environment variable must be set")
    print("Get it with: export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)")
    sys.exit(1)

VIDEO_S3_URI = f"s3://video-understanding-{AWS_ACCOUNT_ID}-{AWS_REGION}/videos/test.mp4"

print(f"Using API: {API_BASE_URL}")
print(f"Using S3 URI: {VIDEO_S3_URI}")

def test_sync_analysis():
    """Test synchronous video analysis with Pegasus"""
    print("🎬 Testing synchronous video analysis (Pegasus)...")
    
    payload = {
        "s3Uri": VIDEO_S3_URI,
        "prompt": "Analyze this video and describe what you see"
    }
    
    response = requests.post(f"{API_BASE_URL}/analyze", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print("✅ Analysis completed successfully!")
        print(f"Analysis: {result.get('analysis', 'No analysis returned')[:200]}...")
        return True
    else:
        print(f"❌ Analysis failed: {response.text}")
        return False

def test_async_embedding():
    """Test async embedding generation with Marengo"""
    print("\n🔍 Testing async embedding generation (Marengo)...")
    
    payload = {
        "s3Uri": VIDEO_S3_URI,
        "videoId": "test-video-hybrid-001"
    }
    
    response = requests.post(f"{API_BASE_URL}/embed", json=payload)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 202:
        result = response.json()
        invocation_arn = result.get('invocationArn')
        print(f"✅ Embedding generation started with ARN: {invocation_arn}")
        return invocation_arn
    else:
        print(f"❌ Embedding generation failed: {response.text}")
        return None

def check_embedding_status(invocation_arn):
    """Check status of async embedding operation"""
    print(f"\n📊 Checking embedding status...")
    
    response = requests.get(f"{API_BASE_URL}/status", params={"invocationArn": invocation_arn})
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        status = result.get('status')
        print(f"Embedding Status: {status}")
        print(f"Message: {result.get('message', 'No message')}")
        
        if result.get('result'):
            print("✅ Embedding result available!")
            print("Result preview:", str(result['result'])[:200] + "...")
        
        return status
    else:
        print(f"❌ Status check failed: {response.text}")
        return None

def main():
    print("🚀 Testing Hybrid Twelve Labs Models Integration")
    print("=" * 55)
    print("📋 Implementation Summary:")
    print("   • Pegasus: Synchronous analysis (immediate results)")
    print("   • Marengo: Asynchronous embeddings (check status)")
    print("=" * 55)
    
    # Test synchronous analysis
    analysis_success = test_sync_analysis()
    
    # Test async embedding
    embedding_arn = test_async_embedding()
    
    # Check embedding status
    if embedding_arn:
        embedding_status = check_embedding_status(embedding_arn)
        
        if embedding_status == 'InProgress':
            print("\n⏳ Embedding is still processing...")
            print("   You can check status later using the frontend or:")
            print(f"   curl '{API_BASE_URL}/status?invocationArn={embedding_arn}'")
    
    print("\n" + "=" * 55)
    print("🎯 Summary:")
    print(f"   • Pegasus Analysis: {'✅ Working' if analysis_success else '❌ Failed'}")
    print(f"   • Marengo Embeddings: {'✅ Started' if embedding_arn else '❌ Failed'}")
    print("\n💡 Next Steps:")
    print("   1. Use the React frontend at http://localhost:3000")
    print("   2. Upload videos and test both analysis and embeddings")
    print("   3. Use 'Check Embedding Status' button for async results")

if __name__ == "__main__":
    main()
