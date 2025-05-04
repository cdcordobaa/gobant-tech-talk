"""Video processing utilities for content extraction and manipulation."""

# This file will contain video processing utilities using ffmpeg-python 

import os
import json
from typing import Dict, Tuple, Any, Optional
from datetime import datetime
from pathlib import Path

import ffmpeg
from PIL import Image


def validate_video_file(file_path: str) -> bool:
    """
    Validate that a video file exists, is readable, and has a supported format.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        True if the file is valid
        
    Raises:
        ValueError: If the file is invalid or cannot be processed
    """
    if not os.path.exists(file_path):
        raise ValueError(f"File does not exist: {file_path}")
    
    if not os.path.isfile(file_path):
        raise ValueError(f"Path is not a file: {file_path}")
    
    # Check if the file is readable
    if not os.access(file_path, os.R_OK):
        raise ValueError(f"File is not readable: {file_path}")
    
    # Check if the format is supported by ffmpeg
    try:
        probe = ffmpeg.probe(file_path)
        # If we can probe it, ffmpeg recognizes the format
        # Check if it has a video stream
        if not any(stream['codec_type'] == 'video' for stream in probe['streams']):
            raise ValueError(f"File does not contain a video stream: {file_path}")
    except ffmpeg.Error as e:
        raise ValueError(f"Invalid video format or corrupted file: {e.stderr}")
    
    return True


def extract_video_metadata(file_path: str) -> Dict[str, Any]:
    """
    Extract metadata from a video file using FFmpeg.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Dictionary containing video metadata
    """
    try:
        probe = ffmpeg.probe(file_path)
        
        # Find the video stream
        video_stream = next((stream for stream in probe['streams'] 
                           if stream['codec_type'] == 'video'), None)
        
        if video_stream is None:
            raise ValueError(f"No video stream found in file: {file_path}")
            
        # Extract common metadata
        metadata = {
            'duration': float(probe.get('format', {}).get('duration', 0)),
            'dimensions': (
                int(video_stream.get('width', 0)), 
                int(video_stream.get('height', 0))
            ),
        }
        
        # Try to get creation date
        if 'tags' in probe.get('format', {}) and 'creation_time' in probe['format']['tags']:
            creation_time_str = probe['format']['tags']['creation_time']
            try:
                # Standard format is YYYY-MM-DDThh:mm:ss.fffffffZ
                metadata['creation_date'] = datetime.fromisoformat(
                    creation_time_str.replace('Z', '+00:00')
                )
            except ValueError:
                # If we can't parse it, skip
                pass
                
        return metadata
        
    except ffmpeg.Error as e:
        raise ValueError(f"Failed to extract metadata: {e.stderr}")


def extract_thumbnail(video_path: str, timestamp: float, output_path: Optional[str] = None) -> str:
    """
    Extract a thumbnail from a video at the specified timestamp.
    
    Args:
        video_path: Path to the video file
        timestamp: Time in seconds at which to extract the thumbnail
        output_path: Path where to save the thumbnail. If None, a path will be generated.
        
    Returns:
        Path to the saved thumbnail
    """
    if output_path is None:
        video_filename = os.path.basename(video_path)
        base_name, _ = os.path.splitext(video_filename)
        output_dir = os.path.dirname(video_path)
        output_path = os.path.join(output_dir, f"{base_name}_thumbnail_{int(timestamp)}s.jpg")
    
    try:
        # Make sure the output directory exists
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Extract the frame
        (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output(output_path, vframes=1)
            .overwrite_output()
            .run(capture_stdout=True, capture_stderr=True)
        )
        
        return output_path
    
    except ffmpeg.Error as e:
        raise ValueError(f"Failed to extract thumbnail: {e.stderr.decode('utf-8')}")


def get_video_duration_and_dimensions(file_path: str) -> Tuple[float, Tuple[int, int]]:
    """
    Get the duration and dimensions of a video file.
    
    Args:
        file_path: Path to the video file
        
    Returns:
        Tuple of (duration in seconds, (width, height))
    """
    metadata = extract_video_metadata(file_path)
    return metadata['duration'], metadata['dimensions'] 