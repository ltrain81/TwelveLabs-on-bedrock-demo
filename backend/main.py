import json
import os
import boto3
import base64
from typing import Dict, Any
from botocore.exceptions import ClientError

# Initialize AWS clients
s3_client = boto3.client('s3', region_name=os.environ.get('REGION', 'us-east-1'))
bedrock_client = boto3.client('bedrock-runtime', region_name=os.environ.get('REGION', 'us-east-1'))
s3vectors_client = boto3.client('s3vectors', region_name=os.environ.get('REGION', 'us-east-1'))

# OpenSearch configuration - initialize only when needed
opensearch_client = None

# S3 Vectors configuration
S3_VECTOR_BUCKET = None
S3_VECTOR_INDEX = 'video-embeddings-index'
VECTOR_DIMENSION = 1024

def get_account_id():
    """Get AWS Account ID dynamically"""
    account_id = os.environ.get('AWS_ACCOUNT_ID')
    if not account_id:
        # Get account ID dynamically from AWS STS
        try:
            sts_client = boto3.client('sts', region_name=os.environ.get('REGION', 'us-east-1'))
            account_id = sts_client.get_caller_identity()['Account']
            print(f"Dynamically retrieved AWS Account ID: {account_id}")
        except Exception as e:
            print(f"Error retrieving account ID: {e}")
            raise ValueError("AWS_ACCOUNT_ID environment variable not set and unable to retrieve from STS")
    return account_id

def get_opensearch_client():
    """Initialize OpenSearch client lazily"""
    global opensearch_client
    if opensearch_client is None:
        try:
            print("Initializing OpenSearch client...")
            from opensearchpy import OpenSearch, RequestsHttpConnection, AWSV4SignerAuth
            
            opensearch_endpoint = os.environ.get('OPENSEARCH_ENDPOINT', '').replace('https://', '')
            region = os.environ.get('REGION', 'us-east-1')
            print(f"OpenSearch endpoint: {opensearch_endpoint}, region: {region}")
            
            credentials = boto3.Session().get_credentials()
            # Use AWSV4SignerAuth with 'aoss' service for OpenSearch Serverless
            awsauth = AWSV4SignerAuth(credentials, region, 'aoss')
            print("AWSV4SignerAuth created successfully for aoss service")

            opensearch_client = OpenSearch(
                hosts=[{'host': opensearch_endpoint, 'port': 443}],
                http_auth=awsauth,
                use_ssl=True,
                verify_certs=True,
                connection_class=RequestsHttpConnection
            )
            print("OpenSearch client initialized successfully")
        except Exception as e:
            print(f"OpenSearch client initialization failed: {e}")
            opensearch_client = None
    
    return opensearch_client

def get_or_create_s3_vector_bucket():
    """Get or create S3 Vector bucket and index"""
    global S3_VECTOR_BUCKET
    if S3_VECTOR_BUCKET is None:
        try:
            # Generate unique bucket name
            account_id = get_account_id()
            region = os.environ.get('REGION', 'us-east-1')
            S3_VECTOR_BUCKET = f"video-s3vectors-{account_id}-{region}"
            print(f"Using S3 Vector bucket: {S3_VECTOR_BUCKET}")
            
            # Check if vector bucket exists, create if not
            try:
                # Try to get vector bucket directly
                s3vectors_client.get_vector_bucket(vectorBucketName=S3_VECTOR_BUCKET)
                print(f"S3 Vector bucket {S3_VECTOR_BUCKET} already exists")
            except Exception as e:
                if 'NotFoundException' in str(e) or 'could not be found' in str(e) or 'does not exist' in str(e).lower():
                    print(f"Vector bucket not found. Creating S3 Vector bucket: {S3_VECTOR_BUCKET}")
                    s3vectors_client.create_vector_bucket(vectorBucketName=S3_VECTOR_BUCKET)
                    print(f"S3 Vector bucket {S3_VECTOR_BUCKET} created successfully")
                    
                    # Wait a moment for bucket to be available
                    import time
                    time.sleep(2)
                else:
                    print(f"Error checking S3 Vector bucket: {e}")
                    raise
            
            # Check if vector index exists, create if not
            try:
                # Try to get vector index directly
                s3vectors_client.get_index(
                    vectorBucketName=S3_VECTOR_BUCKET,
                    indexName=S3_VECTOR_INDEX
                )
                print(f"S3 Vector index {S3_VECTOR_INDEX} already exists")
            except Exception as e:
                if 'NotFoundException' in str(e) or 'could not be found' in str(e) or 'does not exist' in str(e).lower():
                    print(f"Vector index not found. Creating S3 Vector index: {S3_VECTOR_INDEX}")
                    s3vectors_client.create_index(
                        vectorBucketName=S3_VECTOR_BUCKET,
                        indexName=S3_VECTOR_INDEX,
                        dataType='float32',
                        dimension=VECTOR_DIMENSION,
                        distanceMetric='cosine'
                    )
                    print(f"S3 Vector index {S3_VECTOR_INDEX} created successfully")
                    
                    # Wait a moment for index to be available
                    import time
                    time.sleep(2)
                else:
                    print(f"Error checking S3 Vector index: {e}")
                    raise
            
        except Exception as e:
            print(f"Error initializing S3 Vector bucket/index: {e}")
            S3_VECTOR_BUCKET = None
            raise
    
    return S3_VECTOR_BUCKET

def store_embeddings_to_s3_vectors(video_id, video_s3_uri, embedding_data_list):
    """Store video embeddings to S3 Vectors"""
    try:
        import time
        start_time = time.time()
        
        bucket_name = get_or_create_s3_vector_bucket()
        if not bucket_name:
            raise Exception("S3 Vector bucket not available")
        
        # Handle both single embedding and list of embeddings
        if not isinstance(embedding_data_list, list):
            embedding_data_list = [embedding_data_list]
        
        vectors = []
        for i, embedding_data in enumerate(embedding_data_list):
            segment_id = f"{video_id}_segment_{i}_{embedding_data.get('startSec', 0)}"
            
            vectors.append({
                "key": segment_id,
                "data": {"float32": embedding_data.get('embedding', [])},
                "metadata": {
                    "videoId": video_id,
                    "videoS3Uri": video_s3_uri,
                    "segmentId": segment_id,
                    "startSec": embedding_data.get('startSec', 0),
                    "endSec": embedding_data.get('endSec', 0),
                    "duration": embedding_data.get('endSec', 0) - embedding_data.get('startSec', 0),
                    "embeddingOption": embedding_data.get('embeddingOption', 'visual-text')
                }
            })
        
        # Store vectors in S3 Vectors
        s3vectors_client.put_vectors(
            vectorBucketName=bucket_name,
            indexName=S3_VECTOR_INDEX,
            vectors=vectors
        )
        
        storage_time = time.time() - start_time
        print(f"S3 Vectors: Stored {len(vectors)} vectors in {storage_time:.3f}s")
        
        return {
            'stored_count': len(vectors),
            'video_id': video_id,
            'storage_time_ms': round(storage_time * 1000, 2)
        }
        
    except Exception as e:
        print(f"Error storing embeddings to S3 Vectors: {e}")
        raise

