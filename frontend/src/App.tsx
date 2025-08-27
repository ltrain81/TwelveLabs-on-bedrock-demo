import React, { useState } from 'react';
import './App.css';
import VideoUpload from './components/VideoUpload';
import VideoAnalysis from './components/VideoAnalysis';
import VideoSearch from './components/VideoSearch';

interface UploadedVideo {
  key: string;
  bucket: string;
  s3Uri: string;
}

function App() {
  const [uploadedVideo, setUploadedVideo] = useState<UploadedVideo | null>(null);
  const [activeTab, setActiveTab] = useState<'upload' | 'analyze' | 'search'>('upload');

  const handleVideoUploaded = (videoData: UploadedVideo) => {
    setUploadedVideo(videoData);
    setActiveTab('analyze');
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Video Understanding with Twelve Labs</h1>
        <nav className="nav-tabs">
          <button 
            className={activeTab === 'upload' ? 'active' : ''}
            onClick={() => setActiveTab('upload')}
          >
            Upload Video
          </button>
          <button 
            className={activeTab === 'analyze' ? 'active' : ''}
            onClick={() => setActiveTab('analyze')}
            disabled={!uploadedVideo}
          >
            Analyze Video
          </button>
          <button 
            className={activeTab === 'search' ? 'active' : ''}
            onClick={() => setActiveTab('search')}
          >
            Search Videos
          </button>
        </nav>
      </header>

      <main className="App-main">
        {activeTab === 'upload' && (
          <VideoUpload onVideoUploaded={handleVideoUploaded} />
        )}
        
        {activeTab === 'analyze' && uploadedVideo && (
          <VideoAnalysis video={uploadedVideo} />
        )}
        
        {activeTab === 'search' && (
          <VideoSearch />
        )}
      </main>
    </div>
  );
}

export default App;
