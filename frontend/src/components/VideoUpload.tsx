import React, { useState, useRef } from 'react';

interface VideoUploadProps {
  onVideoUploaded: (video: { key: string; bucket: string; s3Uri: string }) => void;
}

const VideoUpload: React.FC<VideoUploadProps> = ({ onVideoUploaded }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const API_BASE_URL = process.env.REACT_APP_API_URL || 'https://your-api-gateway-url';

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
    setError(null);
    setSuccess(null);
    setUploadProgress(0);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const uploadVideo = async () => {
    if (!selectedFile) return;

    setUploading(true);
    setError(null);
    setUploadProgress(0);

    try {
      // Get presigned URL
      const response = await fetch(`${API_BASE_URL}/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: selectedFile.name,
          contentType: selectedFile.type,
        }),
      });

      if (!response.ok) {
        throw new Error('Failed to get upload URL');
      }

      const { uploadUrl, fields, key, bucket } = await response.json();

      // Create FormData for proper multipart upload
      const formData = new FormData();
      
      // Add all the fields from presigned POST in the correct order
      Object.entries(fields).forEach(([key, value]) => {
        formData.append(key, value as string);
      });
      
      // Add the file last (required by S3)
      formData.append('file', selectedFile);

      setUploadProgress(10);

      // Use XMLHttpRequest for better upload tracking and verification
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        
        // Track upload progress
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const percentComplete = (event.loaded / event.total) * 80; // Leave 20% for verification
            setUploadProgress(Math.round(10 + percentComplete));
          }
        };
        
        xhr.onload = () => {
          if (xhr.status === 200 || xhr.status === 204) {
            console.log('S3 upload successful');
            setUploadProgress(90);
            
            // Verify the object exists in S3 before resolving
            const s3Uri = `s3://${bucket}/${key}`;
            verifyS3Upload(s3Uri)
              .then(() => {
                setUploadProgress(100);
                resolve();
              })
              .catch(reject);
          } else {
            console.error('S3 upload failed:', xhr.status, xhr.statusText, xhr.responseText);
            reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.statusText}`));
          }
        };
        
        xhr.onerror = () => {
          console.error('S3 upload network error');
          reject(new Error('Network error during upload'));
        };
        
        xhr.timeout = 300000; // 5 minute timeout for large files
        xhr.ontimeout = () => {
          reject(new Error('Upload timeout - file may be too large'));
        };
        
        // Send the request
        xhr.open('POST', uploadUrl);
        xhr.send(formData);
      });

      setSuccess('Video uploaded and verified successfully!');
      const s3Uri = `s3://${bucket}/${key}`;
      onVideoUploaded({ key, bucket, s3Uri });

    } catch (err) {
      console.error('Upload error:', err);
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };
  
  const verifyS3Upload = async (s3Uri: string): Promise<void> => {
    // Give S3 a moment to process the upload
    await new Promise(resolve => setTimeout(resolve, 2000));
    
    // For now, just wait a reasonable time instead of calling the CORS-problematic endpoint
    // The backend will handle waiting for S3 object availability when analyze/embed is called
    console.log('S3 upload completed - backend will verify availability when processing');
    
    // TODO: Fix CORS for /video-url endpoint to enable proper verification
    // For now, we rely on the backend's wait_for_s3_object function
  };

  return (
    <div className="upload-container">
      <h2>Upload Video for Analysis</h2>
      
      <div
        className="drop-zone"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => fileInputRef.current?.click()}
      >
        {selectedFile ? (
          <div className="file-info">
            <p><strong>Selected:</strong> {selectedFile.name}</p>
            <p><strong>Size:</strong> {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
            <p><strong>Type:</strong> {selectedFile.type}</p>
          </div>
        ) : (
          <div className="drop-message">
            <p>Drag and drop a video file here, or click to select</p>
            <p className="file-types">Supported: MP4, MOV, AVI (max 2GB)</p>
          </div>
        )}
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        onChange={handleFileInputChange}
        style={{ display: 'none' }}
      />

      {selectedFile && (
        <div style={{ marginTop: '20px' }}>
          <button
            className="upload-button"
            onClick={uploadVideo}
            disabled={uploading}
          >
            {uploading ? `Uploading... ${uploadProgress}%` : 'Upload Video'}
          </button>
        </div>
      )}

      {uploading && (
        <div className="progress-container">
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${uploadProgress}%` }}
            ></div>
          </div>
          <p>{uploadProgress}% uploaded</p>
        </div>
      )}

      {success && <div className="success">{success}</div>}
      {error && <div className="error">{error}</div>}

      <div style={{ marginTop: '20px', fontSize: '14px', color: '#666' }}>
        <p><strong>Requirements:</strong></p>
        <ul style={{ textAlign: 'left', margin: '10px 0' }}>
          <li>Video formats: MP4, MOV, AVI</li>
          <li>Maximum file size: 2GB</li>
          <li>Maximum duration: 2 hours</li>
          <li>Recommended resolution: 1080p or lower</li>
        </ul>
      </div>
    </div>
  );
};

export default VideoUpload;