def search_opensearch(query_embedding, top_k=10):
    """Search OpenSearch for similar embeddings"""
    try:
        import time
        start_time = time.time()
        
        opensearch = get_opensearch_client()
        if not opensearch:
            raise Exception("OpenSearch client not available")
        
        # First check if index exists and get its mapping
        try:
            ensure_vector_index(opensearch)
        except Exception as e:
            if 'index_not_found_exception' in str(e).lower():
                return {
                    'results': [],
                    'total': 0,
                    'search_time_ms': 0,
                    'message': 'No videos indexed yet - upload and process videos with embeddings first'
                }
            raise
        
        search_body = {
            "size": top_k,
            "query": {
                "knn": {
                    "embedding": {
                        "vector": query_embedding,
                        "k": top_k
                    }
                }
            },
            "_source": ["videoId", "videoS3Uri", "segmentId", "startSec", "endSec", "duration", "embeddingOption", "metadata"]
        }
        
        search_response = opensearch.search(
            index='video-embeddings',
            body=search_body
        )
        
        search_time = time.time() - start_time
        
        results = []
        for hit in search_response['hits']['hits']:
            source = hit['_source']
            results.append({
                'videoId': source.get('videoId', 'unknown'),
                'videoS3Uri': source.get('videoS3Uri', ''),
                'segmentId': source.get('segmentId', ''),
                'startSec': source.get('startSec', 0),
                'endSec': source.get('endSec', 0),
                'duration': source.get('duration', 0),
                'embeddingOption': source.get('embeddingOption', 'visual-text'),
                'score': hit['_score'],
                'metadata': source.get('metadata', {})
            })
        
        print(f"OpenSearch: Found {len(results)} results in {search_time:.3f}s")
        
        return {
            'results': results,
            'total': search_response['hits']['total']['value'],
            'search_time_ms': round(search_time * 1000, 2)
        }
        
    except Exception as e:
        if 'index_not_found_exception' in str(e).lower():
            return {
                'results': [],
                'total': 0,
                'search_time_ms': 0,
                'message': 'No videos indexed yet - upload and process videos with embeddings first'
            }
        print(f"Error searching OpenSearch: {e}")
        raise

def search_s3_vectors(query_embedding, top_k=10):
    """Search S3 Vectors for similar embeddings"""
    try:
        import time
        start_time = time.time()
        
        bucket_name = get_or_create_s3_vector_bucket()
        if not bucket_name:
            raise Exception("S3 Vector bucket not available")
        
        # Query the S3 Vector index
        response = s3vectors_client.query_vectors(
            vectorBucketName=bucket_name,
            indexName=S3_VECTOR_INDEX,
            queryVector={"float32": query_embedding},
            topK=top_k,
            returnDistance=True,
            returnMetadata=True
        )
        
        search_time = time.time() - start_time
        
        # Transform results to match OpenSearch format
        results = []
        for vector in response.get('vectors', []):
            metadata = vector.get('metadata', {})
            results.append({
                'videoId': metadata.get('videoId', 'unknown'),
                'videoS3Uri': metadata.get('videoS3Uri', ''),
                'segmentId': metadata.get('segmentId', ''),
                'startSec': metadata.get('startSec', 0),
                'endSec': metadata.get('endSec', 0),
                'duration': metadata.get('duration', 0),
                'embeddingOption': metadata.get('embeddingOption', 'visual-text'),
                'score': vector.get('distance', 0),  # Note: distance, not similarity score
                'metadata': metadata
            })
        
        print(f"S3 Vectors: Found {len(results)} results in {search_time:.3f}s")
        
        return {
            'results': results,
            'total': len(results),
            'search_time_ms': round(search_time * 1000, 2)
        }
        
    except Exception as e:
        print(f"Error searching S3 Vectors: {e}")
        raise

def ensure_vector_index(opensearch_client):
    """Ensure the vector index exists with proper mapping"""
    index_name = 'video-embeddings'
    
    try:
        # Check if index exists
        if opensearch_client.indices.exists(index=index_name):
            print(f"Index {index_name} already exists")
            # Check current mapping
            try:
                mapping = opensearch_client.indices.get_mapping(index=index_name)
                print(f"Current index mapping: {json.dumps(mapping, indent=2)}")
                
                # Check if embedding field is knn_vector
                properties = mapping.get(index_name, {}).get('mappings', {}).get('properties', {})
                embedding_field = properties.get('embedding', {})
                if embedding_field.get('type') != 'knn_vector':
                    print(f"WARNING: embedding field type is {embedding_field.get('type')}, not knn_vector")
                    print("Deleting and recreating index with correct mapping...")
                    opensearch_client.indices.delete(index=index_name)
                else:
                    print("Index has correct knn_vector mapping")
                    return
            except Exception as e:
                print(f"Error checking mapping: {e}")
                return
        
        # Create index with knn_vector mapping and temporal fields
        index_body = {
            "settings": {
                "index": {
                    "knn": True,
                    "knn.algo_param.ef_search": 512
                }
            },
            "mappings": {
                "properties": {
                    "videoId": {
                        "type": "keyword"
                    },
                    "videoS3Uri": {
                        "type": "keyword"
                    },
                    "segmentId": {
                        "type": "keyword"
                    },
                    "startSec": {
                        "type": "float"
                    },
                    "endSec": {
                        "type": "float"
                    },
                    "duration": {
                        "type": "float"
                    },
                    "embeddingOption": {
                        "type": "keyword"
                    },
                    "embedding": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "nmslib",
                            "parameters": {
                                "ef_construction": 512,
                                "m": 16
                            }
                        }
                    },
                    "metadata": {
                        "type": "object"
                    }
                }
            }
        }
        
        opensearch_client.indices.create(index=index_name, body=index_body)
        print(f"Created index {index_name} with knn_vector mapping")
        
    except Exception as e:
        print(f"Error ensuring vector index: {e}")
        raise

