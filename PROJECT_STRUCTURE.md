# Project Structure

```
shorts-v2/
├── README.md                    # Main project documentation
├── DETAILED_PLAN.md            # Development plan and architecture
├── PROJECT_STRUCTURE.md        # This file
├── deploy.sh                   # Automated deployment script
├── test_api.py                 # API testing script
├── dev-plan.txt               # Original requirements
│
├── infrastructure/             # AWS CDK Infrastructure
│   ├── bin/
│   │   └── infrastructure.ts   # CDK app entry point
│   ├── lib/
│   │   └── infrastructure-stack.ts  # Main CDK stack definition
│   ├── package.json           # CDK dependencies
│   ├── tsconfig.json          # TypeScript configuration
│   └── cdk.json              # CDK configuration
│
├── backend/                   # Python Lambda functions
│   ├── main.py               # Main Lambda handler
│   ├── requirements.txt      # Python dependencies
│   └── [installed packages]  # Dependencies installed by pip
│
└── frontend/                 # React frontend application
    ├── public/               # Static assets
    ├── src/
    │   ├── components/       # React components
    │   │   ├── VideoUpload.tsx    # Video upload component
    │   │   ├── VideoAnalysis.tsx  # Video analysis component
    │   │   └── VideoSearch.tsx    # Video search component
    │   ├── App.tsx          # Main App component
    │   ├── App.css          # Application styles
    │   └── index.tsx        # React entry point
    ├── package.json         # Frontend dependencies
    ├── .env.example         # Environment variables template
    └── .env                 # Environment variables (created by deploy.sh)
```

## Key Files Description

### Infrastructure (`infrastructure/`)
- **infrastructure-stack.ts**: Defines all AWS resources including S3, Lambda, API Gateway, OpenSearch Serverless, and IAM roles
- **infrastructure.ts**: CDK app entry point, specifies region (ap-northeast-2)

### Backend (`backend/`)
- **main.py**: Lambda function handling all API endpoints:
  - `/upload` - Generate S3 presigned URLs
  - `/analyze` - Call Twelve Labs Pegasus for video analysis
  - `/embed` - Call Twelve Labs Marengo for embedding generation
  - `/search` - Vector similarity search using OpenSearch

### Frontend (`frontend/`)
- **VideoUpload.tsx**: Drag-and-drop video upload with progress tracking
- **VideoAnalysis.tsx**: Interface for video analysis and embedding generation
- **VideoSearch.tsx**: Search interface for finding similar videos
- **App.tsx**: Main application with tab navigation

### Deployment
- **deploy.sh**: Automated deployment script that:
  1. Deploys CDK infrastructure
  2. Extracts API Gateway URL from CloudFormation outputs
  3. Configures frontend environment variables
- **test_api.py**: Simple API testing script to verify deployment

## AWS Resources Created

1. **S3 Bucket**: Video storage with CORS configuration
2. **Lambda Function**: Python 3.11 runtime with Bedrock and OpenSearch permissions
3. **API Gateway**: REST API with CORS enabled
4. **OpenSearch Serverless**: Vector collection for embeddings
5. **IAM Roles**: Minimal permissions for Lambda execution

## Environment Variables

### Frontend (.env)
- `REACT_APP_API_URL`: API Gateway URL

### Lambda (set by CDK)
- `VIDEO_BUCKET`: S3 bucket name
- `OPENSEARCH_ENDPOINT`: OpenSearch collection endpoint
- `REGION`: AWS region (ap-northeast-2)

## Dependencies

### CDK (TypeScript)
- aws-cdk-lib
- @cdklabs/generative-ai-cdk-constructs

### Backend (Python)
- boto3: AWS SDK
- opensearch-py: OpenSearch client
- aws-requests-auth: AWS authentication for OpenSearch

### Frontend (React)
- React 18 with TypeScript
- Standard Create React App dependencies
