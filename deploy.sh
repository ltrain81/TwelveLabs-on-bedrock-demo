#!/bin/bash

# Video Understanding PoC Deployment Script

set -e

echo "🚀 Starting deployment of Video Understanding PoC..."

# Check if AWS CLI is configured
if ! aws sts get-caller-identity > /dev/null 2>&1; then
    echo "❌ AWS CLI not configured. Please run 'aws configure' first."
    exit 1
fi

# Set region from environment or default to us-east-1 for S3 Vectors support
export AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION:-us-east-1}
echo "📍 Using region: $AWS_DEFAULT_REGION"

# Verify S3 Vectors is supported in this region
if [[ "$AWS_DEFAULT_REGION" != "us-east-1" ]]; then
    echo "⚠️  Warning: S3 Vectors may not be supported in region $AWS_DEFAULT_REGION. Recommended: us-east-1"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Deployment cancelled."
        exit 1
    fi
fi

# Deploy CDK infrastructure
echo "🏗️  Deploying CDK infrastructure..."
cd infrastructure

# Install dependencies
npm install

# Bootstrap CDK (if not already done)
npx cdk bootstrap --region $AWS_DEFAULT_REGION

# Deploy the stack
npx cdk deploy --require-approval never

# Get outputs
API_URL=$(aws cloudformation describe-stacks --stack-name VideoUnderstandingStack --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text --region $AWS_DEFAULT_REGION)
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name VideoUnderstandingStack --query 'Stacks[0].Outputs[?OutputKey==`VideoBucketName`].OutputValue' --output text --region $AWS_DEFAULT_REGION)

echo "✅ Infrastructure deployed successfully!"
echo "📡 API URL: $API_URL"
echo "🪣 S3 Bucket: $BUCKET_NAME"

# Configure frontend
cd ../frontend
echo "⚛️  Configuring React frontend..."

# Create .env file
cat > .env << EOF
REACT_APP_API_URL=${API_URL}
EOF

echo "✅ Frontend configured!"

# Create environment configuration for testing
echo "🧪 Creating test environment configuration..."
cat > .env.test << EOF
API_BASE_URL=${API_URL}
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=${AWS_DEFAULT_REGION}
EOF

echo ""
echo "🎉 Deployment completed successfully!"
echo ""
echo "Next steps:"
echo "1. cd frontend && npm start (to run the frontend locally)"
echo "2. Upload a video and test the analysis"
echo "3. Run tests: source .env.test && python test_final_api.py"
echo ""
echo "📚 API Endpoints:"
echo "   POST $API_URL/upload - Get presigned URL for video upload"
echo "   POST $API_URL/analyze - Analyze video with Pegasus"
echo "   POST $API_URL/embed - Generate embeddings with Marengo"
echo "   GET  $API_URL/search?q=query - Search videos by content"
echo ""
echo "🔧 Environment Configuration:"
echo "   API URL: $API_URL"
echo "   S3 Bucket: $BUCKET_NAME"
echo "   AWS Account: $(aws sts get-caller-identity --query Account --output text)"
echo "   Region: $AWS_DEFAULT_REGION"