def store_embeddings_dual(bedrock_response, embedding_data_list):
    """Store video embeddings to both OpenSearch and S3 Vectors for comparison"""
    print("🗂️ === DUAL EMBEDDING STORAGE DEBUG START ===")
    print(f"📡 bedrock_response keys: {list(bedrock_response.keys()) if isinstance(bedrock_response, dict) else 'Not a dict'}")
    print(f"📡 bedrock_response content: {bedrock_response}")
    print(f"📊 embedding_data_list length: {len(embedding_data_list) if isinstance(embedding_data_list, list) else 'Not a list'}")
    
    # Initialize storage results
    opensearch_result = None
    s3vectors_result = None
    
    # Store to OpenSearch
    try:
        opensearch_result = store_embeddings_to_opensearch(bedrock_response, embedding_data_list)
    except Exception as e:
        print(f"OpenSearch storage failed: {e}")
        opensearch_result = {'error': str(e)}
    
    # Extract video metadata for S3 Vectors storage
    video_id, video_s3_uri = extract_video_metadata(bedrock_response)
    
    # Store to S3 Vectors
    try:
        s3vectors_result = store_embeddings_to_s3_vectors(video_id, video_s3_uri, embedding_data_list)
    except Exception as e:
        print(f"S3 Vectors storage failed: {e}")
        s3vectors_result = {'error': str(e)}
    
    print("🗂️ === DUAL EMBEDDING STORAGE DEBUG END ===")
    
    return {
        'opensearch': opensearch_result,
        's3vectors': s3vectors_result,
        'video_id': video_id
    }

def extract_video_metadata(bedrock_response):
    """Extract video metadata from bedrock response"""
    video_s3_uri = ''
    video_id = 'unknown'
    
    # Method 1: Try to extract from original request (if present)
    model_input = bedrock_response.get('modelInput', {})
    media_source = model_input.get('mediaSource', {})
    s3_location = media_source.get('s3Location', {})
    video_s3_uri = s3_location.get('uri', '')
    
    print(f"🔍 DEBUG: Method 1 - modelInput approach: '{video_s3_uri}'")
    
    # Method 2: Extract from output path structure if Method 1 fails
    if not video_s3_uri:
        output_data_config = bedrock_response.get('outputDataConfig', {})
        s3_output_config = output_data_config.get('s3OutputDataConfig', {})
        output_s3_uri = s3_output_config.get('s3Uri', '')
        
        print(f"🔍 DEBUG: Method 2 - output_s3_uri: '{output_s3_uri}'")
        
        # The output path structure is: s3://bucket/embeddings/{video_id}/
        # We can extract video_id from this path and reconstruct the original video S3 URI
        if output_s3_uri and '/embeddings/' in output_s3_uri:
            path_parts = output_s3_uri.replace('s3://', '').split('/')
            bucket_name = path_parts[0]
            
            # Find the video_id from the path after /embeddings/
            try:
                embeddings_index = path_parts.index('embeddings')
                if embeddings_index + 1 < len(path_parts):
                    extracted_folder_name = path_parts[embeddings_index + 1]
                    
                    # The folder name is the video filename without extension
                    # We need to reconstruct the full video filename
                    video_filename = f"{extracted_folder_name}.mp4"  # Assume mp4 for now
                    
                    # Reconstruct the original video S3 URI
                    video_s3_uri = f"s3://{bucket_name}/videos/{video_filename}"
                    video_id = extracted_folder_name  # Keep video_id without extension
                    
                    print(f"🔍 DEBUG: Method 2 success - folder name: '{extracted_folder_name}', video_id: '{video_id}', reconstructed S3 URI: '{video_s3_uri}'")
                else:
                    print(f"🔍 DEBUG: Method 2 failed - could not find video_id in path")
            except (ValueError, IndexError) as e:
                print(f"🔍 DEBUG: Method 2 failed - error parsing output path: {e}")
        
    # If video_id is still unknown, try to extract from S3 URI as fallback
    if video_id == 'unknown' and video_s3_uri and video_s3_uri.startswith('s3://'):
        # Parse s3://bucket/path/to/file.mp4 -> file.mp4
        extracted_id = video_s3_uri.split('/')[-1]
        # Remove file extension for cleaner ID
        if '.' in extracted_id:
            video_id = extracted_id.rsplit('.', 1)[0]
        else:
            video_id = extracted_id
        print(f"🔍 DEBUG: Fallback extraction from S3 URI - video_id: '{video_id}'")
    
    if video_id == 'unknown' or not video_s3_uri:
        print(f"⚠️ WARNING: Could not extract proper video metadata - video_id: '{video_id}', S3 URI: '{video_s3_uri}'")
    
    return video_id, video_s3_uri

def store_embeddings_to_opensearch(bedrock_response, embedding_data_list):
    """Store video embeddings with temporal segments to OpenSearch for similarity search"""
    print("🗂️ === OPENSEARCH EMBEDDING STORAGE START ===")
    
    opensearch = get_opensearch_client()
    if not opensearch:
        raise Exception("OpenSearch client not available")
    
    # ALWAYS ensure index exists with proper mapping BEFORE storing documents
    ensure_vector_index(opensearch)
    
    # Extract video metadata using shared function
    video_id, video_s3_uri = extract_video_metadata(bedrock_response)
    
    import time
    start_time = time.time()
    
    print(f"🗂️ Processing OpenSearch storage for video: {video_id}, S3 URI: {video_s3_uri}")
    
    stored_count = 0
    responses = []
    
    # Handle both single embedding and list of embeddings
    if not isinstance(embedding_data_list, list):
        embedding_data_list = [embedding_data_list]
    
    # Store each temporal segment as a separate document
    for i, embedding_data in enumerate(embedding_data_list):
        # Create unique document ID for each segment
        segment_id = f"{video_id}_segment_{i}_{embedding_data.get('startSec', 0)}"
        
        # Prepare document for OpenSearch
        document = {
            'videoId': video_id,
            'videoS3Uri': video_s3_uri,
            'segmentId': segment_id,
            'startSec': embedding_data.get('startSec', 0),
            'endSec': embedding_data.get('endSec', 0),
            'duration': embedding_data.get('endSec', 0) - embedding_data.get('startSec', 0),
            'embedding': embedding_data.get('embedding', []),
            'embeddingOption': embedding_data.get('embeddingOption', 'visual-text'),
            'metadata': {
                'modelId': bedrock_response.get('modelId', ''),
                'invocationArn': bedrock_response.get('invocationArn', ''),
                'timestamp': bedrock_response.get('endTime', ''),
                'segmentIndex': i,
                'totalSegments': len(embedding_data_list)
            }
        }
        
        print(f"Storing segment {i+1}/{len(embedding_data_list)}: {embedding_data.get('startSec', 0)}-{embedding_data.get('endSec', 0)}s, embedding length: {len(document['embedding'])}, type: {document['embeddingOption']}")
        
        # Index the document without explicit ID (OpenSearch Serverless doesn't support it)
        response = opensearch.index(
            index='video-embeddings',
            body=document
        )
        
        responses.append(response)
        stored_count += 1
    
    storage_time = time.time() - start_time
    print(f"OpenSearch: Stored {stored_count} segments in {storage_time:.3f}s")
    # Return simplified response to avoid Lambda 413 error with large responses
    return {
        'stored_count': stored_count, 
        'video_id': video_id,
        'storage_time_ms': round(storage_time * 1000, 2)
    }

