import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as opensearchserverless from 'aws-cdk-lib/aws-opensearchserverless';
import { Construct } from 'constructs';
import * as path from 'path';

export class InfrastructureStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // S3 bucket for video storage
    const videoBucket = new s3.Bucket(this, 'VideoBucket', {
      bucketName: `video-understanding-${this.account}-${this.region}`,
      cors: [
        {
          allowedHeaders: ['*'],
          allowedMethods: [
            s3.HttpMethods.GET,
            s3.HttpMethods.POST,
            s3.HttpMethods.PUT,
            s3.HttpMethods.DELETE,
            s3.HttpMethods.HEAD,
          ],
          allowedOrigins: ['http://localhost:3000', 'https://localhost:3000'],
          exposedHeaders: ['ETag'],
        },
      ],
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    // CloudFront Origin Access Control
    const originAccessControl = new cloudfront.CfnOriginAccessControl(this, 'VideoOAC', {
      originAccessControlConfig: {
        description: 'OAC for video streaming',
        name: 'VideoUnderstandingStackVideoOAC09953FB6',
        originAccessControlOriginType: 's3',
        signingBehavior: 'always',
        signingProtocol: 'sigv4',
      },
    });

    // CloudFront Cache Policy for video streaming
    const cachePolicy = new cloudfront.CachePolicy(this, 'VideoCachePolicy', {
      cachePolicyName: `video-cache-policy-${this.region}`,
      defaultTtl: cdk.Duration.days(1),
      maxTtl: cdk.Duration.days(365),
      minTtl: cdk.Duration.seconds(0),
      enableAcceptEncodingBrotli: false,
      enableAcceptEncodingGzip: false,
      headerBehavior: cloudfront.CacheHeaderBehavior.allowList('Range'),
      cookieBehavior: cloudfront.CacheCookieBehavior.none(),
      queryStringBehavior: cloudfront.CacheQueryStringBehavior.none(),
    });

    // CloudFront distribution for video streaming
    const distribution = new cloudfront.Distribution(this, 'VideoDistribution', {
      comment: 'Video streaming distribution for video understanding application',
      defaultBehavior: {
        origin: origins.S3BucketOrigin.withOriginAccessControl(videoBucket, {
          originAccessControlId: originAccessControl.attrId,
        }),
        cachePolicy: cachePolicy,
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        allowedMethods: cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
        cachedMethods: cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
        compress: true,
      },
      httpVersion: cloudfront.HttpVersion.HTTP2,
      enableIpv6: true,
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100,
    });

    // Update bucket policy to allow CloudFront access
    videoBucket.addToResourcePolicy(new iam.PolicyStatement({
      actions: ['s3:GetObject'],
      resources: [videoBucket.arnForObjects('*')],
      principals: [new iam.ServicePrincipal('cloudfront.amazonaws.com')],
      conditions: {
        StringEquals: {
          'AWS:SourceArn': `arn:${this.partition}:cloudfront::${this.account}:distribution/${distribution.distributionId}`,
        },
      },
    }));

    // OpenSearch Serverless encryption policy
    const encryptionPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'VideoEmbeddingsCollectionEncryptionPolicy', {
      name: 'encryptionpolicyvidetionb7b973ac',
      type: 'encryption',
      policy: JSON.stringify({
        Rules: [{
          ResourceType: 'collection',
          Resource: ['collection/video-embeddings']
        }],
        AWSOwnedKey: true
      }),
    });

    // OpenSearch Serverless network policy
    const networkPolicy = new opensearchserverless.CfnSecurityPolicy(this, 'VideoEmbeddingsCollectionNetworkPolicy', {
      name: 'networkpolicyvideoctionb7b973ac',
      type: 'network',
      policy: JSON.stringify([{
        Rules: [{
          ResourceType: 'collection',
          Resource: ['collection/video-embeddings']
        }, {
          ResourceType: 'dashboard',
          Resource: ['collection/video-embeddings']
        }],
        AllowFromPublic: true
      }]),
    });

    // OpenSearch Serverless collection
    const vectorCollection = new opensearchserverless.CfnCollection(this, 'VideoEmbeddingsCollectionVectorCollection', {
      name: 'video-embeddings',
      description: 'Vector collection for video embeddings from Twelve Labs Marengo',
      type: 'VECTORSEARCH',
      standbyReplicas: 'ENABLED',
      tags: [{
        key: 'Name',
        value: 'video-embeddings',
      }, {
        key: 'Type',
        value: 'VectorCollection',
      }],
    });
    vectorCollection.addDependency(encryptionPolicy);
    vectorCollection.addDependency(networkPolicy);

    // IAM managed policy for OpenSearch access
    const aossApiAccessPolicy = new iam.ManagedPolicy(this, 'VideoEmbeddingsCollectionAOSSApiAccessAll', {
      statements: [
        new iam.PolicyStatement({
          actions: ['aoss:APIAccessAll'],
          resources: [vectorCollection.attrArn],
        }),
      ],
    });

    // Lambda execution role
    const lambdaRole = new iam.Role(this, 'VideoProcessingLambdaRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
        aossApiAccessPolicy,
      ],
      inlinePolicies: {
        BedrockAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'bedrock:GetAsyncInvoke',
                'bedrock:InvokeModel',
                'bedrock:InvokeModelWithResponseStream',
                'bedrock:StartAsyncInvoke',
              ],
              resources: [
                'arn:aws:bedrock:*::foundation-model/twelvelabs.*',
                `arn:aws:bedrock:*:${this.account}:async-invoke/*`,
                `arn:aws:bedrock:*:${this.account}:inference-profile/us.twelvelabs.*`,
              ],
            }),
          ],
        }),
        S3Access: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                's3:DeleteObject',
                's3:GetObject',
                's3:PutObject',
              ],
              resources: [videoBucket.arnForObjects('*')],
            }),
            new iam.PolicyStatement({
              actions: ['s3:ListBucket'],
              resources: [videoBucket.bucketArn],
            }),
          ],
        }),
        OpenSearchAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                'aoss:APIAccessAll',
                'aoss:CreateIndex',
                'aoss:DeleteIndex',
              ],
              resources: [vectorCollection.attrArn],
            }),
          ],
        }),
        S3VectorsAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: [
                's3vectors:CreateIndex',
                's3vectors:CreateVectorBucket',
                's3vectors:DeleteIndex',
                's3vectors:DeleteVectorBucket',
                's3vectors:DeleteVectors',
                's3vectors:GetIndex',
                's3vectors:GetVectorBucket',
                's3vectors:GetVectors',
                's3vectors:ListIndexes',
                's3vectors:ListVectorBuckets',
                's3vectors:ListVectors',
                's3vectors:PutVectors',
                's3vectors:QueryVectors',
              ],
              resources: [
                `arn:aws:s3vectors:${this.region}:${this.account}:*`,
                `arn:aws:s3vectors:*:${this.account}:*`,
              ],
            }),
          ],
        }),
        LambdaInvokeAccess: new iam.PolicyDocument({
          statements: [
            new iam.PolicyStatement({
              actions: ['lambda:InvokeFunction'],
              resources: [`arn:aws:lambda:${this.region}:${this.account}:function:*`],
            }),
          ],
        }),
      },
    });

    // OpenSearch data access policy
    const dataAccessPolicy = new opensearchserverless.CfnAccessPolicy(this, 'VideoEmbeddingsCollectionDataAccessPolicy', {
      name: 'dataaccesspolicyvidetionb7b973ac',
      type: 'data',
      policy: JSON.stringify([{
        Rules: [{
          Resource: ['collection/video-embeddings'],
          Permission: [
            'aoss:DescribeCollectionItems',
            'aoss:CreateCollectionItems',
            'aoss:UpdateCollectionItems',
          ],
          ResourceType: 'collection',
        }, {
          Resource: ['index/video-embeddings/*'],
          Permission: [
            'aoss:UpdateIndex',
            'aoss:DescribeIndex',
            'aoss:ReadDocument',
            'aoss:WriteDocument',
            'aoss:CreateIndex',
          ],
          ResourceType: 'index',
        }],
        Principal: [lambdaRole.roleArn],
        Description: '',
      }]),
    });

    // Lambda function
    const videoProcessingFunction = new lambda.Function(this, 'VideoProcessingFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'main.handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../backend'), {
        bundling: {
          image: lambda.Runtime.PYTHON_3_11.bundlingImage,
          local: {
            tryBundle(outputDir: string) {
              try {
                const { execSync } = require('child_process');
                const backendPath = path.join(__dirname, '../../backend');
                
                // Install dependencies locally
                execSync(`pip install -r requirements.txt -t ${outputDir}`, {
                  cwd: backendPath,
                  stdio: 'inherit',
                });
                
                // Copy source files
                execSync(`cp -r ${backendPath}/* ${outputDir}/`, {
                  stdio: 'inherit',
                });
                
                return true;
              } catch (error) {
                console.log('Local bundling failed, falling back to Docker:', error);
                return false;
              }
            },
          },
          command: [
            'bash', '-c',
            'pip install -r requirements.txt -t /asset-output && cp -au . /asset-output'
          ],
        },
      }),
      timeout: cdk.Duration.minutes(15),
      memorySize: 1024,
      role: lambdaRole,
      environment: {
        VIDEO_BUCKET: videoBucket.bucketName,
        OPENSEARCH_ENDPOINT: vectorCollection.attrCollectionEndpoint,
        REGION: this.region,
        AWS_ACCOUNT_ID: this.account,
        CLOUDFRONT_DOMAIN: distribution.domainName,
      },
    });

    // API Gateway
    const api = new apigateway.RestApi(this, 'VideoUnderstandingApi', {
      restApiName: 'Video Understanding API',
      description: 'API for video understanding using Twelve Labs models',
      defaultCorsPreflightOptions: {
        allowOrigins: ['http://localhost:3000'],
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
      },
    });

    const integration = new apigateway.LambdaIntegration(videoProcessingFunction);

    // Add API methods
    api.root.addResource('upload').addMethod('POST', integration);
    api.root.addResource('analyze').addMethod('POST', integration);
    api.root.addResource('embed').addMethod('POST', integration);
    api.root.addResource('search').addMethod('GET', integration);
    api.root.addResource('status').addMethod('GET', integration);
    api.root.addResource('video-url').addMethod('GET', integration);
    api.root.addResource('flush-opensearch').addMethod('POST', integration);

    // Outputs
    new cdk.CfnOutput(this, 'ApiUrl', {
      description: 'API Gateway URL',
      value: api.url,
    });

    new cdk.CfnOutput(this, 'VideoBucketName', {
      description: 'S3 bucket for video storage',
      value: videoBucket.bucketName,
    });

    new cdk.CfnOutput(this, 'OpenSearchEndpoint', {
      description: 'OpenSearch Serverless collection endpoint',
      value: vectorCollection.attrCollectionEndpoint,
    });

    new cdk.CfnOutput(this, 'CloudFrontDomain', {
      description: 'CloudFront distribution domain for video streaming',
      value: distribution.domainName,
    });
  }
}
