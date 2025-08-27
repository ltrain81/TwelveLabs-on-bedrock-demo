import React, { useState } from 'react';

interface VideoAnalysisProps {
  video: {
    key: string;
    bucket: string;
    s3Uri: string;
  };
}

const VideoAnalysis: React.FC<VideoAnalysisProps> = ({ video }) => {
  const [prompt, setPrompt] = useState('Analyze this video and provide a detailed description of what you see, including actions, objects, scenes, and any notable events.');
  const [analysis, setAnalysis] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [embeddingStatus, setEmbeddingStatus] = useState<string | null>(null);
  const [analysisInvocationArn, setAnalysisInvocationArn] = useState<string | null>(null);
  const [embeddingInvocationArn, setEmbeddingInvocationArn] = useState<string | null>(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://your-api-gateway-url';

  const analyzeVideo = async () => {
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setAnalysisInvocationArn(null);

    try {
      const response = await fetch(`${API_BASE_URL}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          s3Uri: video.s3Uri,
          prompt: prompt,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        if (response.status === 404 && errorData.error?.includes('not found in S3')) {
          throw new Error('Video is still uploading. Please wait a moment and try again.');
        }
        throw new Error(errorData.error || 'Failed to analyze video');
      }

      const result = await response.json();
      
      // Pegasus is now synchronous, so we get the result immediately
      if (result.analysis) {
        setAnalysis(result.analysis);
      } else {
        setAnalysis('Analysis completed but no content returned');
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };

  const checkAnalysisStatus = async () => {
    if (!analysisInvocationArn) return;

    try {
      const response = await fetch(`${API_BASE_URL}/status?invocationArn=${encodeURIComponent(analysisInvocationArn)}`);
      
      if (!response.ok) {
        throw new Error('Failed to check status');
      }

      const result = await response.json();
      
      if (result.status === 'Completed' && result.result) {
        setAnalysis(result.result.message || result.result.analysis || JSON.stringify(result.result, null, 2));
      } else {
        setAnalysis(`Status: ${result.status} - ${result.message || 'Processing...'}`);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Status check failed');
    }
  };

  const generateEmbeddings = async () => {
    setEmbeddingStatus('Generating embeddings...');
    setError(null);
    setEmbeddingInvocationArn(null);

    try {
      const response = await fetch(`${API_BASE_URL}/embed`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          s3Uri: video.s3Uri,
          videoId: video.key,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        if (response.status === 404 && errorData.error?.includes('not found in S3')) {
          throw new Error('Video is still uploading. Please wait a moment and try again.');
        }
        throw new Error(errorData.error || 'Failed to generate embeddings');
      }

      const result = await response.json();
      setEmbeddingInvocationArn(result.invocationArn);
      setEmbeddingStatus(`Embeddings generation started. ARN: ${result.invocationArn}`);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Embedding generation failed');
      setEmbeddingStatus(null);
    }
  };

  const checkEmbeddingStatus = async () => {
    if (!embeddingInvocationArn) {
      setError('No invocation ARN available. Please generate embeddings first.');
      return;
    }

    setEmbeddingStatus('Checking status...');
    setError(null);

    try {
      console.log('Checking status for ARN:', embeddingInvocationArn);
      const response = await fetch(`${API_BASE_URL}/status?invocationArn=${encodeURIComponent(embeddingInvocationArn)}`);
      
      console.log('Status response:', response.status, response.statusText);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        console.error('Status check error:', errorData);
        throw new Error(errorData.error || `Status check failed: ${response.status} ${response.statusText}`);
      }

      const result = await response.json();
      console.log('Status result:', result);
      
      if (result.status === 'Completed') {
        if (result.segments_processed) {
          let statusMessage = `✅ Embeddings completed! Processed ${result.segments_processed} segments.`;
          
          // Add dual storage information if available
          if (result.opensearch_stored || result.s3vectors_stored) {
            statusMessage += `\n\n🔍 OpenSearch: ${result.opensearch_stored || 0} segments`;
            statusMessage += `\n📦 S3 Vectors: ${result.s3vectors_stored || 0} segments`;
            
            // Add timing information if available
            if (result.storage_times) {
              statusMessage += `\n\n⏱️ Storage Performance:`;
              statusMessage += `\n• OpenSearch: ${result.storage_times.opensearch_ms || 0}ms`;
              statusMessage += `\n• S3 Vectors: ${result.storage_times.s3vectors_ms || 0}ms`;
            }
            
            statusMessage += `\n\n🔍 Video is now searchable in both systems!`;
          }
          
          setEmbeddingStatus(statusMessage);
        } else {
          setEmbeddingStatus(`✅ Embeddings completed successfully! Video is now searchable.`);
        }
      } else {
        setEmbeddingStatus(`Status: ${result.status} - ${result.message || 'Processing...'}`);
      }

    } catch (err) {
      console.error('Embedding status check error:', err);
      setError(err instanceof Error ? err.message : 'Embedding status check failed');
      setEmbeddingStatus(null);
    }
  };

  return (
    <div className="analysis-container">
      <h2>Video Analysis</h2>
      
      <div className="video-info">
        <p><strong>Video:</strong> {video.key}</p>
        <p><strong>S3 URI:</strong> {video.s3Uri}</p>
      </div>

      <div className="analysis-form">
        <h3>Analysis Prompt</h3>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="Enter your analysis prompt here..."
          rows={4}
        />
        
        <div style={{ marginTop: '20px', display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            className="upload-button"
            onClick={analyzeVideo}
            disabled={loading || !prompt.trim()}
          >
            {loading ? 'Analyzing...' : 'Analyze Video (Pegasus)'}
          </button>
          
          <button
            className="upload-button"
            onClick={generateEmbeddings}
            disabled={loading}
            style={{ backgroundColor: '#38a169' }}
          >
            Generate Embeddings (Marengo)
          </button>

          {embeddingInvocationArn && (
            <button
              className="upload-button"
              onClick={checkEmbeddingStatus}
              style={{ backgroundColor: '#38a169' }}
            >
              Check Embedding Status
            </button>
          )}
        </div>
      </div>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
        </div>
      )}

      {analysis && (
        <div className="analysis-result">
          <h3>Analysis Result (Twelve Labs Pegasus)</h3>
          <div style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}>
            {analysis}
          </div>
        </div>
      )}

      {embeddingStatus && (
        <div className="success">
          <h4>Embedding Status</h4>
          <p>{embeddingStatus}</p>
          <p><em>Note: Embedding generation is asynchronous and may take several minutes to complete.</em></p>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div style={{ marginTop: '30px', padding: '20px', backgroundColor: '#f0f8ff', borderRadius: '5px' }}>
        <h4>About the Models (Hybrid Processing):</h4>
        <ul style={{ textAlign: 'left', margin: '10px 0' }}>
          <li><strong>Twelve Labs Pegasus:</strong> Provides comprehensive video understanding and analysis. Uses synchronous processing for immediate results.</li>
          <li><strong>Twelve Labs Marengo:</strong> Generates embeddings from video content for similarity search. Uses async processing - click "Check Embedding Status" to get results.</li>
          <li><strong>Processing Types:</strong> Pegasus returns results immediately, while Marengo processes asynchronously for better handling of large videos.</li>
        </ul>
      </div>
    </div>
  );
};

export default VideoAnalysis;