def handle_flush_opensearch(event: Dict[str, Any], cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Flush/delete all documents from the OpenSearch vector index"""
    try:
        print("🗑️ Starting OpenSearch index flush...")
        
        opensearch = get_opensearch_client()
        if not opensearch:
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': 'OpenSearch client not available'})
            }
        
        index_name = 'video-embeddings'
        
        # Check if index exists
        if not opensearch.indices.exists(index=index_name):
            print(f"Index {index_name} does not exist")
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'message': f'Index {index_name} does not exist - nothing to flush',
                    'documents_deleted': 0
                })
            }
        
        # Get current document count
        try:
            count_response = opensearch.count(index=index_name)
            total_docs = count_response.get('count', 0)
            print(f"Found {total_docs} documents to delete")
        except Exception as e:
            print(f"Could not get document count: {e}")
            total_docs = "unknown"
        
        # Delete all documents using delete_by_query
        delete_response = opensearch.delete_by_query(
            index=index_name,
            body={
                "query": {
                    "match_all": {}
                }
            },
            refresh=True  # Refresh the index after deletion
        )
        
        deleted_count = delete_response.get('deleted', 0)
        print(f"Successfully deleted {deleted_count} documents from {index_name}")
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'message': f'Successfully flushed OpenSearch index {index_name}',
                'documents_before': total_docs,
                'documents_deleted': deleted_count,
                'took_ms': delete_response.get('took', 0)
            })
        }
        
    except Exception as e:
        print(f"Error flushing OpenSearch: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Failed to flush OpenSearch: {str(e)}'})
        }

def process_analysis_async(event: Dict[str, Any]) -> Dict[str, Any]:
    """Process video analysis asynchronously (called via direct Lambda invoke)"""
    try:
        print("=== ASYNC ANALYSIS PROCESSING START ===")
        
        analysis_job_id = event.get('analysisJobId')
        s3_uri = event.get('s3Uri')
        prompt = event.get('prompt')
        video_id = event.get('videoId')
        bucket_name = event.get('bucketName')
        
        print(f"Processing async analysis - Job ID: {analysis_job_id}")
        print(f"S3 URI: {s3_uri}, Video ID: {video_id}")
        print(f"Prompt length: {len(prompt) if prompt else 0}")
        
        if not all([analysis_job_id, s3_uri, prompt, bucket_name]):
            raise ValueError("Missing required parameters for async analysis processing")
        
        import time
        start_time = time.time()
        
        # Use invoke_model for Pegasus
        request_body = {
            "inputPrompt": prompt,
            "mediaSource": {
                "s3Location": {
                    "uri": s3_uri,
                    "bucketOwner": get_account_id()
                }
            },
            "temperature": 0.2,
            "maxOutputTokens": 4096
        }
        
        print(f"Calling Bedrock Pegasus model with request: {json.dumps(request_body, indent=2)}")
        
        response = bedrock_client.invoke_model(
            modelId='us.twelvelabs.pegasus-1-2-v1:0',
            body=json.dumps(request_body),
            contentType='application/json'
        )
        
        print(f"Bedrock response status: {response['ResponseMetadata']['HTTPStatusCode']}")
        response_body = json.loads(response['body'].read())
        print(f"Analysis completed successfully. Response keys: {list(response_body.keys())}")
        
        # Store the analysis result in S3
        analysis_result = {
            'jobId': analysis_job_id,
            'status': 'Completed',
            'videoId': video_id,
            's3Uri': s3_uri,
            'prompt': prompt,
            'analysis': response_body.get('message', ''),
            'finishReason': response_body.get('finishReason', ''),
            'endTime': time.time(),
            'completedTime': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            'processingTimeSeconds': time.time() - start_time
        }
        
        # Store completed result
        result_key = f"analysis/{analysis_job_id}/result.json"
        s3_client.put_object(
            Bucket=bucket_name,
            Key=result_key,
            Body=json.dumps(analysis_result, indent=2),
            ContentType='application/json'
        )
        
        # Update job status
        job_key = f"analysis/{analysis_job_id}/job_info.json"
        job_info = {
            'jobId': analysis_job_id,
            'status': 'Completed',
            'videoId': video_id,
            's3Uri': s3_uri,
            'prompt': prompt,
            'endTime': time.time(),
            'completedTime': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()),
            'processingTimeSeconds': time.time() - start_time
        }
        s3_client.put_object(
            Bucket=bucket_name,
            Key=job_key,
            Body=json.dumps(job_info, indent=2),
            ContentType='application/json'
        )
        
        print(f"Analysis completed and stored at s3://{bucket_name}/{result_key}")
        print(f"Processing time: {time.time() - start_time:.2f} seconds")
        print("=== ASYNC ANALYSIS PROCESSING END ===")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'jobId': analysis_job_id,
                'status': 'Completed',
                'processingTime': time.time() - start_time
            })
        }
        
    except Exception as e:
        print(f"Async analysis processing failed: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        
        # Update job status to failed if we have the required info
        if 'analysis_job_id' in locals() and 'bucket_name' in locals():
            try:
                job_key = f"analysis/{analysis_job_id}/job_info.json"
                failed_job_info = {
                    'jobId': analysis_job_id,
                    'status': 'Failed',
                    'error': str(e),
                    'endTime': time.time(),
                    'failedTime': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
                }
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=job_key,
                    Body=json.dumps(failed_job_info, indent=2),
                    ContentType='application/json'
                )
                print(f"Updated job status to failed in S3")
            except Exception as update_error:
                print(f"Failed to update job status: {update_error}")
        
        print("=== ASYNC ANALYSIS PROCESSING END (ERROR) ===")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'jobId': locals().get('analysis_job_id', 'unknown')
            })
        }

def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Main Lambda handler for video understanding API"""
    
    # Check if this is an async processing request (direct Lambda invoke, not API Gateway)
    if 'action' in event and event.get('action') == 'process_analysis':
        print("Processing async analysis request")
        return process_analysis_async(event)
    
    print(f"Received event: {event.get('httpMethod')} {event.get('path')}")
    event_body = event.get('body', 'No body')
    if event_body and event_body != 'No body':
        print(f"Event body preview: {event_body[:200]}...")
    else:
        print("Event body: None or empty")
    print(f"Context: {context.function_name} - {context.aws_request_id}")
    
    # CORS headers
    cors_headers = {
        'Access-Control-Allow-Origin': os.environ.get('CORS_ORIGIN', 'http://localhost:3000'),
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, X-Amz-Date, Authorization, X-Api-Key, X-Amz-Security-Token',
        'Content-Type': 'application/json'
    }
    
    try:
        path = event.get('path', '')
        method = event.get('httpMethod', '')
        
        # Handle preflight OPTIONS requests
        if method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': ''
            }
        
        print(f"Processing request: {method} {path}")
        
        if path == '/upload' and method == 'POST':
            print("Routing to handle_upload")
            return handle_upload(event, cors_headers)
        elif path == '/analyze' and method == 'POST':
            print("Routing to handle_analyze")
            return handle_analyze(event, cors_headers, context)
        elif path == '/embed' and method == 'POST':
            print("Routing to handle_embed")
            return handle_embed(event, cors_headers)
        elif path == '/status' and method == 'GET':
            print("Routing to handle_status")
            return handle_status(event, cors_headers)
        elif path == '/search' and method == 'GET':
            print("Routing to handle_search")
            return handle_search(event, cors_headers)
        elif path == '/video-url' and method == 'GET':
            print("Routing to handle_video_url")
            return handle_video_url(event, cors_headers)
        elif path == '/flush-opensearch' and method == 'POST':
            print("Routing to handle_flush_opensearch")
            return handle_flush_opensearch(event, cors_headers)
        else:
            print(f"No route found for {method} {path}")
            return {
                'statusCode': 404,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Not found'})
            }
    
    except Exception as e:
        print(f"CRITICAL ERROR in main handler: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Internal server error: {str(e)}'})
        }

