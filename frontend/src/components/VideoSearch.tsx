import React, { useState } from 'react';
import VideoPlayer from './VideoPlayer';

interface SearchResult {
  videoId: string;
  videoS3Uri: string;
  segmentId: string;
  startSec: number;
  endSec: number;
  duration: number;
  embeddingOption: string;
  score: number;
  metadata: {
    [key: string]: any;
  };
}

interface VectorSystemResult {
  results: SearchResult[];
  total: number;
  search_time_ms: number;
  message?: string;
  error?: string;
}

interface DualSearchResult {
  comparison: {
    opensearch: VectorSystemResult;
    s3vectors: VectorSystemResult;
  };
  query: string;
  message: string;
}

const VideoSearch: React.FC = () => {
  const [query, setQuery] = useState('');
  const [dualResults, setDualResults] = useState<DualSearchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedVideos, setExpandedVideos] = useState<Set<string>>(new Set());
  const [activeTab, setActiveTab] = useState<'opensearch' | 's3vectors'>('opensearch');

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://your-api-gateway-url';

  const searchVideos = async () => {
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    setDualResults(null);

    try {
      const response = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(query)}`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        throw new Error('Search failed');
      }

      const result: DualSearchResult = await response.json();
      
      console.log('Dual search results:', result);
      console.log('OpenSearch results:', result.comparison.opensearch.results.length);
      console.log('S3 Vectors results:', result.comparison.s3vectors.results.length);
      console.log('OpenSearch time:', result.comparison.opensearch.search_time_ms, 'ms');
      console.log('S3 Vectors time:', result.comparison.s3vectors.search_time_ms, 'ms');
      
      setDualResults(result);

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      searchVideos();
    }
  };

  return (
    <div className="search-container">
      <h2>Search Videos by Content</h2>
      
      <div className="search-form">
        <input
          type="text"
          className="search-input"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyPress={handleKeyPress}
          placeholder="Search for videos by describing what you're looking for..."
        />
        <button
          className="search-button"
          onClick={searchVideos}
          disabled={loading || !query.trim()}
        >
          {loading ? 'Searching...' : 'Search'}
        </button>
      </div>

      {loading && (
        <div className="loading">
          <div className="spinner"></div>
        </div>
      )}

      {dualResults && (
        <div className="dual-search-results">
          {/* Performance Comparison Header */}
          <div className="performance-comparison">
            <h3>🚀 Vector Search Performance Comparison</h3>
            <div className="performance-stats">
              <div className="stat-card opensearch">
                <h4>🔍 OpenSearch Serverless</h4>
                <p className="time">{dualResults.comparison.opensearch.search_time_ms}ms</p>
                <p className="results-count">{dualResults.comparison.opensearch.results.length} results</p>
                {dualResults.comparison.opensearch.error && (
                  <p className="error-status">❌ {dualResults.comparison.opensearch.error}</p>
                )}
              </div>
              <div className="vs-divider">VS</div>
              <div className="stat-card s3vectors">
                <h4>📦 S3 Vectors</h4>
                <p className="time">{dualResults.comparison.s3vectors.search_time_ms}ms</p>
                <p className="results-count">{dualResults.comparison.s3vectors.results.length} results</p>
                {dualResults.comparison.s3vectors.error && (
                  <p className="error-status">❌ {dualResults.comparison.s3vectors.error}</p>
                )}
              </div>
            </div>
            <div className="winner-announcement">
              {(() => {
                const osTime = dualResults.comparison.opensearch.search_time_ms;
                const s3Time = dualResults.comparison.s3vectors.search_time_ms;
                if (osTime < s3Time) {
                  return <p>🏆 <strong>OpenSearch Serverless</strong> is faster by {(s3Time - osTime).toFixed(0)}ms!</p>;
                } else if (s3Time < osTime) {
                  return <p>🏆 <strong>S3 Vectors</strong> is faster by {(osTime - s3Time).toFixed(0)}ms!</p>;
                } else {
                  return <p>🤝 Both systems performed equally!</p>;
                }
              })()}
            </div>
          </div>

          {/* Tab Navigation */}
          <div className="result-tabs">
            <button 
              className={`tab ${activeTab === 'opensearch' ? 'active' : ''}`}
              onClick={() => setActiveTab('opensearch')}
            >
              🔍 OpenSearch Results ({dualResults.comparison.opensearch.results.length})
            </button>
            <button 
              className={`tab ${activeTab === 's3vectors' ? 'active' : ''}`}
              onClick={() => setActiveTab('s3vectors')}
            >
              📦 S3 Vectors Results ({dualResults.comparison.s3vectors.results.length})
            </button>
          </div>

          {/* Results Display */}
          <div className="tab-content">
            {(() => {
              const currentResults = dualResults.comparison[activeTab];
              const systemName = activeTab === 'opensearch' ? 'OpenSearch Serverless' : 'S3 Vectors';
              
              if (currentResults.error) {
                return (
                  <div className="error-state">
                    <h4>❌ {systemName} Error</h4>
                    <p>{currentResults.error}</p>
                  </div>
                );
              }

              if (currentResults.results.length === 0) {
                return (
                  <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
                    <p>No results found in {systemName}.</p>
                    {currentResults.message && <p><em>{currentResults.message}</em></p>}
                  </div>
                );
              }

              const formatTime = (seconds: number): string => {
                const minutes = Math.floor(seconds / 60);
                const secs = Math.floor(seconds % 60);
                return `${minutes}:${secs.toString().padStart(2, '0')}`;
              };

              // Deduplicate results by video + timestamp
              const deduplicatedResults = currentResults.results.reduce((acc, result) => {
                const dedupeKey = `${result.videoId}-${result.startSec}-${result.endSec}`;
                
                // Keep the result with the best score (highest for opensearch, lowest for s3vectors)
                if (!acc[dedupeKey] || 
                    (activeTab === 'opensearch' && result.score > acc[dedupeKey].score) ||
                    (activeTab === 's3vectors' && result.score < acc[dedupeKey].score)) {
                  acc[dedupeKey] = result;
                }
                
                return acc;
              }, {} as Record<string, SearchResult>);
              
              const uniqueResults = Object.values(deduplicatedResults);

              return (
                <div className="search-results">
                  <div className="system-header">
                    <h4>{systemName} Results - {currentResults.search_time_ms}ms</h4>
                    {uniqueResults.length !== currentResults.results.length && (
                      <p style={{ fontSize: '0.9em', color: '#666', marginTop: '5px' }}>
                        Showing {uniqueResults.length} unique results (deduplicated from {currentResults.results.length} total)
                      </p>
                    )}
                  </div>
                  {uniqueResults.map((result, index) => {
                    const resultKey = `${activeTab}-${result.videoId}-${result.segmentId}-${result.startSec}`;
                    const isExpanded = expandedVideos.has(resultKey);
                    
                    const toggleExpanded = () => {
                      console.log(`🎬 Play Video button clicked for:`, {
                        system: activeTab,
                        videoId: result.videoId,
                        segmentId: result.segmentId,
                        videoS3Uri: result.videoS3Uri,
                        startTime: result.startSec,
                        endTime: result.endSec,
                        isCurrentlyExpanded: isExpanded
                      });
                      
                      const newExpanded = new Set(expandedVideos);
                      if (isExpanded) {
                        console.log(`🔽 Hiding video player for segment: ${resultKey}`);
                        newExpanded.delete(resultKey);
                      } else {
                        console.log(`🔼 Showing video player for segment: ${resultKey}`);
                        console.log(`📹 Video will load from S3 URI: ${result.videoS3Uri}`);
                        console.log(`⏰ Video will start at: ${result.startSec} seconds`);
                        newExpanded.add(resultKey);
                      }
                      setExpandedVideos(newExpanded);
                    };
                    
                    return (
                      <div key={resultKey} className={`search-result enhanced ${activeTab}`}>
                        <div className="result-header">
                          <div className="video-info">
                            <h4>📹 {result.videoId}</h4>
                            <div className="segment-info">
                              <span className="time-range">
                                ⏱️ {formatTime(result.startSec)} - {formatTime(result.endSec)}
                              </span>
                              <span className="duration">
                                ({Math.round(result.duration)}s segment)
                              </span>
                              <span className="embedding-type">
                                {result.embeddingOption === 'visual-text' ? '👁️ Visual' : 
                                 result.embeddingOption === 'audio' ? '🔊 Audio' : '🎥 Mixed'}
                              </span>
                            </div>
                          </div>
                          <div className="result-actions">
                            <div className="similarity-score">
                              <strong>Score:</strong> {activeTab === 'opensearch' 
                                ? (result.score * 100).toFixed(1) + '%'
                                : result.score.toFixed(3) + ' (distance)'
                              }
                            </div>
                            <button 
                              className="toggle-video-btn"
                              onClick={toggleExpanded}
                            >
                              {isExpanded ? '🔼 Hide Video' : '▶️ Play Video'}
                            </button>
                          </div>
                        </div>
                        
                        {isExpanded && (
                          <div className="video-preview">
                            <VideoPlayer
                              videoS3Uri={result.videoS3Uri}
                              startTime={result.startSec}
                              autoPlay={false}
                              className="search-result-video"
                              onError={(error) => console.error('Video playback error:', error)}
                            />
                          </div>
                        )}
                        
                        {Object.keys(result.metadata).length > 0 && (
                          <div className="metadata-section">
                            <details>
                              <summary><strong>📊 Technical Details</strong></summary>
                              <pre className="metadata-content">
                                {JSON.stringify({
                                  system: systemName,
                                  segmentId: result.segmentId,
                                  embeddingType: result.embeddingOption,
                                  score: result.score,
                                  timeRange: `${result.startSec}s - ${result.endSec}s`,
                                  ...result.metadata
                                }, null, 2)}
                              </pre>
                            </details>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              );
            })()}
          </div>
        </div>
      )}

      {!dualResults && !loading && query && (
        <div style={{ textAlign: 'center', padding: '40px', color: '#666' }}>
          <p>No results from either system.</p>
          <p>Make sure you have uploaded and processed videos with embeddings first.</p>
        </div>
      )}

      {error && <div className="error">{error}</div>}

      <div style={{ marginTop: '30px', padding: '20px', backgroundColor: '#f0f8ff', borderRadius: '5px', textAlign: 'left' }}>
        <h4>🔄 Dual Vector Search Comparison:</h4>
        <ol style={{ margin: '10px 0' }}>
          <li><strong>Query Processing:</strong> Your search query is converted to an embedding using Twelve Labs Marengo</li>
          <li><strong>Parallel Search:</strong> The system simultaneously searches both OpenSearch Serverless and S3 Vectors</li>
          <li><strong>Performance Comparison:</strong> Search times are measured and compared for both systems</li>
          <li><strong>Results Analysis:</strong> You can compare relevancy and performance between the two vector databases</li>
        </ol>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '15px', marginTop: '15px' }}>
          <div style={{ backgroundColor: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #ddd' }}>
            <h5>🔍 OpenSearch Serverless</h5>
            <ul style={{ fontSize: '0.9em', margin: '5px 0' }}>
              <li>Managed vector search service</li>
              <li>HNSW algorithm with cosine similarity</li>
              <li>Similarity scores (higher = more similar)</li>
            </ul>
          </div>
          <div style={{ backgroundColor: '#fff', padding: '10px', borderRadius: '5px', border: '1px solid #ddd' }}>
            <h5>📦 S3 Vectors</h5>
            <ul style={{ fontSize: '0.9em', margin: '5px 0' }}>
              <li>Native S3 vector storage</li>
              <li>Built-in cosine distance search</li>
              <li>Distance scores (lower = more similar)</li>
            </ul>
          </div>
        </div>
        <p style={{ marginTop: '10px' }}><em>Note: Videos must be processed with embeddings before they appear in search results. This demo shows real-time performance comparison between two AWS vector database solutions.</em></p>
      </div>
    </div>
  );
};

export default VideoSearch;
