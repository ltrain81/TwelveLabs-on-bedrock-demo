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
  const [analysisJobId, setAnalysisJobId] = useState<string | null>(null);
  const [analysisStatus, setAnalysisStatus] = useState<string | null>(null);
  const [embeddingInvocationArn, setEmbeddingInvocationArn] = useState<string | null>(null);

  const API_BASE_URL = (process.env.REACT_APP_API_URL || 'https://your-api-gateway-url').replace(/\/+$/, '');

  const analyzeVideo = async () => {
    setLoading(true);
    setError(null);
    setAnalysis(null);
    setAnalysisJobId(null);
    setAnalysisStatus(null);

    try {
      const analyzeUrl = `${API_BASE_URL}/analyze`;
      console.log('Making analyze request to:', analyzeUrl);
      const response = await fetch(analyzeUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          s3Uri: video.s3Uri,
          videoId: video.key,
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
      
      if (result.analysisJobId) {
        setAnalysisJobId(result.analysisJobId);
        setAnalysisStatus('Analysis started and running asynchronously. Use "Check Analysis Status" button to get results.');
        
        // Don't wait - let user check status manually
        console.log(`Analysis job ${result.analysisJobId} started successfully`);
      } else {
        throw new Error('No analysis job ID received');
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setLoading(false);
    }
  };


  const checkAnalysisStatus = async () => {
    if (!analysisJobId) {
      setError('No analysis job ID available. Please start an analysis first.');
      return;
    }

    setAnalysisStatus('Checking analysis status...');
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/status?analysisJobId=${encodeURIComponent(analysisJobId)}`);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ error: 'Unknown error' }));
        throw new Error(errorData.error || 'Failed to check analysis status');
      }

      const result = await response.json();
      
      if (result.status === 'Completed') {
        setAnalysis(result.analysis || 'Analysis completed but no content returned');
        setAnalysisStatus(`✅ Analysis completed successfully! Processing time: ${result.processingTime || 0}s`);
      } else if (result.status === 'Failed') {
        setError(result.error || 'Analysis failed');
        setAnalysisStatus('❌ Analysis failed');
      } else {
        setAnalysisStatus(`Status: ${result.status} - ${result.message || 'Processing...'}`);
      }

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis status check failed');
      setAnalysisStatus(null);
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

          {analysisJobId && (
            <button
              className="upload-button"
              onClick={checkAnalysisStatus}
              style={{ backgroundColor: '#d69e2e' }}
            >
              Check Analysis Status
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

      {analysisStatus && (
        <div className="success">
          <h4>Analysis Status</h4>
          <p style={{ whiteSpace: 'pre-wrap' }}>{analysisStatus}</p>
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
        <h4>About the Models (Async Processing):</h4>
        <ul style={{ textAlign: 'left', margin: '10px 0' }}>
          <li><strong>Twelve Labs Pegasus:</strong> Provides comprehensive video understanding and analysis. Uses async processing due to API Gateway timeout limits - click "Check Analysis Status" if it takes more than 10 seconds.</li>
          <li><strong>Twelve Labs Marengo:</strong> Generates embeddings from video content for similarity search. Uses async processing - click "Check Embedding Status" to get results.</li>
          <li><strong>Processing Types:</strong> Both models now use async processing for better handling of large videos and timeout management.</li>
        </ul>
      </div>
    </div>
  );
};

export default VideoAnalysis;