def handle_video_url(event: Dict[str, Any], cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Generate presigned URL for video playback"""
    try:
        print(f"🎬 === VIDEO URL REQUEST START ===")
        print(f"📡 Request event: {json.dumps(event, indent=2)}")
        print(f"🔒 CORS headers: {cors_headers}")
        
        query_params = event.get('queryStringParameters', {}) or {}
        video_s3_uri = query_params.get('videoS3Uri')
        
        print(f"📹 Video S3 URI requested: {video_s3_uri}")
        print(f"🔍 All query parameters: {query_params}")
        
        if not video_s3_uri:
            print("❌ ERROR: videoS3Uri parameter is required but not provided")
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'videoS3Uri parameter is required'})
            }
        
        # Parse S3 URI to get bucket and key
        if not video_s3_uri.startswith('s3://'):
            print(f"❌ ERROR: Invalid S3 URI format: {video_s3_uri}")
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Invalid S3 URI format'})
            }
        
        # Remove s3:// prefix and split bucket/key
        s3_path = video_s3_uri[5:]  # Remove 's3://'
        parts = s3_path.split('/', 1)
        print(f"🔗 S3 path after removing s3://: {s3_path}")
        print(f"🪣 Parsed parts: {parts}")
        
        if len(parts) != 2:
            print(f"❌ ERROR: Invalid S3 URI format - could not split bucket/key: {parts}")
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Invalid S3 URI format'})
            }
        
        bucket_name, object_key = parts
        print(f"🪣 Bucket: {bucket_name}")
        print(f"🔑 Object key: {object_key}")
        
        # Check if object exists before generating presigned URL
        try:
            print(f"🔍 Checking if object exists in S3...")
            s3_client.head_object(Bucket=bucket_name, Key=object_key)
            print(f"✅ Object exists in S3: {bucket_name}/{object_key}")
        except Exception as head_error:
            print(f"❌ Object does not exist in S3: {head_error}")
            return {
                'statusCode': 404,
                'headers': cors_headers,
                'body': json.dumps({'error': f'Video file not found in S3: {object_key}'})
            }
        
        # Generate presigned URL for video access (valid for 1 hour)
        print(f"🔗 Generating presigned URL for {bucket_name}/{object_key}")
        presigned_url = s3_client.generate_presigned_url(
            'get_object',
            Params={'Bucket': bucket_name, 'Key': object_key},
            ExpiresIn=3600
        )
        
        print(f"✅ Generated presigned URL successfully for {bucket_name}/{object_key}")
        print(f"🌐 Presigned URL length: {len(presigned_url)}")
        print(f"🌐 Presigned URL preview: {presigned_url[:100]}...")
        response_data = {
            'presignedUrl': presigned_url,
            'videoS3Uri': video_s3_uri,
            'bucket': bucket_name,
            'key': object_key
        }
        
        print(f"✅ Returning successful response with data: {json.dumps(response_data, indent=2)}")
        print(f"🎬 === VIDEO URL REQUEST END ===")
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps(response_data)
        }
    
    except Exception as e:
        print(f"❌ ERROR in handle_video_url: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Full traceback: {traceback.format_exc()}")
        print(f"🎬 === VIDEO URL REQUEST END (ERROR) ===")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }

def handle_upload(event: Dict[str, Any], cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Handle video upload to S3"""
    try:
        body = json.loads(event.get('body', '{}'))
        filename = body.get('filename')
        content_type = body.get('contentType', 'video/mp4')
        
        if not filename:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Filename is required'})
            }
        
        bucket_name = os.environ.get('VIDEO_BUCKET')
        key = f"videos/{filename}"
        
        # Generate presigned POST instead of PUT
        presigned_post = s3_client.generate_presigned_post(
            Bucket=bucket_name,
            Key=key,
            Fields={'Content-Type': content_type},
            Conditions=[
                {'Content-Type': content_type},
                ['content-length-range', 1, 2147483648]  # 1 byte to 2GB
            ],
            ExpiresIn=3600
        )
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'uploadUrl': presigned_post['url'],
                'fields': presigned_post['fields'],
                'key': key,
                'bucket': bucket_name
            })
        }
    
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }

def wait_for_s3_object(s3_uri: str, max_wait_seconds: int = 30) -> bool:
    """Wait for S3 object to be available with exponential backoff"""
    if not s3_uri.startswith('s3://'):
        print(f"Invalid S3 URI format: {s3_uri}")
        return False
    
    # Parse S3 URI
    s3_path = s3_uri[5:]  # Remove 's3://'
    parts = s3_path.split('/', 1)
    if len(parts) != 2:
        print(f"Invalid S3 URI format: {s3_uri}")
        return False
    
    bucket_name, object_key = parts
    print(f"Checking S3 object existence: bucket={bucket_name}, key={object_key}")
    
    import time
    wait_time = 1  # Start with 1 second
    total_waited = 0
    
    while total_waited < max_wait_seconds:
        try:
            response = s3_client.head_object(Bucket=bucket_name, Key=object_key)
            file_size = response.get('ContentLength', 0)
            print(f"S3 object found! Size: {file_size} bytes, waited {total_waited}s")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code')
            if error_code == 'NoSuchKey':
                print(f"S3 object not found yet, waited {total_waited}s, retrying in {wait_time}s...")
                time.sleep(wait_time)
                total_waited += wait_time
                wait_time = min(wait_time * 1.5, 5)  # Exponential backoff, max 5s
            else:
                print(f"S3 error checking object: {error_code} - {e}")
                return False
        except Exception as e:
            print(f"Unexpected error checking S3 object: {e}")
            return False
    
    print(f"S3 object not found after waiting {max_wait_seconds} seconds")
    return False

