#!/usr/bin/env python3
"""
Test script for async Twelve Labs models via API Gateway
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

def test_async_analysis():
    """Test async video analysis with Pegasus"""
    print("🎬 Testing async video analysis...")
    
    payload = {
        "s3Uri": VIDEO_S3_URI,
        "prompt": "Analyze this video and describe what you see"
    }
    
    response = requests.post(f"{API_BASE_URL}/analyze", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 202:
        result = response.json()
        invocation_arn = result.get('invocationArn')
        print(f"✅ Analysis started with ARN: {invocation_arn}")
        return invocation_arn
    else:
        print("❌ Analysis failed to start")
        return None

def test_async_embedding():
    """Test async embedding generation with Marengo"""
    print("\n🔍 Testing async embedding generation...")
    
    payload = {
        "s3Uri": VIDEO_S3_URI,
        "videoId": "test-video-001"
    }
    
    response = requests.post(f"{API_BASE_URL}/embed", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 202:
        result = response.json()
        invocation_arn = result.get('invocationArn')
        print(f"✅ Embedding generation started with ARN: {invocation_arn}")
        return invocation_arn
    else:
        print("❌ Embedding generation failed to start")
        return None

def check_status(invocation_arn, operation_name):
    """Check status of async operation"""
    print(f"\n📊 Checking status for {operation_name}...")
    
    response = requests.get(f"{API_BASE_URL}/status", params={"invocationArn": invocation_arn})
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        result = response.json()
        print(f"Operation Status: {result.get('status')}")
        print(f"Message: {result.get('message', 'No message')}")
        
        if result.get('result'):
            print("Result available:")
            print(json.dumps(result['result'], indent=2))
        
        return result.get('status')
    else:
        print(f"❌ Status check failed: {response.text}")
        return None

def main():
    print("🚀 Testing Async Twelve Labs Models Integration")
    print("=" * 50)
    
    # Test analysis
    analysis_arn = test_async_analysis()
    
    # Test embedding
    embedding_arn = test_async_embedding()
    
    # Check status immediately (should be InProgress)
    if analysis_arn:
        check_status(analysis_arn, "Video Analysis")
    
    if embedding_arn:
        check_status(embedding_arn, "Embedding Generation")
    
    print("\n💡 Note: Both operations are now asynchronous.")
    print("   Use the status endpoint to check for completion.")
    print("   Processing may take several minutes depending on video length.")

if __name__ == "__main__":
    main()
