#!/usr/bin/env python3
"""
Test script to check available Bedrock methods
"""

import boto3

def check_bedrock_methods():
    """Check available methods in bedrock-runtime client"""
    print("🔍 Checking Bedrock Runtime client methods...")
    
    client = boto3.client('bedrock-runtime', region_name='ap-northeast-2')
    
    # Get all methods
    methods = [method for method in dir(client) if not method.startswith('_')]
    
    print(f"Available methods ({len(methods)}):")
    for method in sorted(methods):
        print(f"  - {method}")
    
    # Check for async methods specifically
    async_methods = [method for method in methods if 'async' in method.lower()]
    print(f"\nAsync-related methods ({len(async_methods)}):")
    for method in async_methods:
        print(f"  - {method}")
    
    # Check boto3 version
    print(f"\nBoto3 version: {boto3.__version__}")

if __name__ == "__main__":
    check_bedrock_methods()