def handle_analysis_status(analysis_job_id: str, cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Check status of Pegasus analysis job and retrieve results from S3"""
    try:
        print(f"Checking analysis status for job: {analysis_job_id}")
        
        bucket_name = os.environ.get('VIDEO_BUCKET')
        job_key = f"analysis/{analysis_job_id}/job_info.json"
        result_key = f"analysis/{analysis_job_id}/result.json"
        
        # First, check if job info exists
        try:
            job_response = s3_client.get_object(Bucket=bucket_name, Key=job_key)
            job_info = json.loads(job_response['Body'].read())
            print(f"Found job info: {job_info.get('status', 'Unknown')}")
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                print(f"Analysis job {analysis_job_id} not found")
                return {
                    'statusCode': 404,
                    'headers': cors_headers,
                    'body': json.dumps({'error': f'Analysis job {analysis_job_id} not found'})
                }
            raise
        
        job_status = job_info.get('status', 'Unknown')
        
        if job_status == 'Completed':
            # Try to get the analysis result
            try:
                result_response = s3_client.get_object(Bucket=bucket_name, Key=result_key)
                result_data = json.loads(result_response['Body'].read())
                print(f"Retrieved analysis result for job {analysis_job_id}")
                
                return {
                    'statusCode': 200,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'status': 'Completed',
                        'jobId': analysis_job_id,
                        'videoId': result_data.get('videoId', 'unknown'),
                        'analysis': result_data.get('analysis', ''),
                        'finishReason': result_data.get('finishReason', ''),
                        'prompt': result_data.get('prompt', ''),
                        'processingTime': result_data.get('processingTimeSeconds', 0),
                        'completedTime': result_data.get('completedTime', ''),
                        'message': 'Analysis completed successfully'
                    })
                }
                
            except ClientError as e:
                if e.response.get('Error', {}).get('Code') == 'NoSuchKey':
                    print(f"Result file not found for completed job {analysis_job_id}")
                    return {
                        'statusCode': 200,
                        'headers': cors_headers,
                        'body': json.dumps({
                            'status': 'Completed',
                            'message': 'Analysis completed but result file not found',
                            'jobId': analysis_job_id
                        })
                    }
                raise
                
        elif job_status == 'Failed':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'status': 'Failed',
                    'jobId': analysis_job_id,
                    'error': job_info.get('error', 'Analysis failed'),
                    'message': 'Analysis failed'
                })
            }
        
        else:  # InProgress or other status
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': json.dumps({
                    'status': job_status,
                    'jobId': analysis_job_id,
                    'message': f'Analysis is {job_status.lower()}',
                    'videoId': job_info.get('videoId', 'unknown'),
                    'submitTime': job_info.get('submitTime', '')
                })
            }
            
    except Exception as e:
        print(f"Error checking analysis status: {e}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Failed to check analysis status: {str(e)}'})
        }

def handle_analyze(event: Dict[str, Any], cors_headers: Dict[str, str], context: Any) -> Dict[str, Any]:
    """Handle video analysis using Twelve Labs Pegasus - start analysis and return job ID"""
    try:
        print("Starting video analysis...")
        body = json.loads(event.get('body', '{}'))
        s3_uri = body.get('s3Uri')
        prompt = body.get('prompt', 'Analyze this video and provide a detailed description')
        video_id = body.get('videoId', 'unknown')
        
        print(f"Analysis request - S3 URI: {s3_uri}, Video ID: {video_id}, Prompt length: {len(prompt)}")
        
        if not s3_uri:
            print("ERROR: S3 URI is required but not provided")
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'S3 URI is required'})
            }
        
        # Wait for S3 object to be available
        if not wait_for_s3_object(s3_uri, max_wait_seconds=30):
            return {
                'statusCode': 404,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Video file not found in S3. Please ensure the upload completed successfully.'})
            }
        
        # Generate unique analysis job ID
        import uuid
        import time
        analysis_job_id = f"analysis_{int(time.time())}_{str(uuid.uuid4())[:8]}"
        
        # Create analysis job info to store in S3
        job_info = {
            'jobId': analysis_job_id,
            'status': 'InProgress',
            'videoId': video_id,
            's3Uri': s3_uri,
            'prompt': prompt,
            'startTime': time.time(),
            'submitTime': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
        }
        
        # Store job info in S3 first
        bucket_name = os.environ.get('VIDEO_BUCKET')
        job_key = f"analysis/{analysis_job_id}/job_info.json"
        
        try:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=job_key,
                Body=json.dumps(job_info, indent=2),
                ContentType='application/json'
            )
            print(f"Stored analysis job info at s3://{bucket_name}/{job_key}")
        except Exception as e:
            print(f"Failed to store job info: {e}")
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': f'Failed to initialize analysis job: {str(e)}'})
            }
        
        # Invoke Lambda asynchronously to process the analysis
        try:
            lambda_client = boto3.client('lambda', region_name=os.environ.get('REGION', 'us-east-1'))
            function_name = os.environ.get('LAMBDA_FUNCTION_NAME') or context.function_name
            
            # Create payload for async processing
            async_payload = {
                'action': 'process_analysis',  # Special action for async processing
                'analysisJobId': analysis_job_id,
                's3Uri': s3_uri,
                'prompt': prompt,
                'videoId': video_id,
                'bucketName': bucket_name
            }
            
            print(f"Invoking Lambda function asynchronously for job {analysis_job_id}")
            print(f"Function name: {function_name}")
            print(f"Async payload: {json.dumps(async_payload, indent=2)}")
            
            # Invoke Lambda asynchronously (Event invocation type)
            lambda_client.invoke(
                FunctionName=function_name,
                InvocationType='Event',  # Async invocation
                Payload=json.dumps(async_payload)
            )
            
            print(f"Lambda function invoked asynchronously for analysis job {analysis_job_id}")
            
        except Exception as e:
            print(f"Failed to invoke Lambda asynchronously: {e}")
            # Update job status to failed
            job_info.update({
                'status': 'Failed',
                'error': f'Failed to start async processing: {str(e)}',
                'endTime': time.time(),
                'failedTime': time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())
            })
            s3_client.put_object(
                Bucket=bucket_name,
                Key=job_key,
                Body=json.dumps(job_info, indent=2),
                ContentType='application/json'
            )
            
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': f'Failed to start analysis: {str(e)}'})
            }
        
        # Return job ID immediately for status checking
        return {
            'statusCode': 202,
            'headers': cors_headers,
            'body': json.dumps({
                'analysisJobId': analysis_job_id,
                'status': 'processing',
                'message': 'Analysis started successfully. Use /status endpoint to check progress.',
                'videoId': video_id
            })
        }
    
    except json.JSONDecodeError as e:
        print(f"JSON decode error in analyze: {e}")
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Invalid JSON in request body: {str(e)}'})
        }
    except ClientError as e:
        print(f"AWS ClientError in analyze: {e}")
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        print(f"Error code: {error_code}, Message: {error_message}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'AWS Error ({error_code}): {error_message}'})
        }
    except Exception as e:
        print(f"Unexpected error in analyze: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Analysis failed: {str(e)}'})
        }

def handle_embed(event: Dict[str, Any], cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Handle video embedding generation using Twelve Labs Marengo (async)"""
    try:
        print("Starting embedding generation...")
        body = json.loads(event.get('body', '{}'))
        s3_uri = body.get('s3Uri')
        video_id = body.get('videoId')
        
        print(f"Embedding request - S3 URI: {s3_uri}, Video ID: {video_id}")
        
        if not s3_uri or not video_id:
            print(f"ERROR: Missing required parameters - S3 URI: {bool(s3_uri)}, Video ID: {bool(video_id)}")
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'S3 URI and video ID are required'})
            }
        
        # Wait for S3 object to be available
        if not wait_for_s3_object(s3_uri, max_wait_seconds=45):
            return {
                'statusCode': 404,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Video file not found in S3. Please ensure the upload completed successfully.'})
            }
        
        # Use async invoke for Marengo with temporal segmentation
        model_input = {
            "inputType": "video",
            "mediaSource": {
                "s3Location": {
                    "uri": s3_uri,
                    "bucketOwner": get_account_id()
                }
            },
            "useFixedLengthSec": 10,  # 10-second segments for better temporal granularity
            "embeddingOption": ["visual-text", "audio"],  # Get both visual and audio embeddings
            "minClipSec": 2  # Minimum clip duration
        }
        
        print(f"Calling Bedrock Marengo model with input: {json.dumps(model_input, indent=2)}")
        
        # Create a unique embedding folder that includes the video_id for later retrieval
        # Clean the video_id to remove path prefixes but keep the filename with extension
        clean_video_id = video_id
        if '/' in clean_video_id:
            clean_video_id = clean_video_id.split('/')[-1]  # Remove path prefix like "videos/"
        
        # For the safe folder name, remove extension to avoid confusion
        safe_video_id = clean_video_id
        if '.' in safe_video_id:
            safe_video_id = safe_video_id.rsplit('.', 1)[0]  # Remove extension for folder name
        safe_video_id = safe_video_id.replace('/', '_').replace(' ', '_')  # Make filesystem safe
        
        print(f"🔍 DEBUG: Original video_id: '{video_id}', clean_video_id: '{clean_video_id}', safe_video_id: '{safe_video_id}'")
        response = bedrock_client.start_async_invoke(
            modelId='twelvelabs.marengo-embed-2-7-v1:0',
            modelInput=model_input,
            outputDataConfig={
                's3OutputDataConfig': {
                    's3Uri': f"s3://{os.environ.get('VIDEO_BUCKET')}/embeddings/{safe_video_id}/"
                }
            }
        )
        
        print(f"Bedrock async invoke response: {json.dumps(response, indent=2, default=str)}")
        
        invocation_arn = response.get('invocationArn')
        print(f"Successfully started embedding generation with ARN: {invocation_arn}")
        
        return {
            'statusCode': 202,
            'headers': cors_headers,
            'body': json.dumps({
                'invocationArn': invocation_arn,
                'status': 'processing',
                'message': 'Embedding generation started'
            })
        }
    
    except json.JSONDecodeError as e:
        print(f"JSON decode error in embed: {e}")
        return {
            'statusCode': 400,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Invalid JSON in request body: {str(e)}'})
        }
    except ClientError as e:
        print(f"AWS ClientError in embed: {e}")
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        print(f"Error code: {error_code}, Message: {error_message}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'AWS Error ({error_code}): {error_message}'})
        }
    except Exception as e:
        print(f"Unexpected error in embed: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Embedding generation failed: {str(e)}'})
        }

def handle_status(event: Dict[str, Any], cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Check status of async invocation OR analysis job and retrieve results"""
    try:
        query_params = event.get('queryStringParameters', {}) or {}
        invocation_arn = query_params.get('invocationArn')
        analysis_job_id = query_params.get('analysisJobId')
        
        print(f"Status check request - ARN: {invocation_arn}, Analysis Job ID: {analysis_job_id}")
        
        # Handle analysis job status check
        if analysis_job_id:
            return handle_analysis_status(analysis_job_id, cors_headers)
        
        # Handle embedding status check (existing functionality)
        if not invocation_arn:
            print("ERROR: Neither invocation ARN nor analysis job ID provided")
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Either invocationArn or analysisJobId parameter is required'})
            }
        
        # Get invocation status
        print("Calling bedrock_client.get_async_invoke...")
        response = bedrock_client.get_async_invoke(invocationArn=invocation_arn)
        
        status = response.get('status')
        print(f"Bedrock response status: {status}")
        
        if status == 'Completed':
            # Get the output S3 URI from Bedrock response
            output_data_config = response.get('outputDataConfig', {})
            s3_output_config = output_data_config.get('s3OutputDataConfig', {})
            output_s3_uri = s3_output_config.get('s3Uri')
            
            if output_s3_uri:
                # Bedrock creates: s3://bucket/embeddings/{invocationId}
                # The actual results are in: s3://bucket/embeddings/{invocationId}/output.json
                uri_parts = output_s3_uri.replace('s3://', '').split('/')
                bucket = uri_parts[0]
                key = '/'.join(uri_parts[1:]) + '/output.json'
                
                try:
                    print(f"Fetching result from S3: {bucket}/{key}")
                    s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                    result_data = json.loads(s3_response['Body'].read())
                    print(f"Retrieved result data structure: {list(result_data.keys())}")
                    
                    # Store embeddings to both OpenSearch and S3 Vectors
                    storage_result = None
                    if 'data' in result_data and result_data['data']:
                        try:
                            print("Storing embeddings to both OpenSearch and S3 Vectors...")
                            storage_result = store_embeddings_dual(response, result_data['data'])
                            print(f"Dual storage result: {storage_result}")
                        except Exception as e:
                            print(f"Failed to store embeddings: {e}")
                            storage_result = {'error': str(e)}
                    
                    # Return minimal data to avoid 413 error
                    segments_count = len(result_data.get('data', [])) if 'data' in result_data else 0
                    
                    return {
                        'statusCode': 200,
                        'headers': cors_headers,
                        'body': json.dumps({
                            'status': status,
                            'segments_processed': segments_count,
                            'opensearch_stored': storage_result.get('opensearch', {}).get('stored_count', 0) if isinstance(storage_result, dict) else 0,
                            's3vectors_stored': storage_result.get('s3vectors', {}).get('stored_count', 0) if isinstance(storage_result, dict) else 0,
                            'video_id': storage_result.get('video_id', 'unknown') if isinstance(storage_result, dict) else 'unknown',
                            'storage_times': {
                                'opensearch_ms': storage_result.get('opensearch', {}).get('storage_time_ms', 0) if isinstance(storage_result, dict) else 0,
                                's3vectors_ms': storage_result.get('s3vectors', {}).get('storage_time_ms', 0) if isinstance(storage_result, dict) else 0
                            },
                            'message': f'Embedding completed with {segments_count} segments stored to both systems'
                        })
                    }
                except Exception as e:
                    return {
                        'statusCode': 200,
                        'headers': cors_headers,
                        'body': json.dumps({
                            'status': status,
                            'message': f'Completed but could not retrieve result: {str(e)}'
                        })
                    }
            else:
                return {
                    'statusCode': 200,
                    'headers': cors_headers,
                    'body': json.dumps({
                        'status': status,
                        'message': 'Completed but no output S3 URI found in response'
                    })
                }
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'status': status,
                'message': f'Invocation is {status.lower()}'
            })
        }
    
    except ClientError as e:
        print(f"AWS ClientError in status: {e}")
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        print(f"Error code: {error_code}, Message: {error_message}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'AWS Error ({error_code}): {error_message}'})
        }
    except Exception as e:
        print(f"Unexpected error in status check: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': f'Status check failed: {str(e)}'})
        }

def handle_search(event: Dict[str, Any], cors_headers: Dict[str, str]) -> Dict[str, Any]:
    """Handle vector similarity search"""
    try:
        print("Starting search request...")
        query_params = event.get('queryStringParameters', {}) or {}
        query_text = query_params.get('q', '')
        print(f"Search query: {query_text}")
        
        if not query_text:
            return {
                'statusCode': 400,
                'headers': cors_headers,
                'body': json.dumps({'error': 'Query parameter q is required'})
            }
        
        # Generate embedding for query text using Marengo (async)
        model_input = {
            "inputType": "text",
            "inputText": query_text
        }
        
        try:
            print("Starting async query embedding generation...")
            response = bedrock_client.start_async_invoke(
                modelId='twelvelabs.marengo-embed-2-7-v1:0',
                modelInput=model_input,
                outputDataConfig={
                    's3OutputDataConfig': {
                        's3Uri': f"s3://{os.environ.get('VIDEO_BUCKET')}/search-embeddings/"
                    }
                }
            )
            
            invocation_arn = response.get('invocationArn')
            print(f"Started async embedding with ARN: {invocation_arn}")
            
            # Poll for completion (max 30 seconds for Lambda timeout)
            import time
            max_wait = 25  # seconds
            poll_interval = 1  # second
            waited = 0
            
            while waited < max_wait:
                status_response = bedrock_client.get_async_invoke(invocationArn=invocation_arn)
                status = status_response.get('status')
                print(f"Embedding status: {status} (waited {waited}s)")
                
                if status == 'Completed':
                    # Get the result
                    output_data_config = status_response.get('outputDataConfig', {})
                    s3_output_config = output_data_config.get('s3OutputDataConfig', {})
                    output_s3_uri = s3_output_config.get('s3Uri')
                    
                    if output_s3_uri:
                        uri_parts = output_s3_uri.replace('s3://', '').split('/')
                        bucket = uri_parts[0]
                        key = '/'.join(uri_parts[1:]) + '/output.json'
                        
                        s3_response = s3_client.get_object(Bucket=bucket, Key=key)
                        result_data = json.loads(s3_response['Body'].read())
                        
                        if 'data' in result_data and result_data['data'] and 'embedding' in result_data['data'][0]:
                            query_embedding = result_data['data'][0]['embedding']
                            print(f"Retrieved query embedding length: {len(query_embedding)}")
                            break
                    
                elif status in ['Failed', 'Cancelled']:
                    raise Exception(f"Embedding generation {status.lower()}")
                
                time.sleep(poll_interval)
                waited += poll_interval
            
            if waited >= max_wait:
                return {
                    'statusCode': 408,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'Query embedding generation timed out'})
                }
            
            if not query_embedding:
                return {
                    'statusCode': 500,
                    'headers': cors_headers,
                    'body': json.dumps({'error': 'Failed to generate query embedding'})
                }
            
        except Exception as e:
            print(f"Failed to generate embedding: {e}")
            return {
                'statusCode': 500,
                'headers': cors_headers,
                'body': json.dumps({'error': f'Failed to generate embedding: {str(e)}'})
            }
        
        # Search both OpenSearch and S3 Vectors in parallel for comparison
        print("Starting dual search: OpenSearch vs S3 Vectors...")
        
        opensearch_result = {}
        s3vectors_result = {}
        
        # Search OpenSearch
        try:
            print("Searching OpenSearch...")
            opensearch_result = search_opensearch(query_embedding, top_k=10)
        except Exception as e:
            print(f"OpenSearch search failed: {e}")
            opensearch_result = {
                'results': [],
                'total': 0,
                'search_time_ms': 0,
                'error': str(e)
            }
        
        # Search S3 Vectors
        try:
            print("Searching S3 Vectors...")
            s3vectors_result = search_s3_vectors(query_embedding, top_k=10)
        except Exception as e:
            print(f"S3 Vectors search failed: {e}")
            s3vectors_result = {
                'results': [],
                'total': 0,
                'search_time_ms': 0,
                'error': str(e)
            }
        
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'comparison': {
                    'opensearch': opensearch_result,
                    's3vectors': s3vectors_result
                },
                'query': query_text,
                'message': 'Dual search completed - compare OpenSearch vs S3 Vectors performance and results'
            })
        }
    
    except Exception as e:
        print(f"Search handler failed: {e}")
        return {
            'statusCode': 500,
            'headers': cors_headers,
            'body': json.dumps({'error': str(e)})
        }
