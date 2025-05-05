"""Client for interacting with Google's Gemini API for video content analysis."""

import os
import json
import tempfile
from typing import List, Dict, Any, Optional, Union
from pathlib import Path

import google.generativeai as genai
from PIL import Image

from src.models.state import VideoMoment
from src.tools.video_utils import get_video_duration_and_dimensions, validate_video_file


class GeminiClient:
    """Client for interacting with Google's Gemini API for video content analysis."""
    
    def __init__(self, api_key: str):
        """
        Initialize the Gemini API client.
        
        Args:
            api_key: Google API key with access to Gemini models
        """
        genai.configure(api_key=api_key)
        # Use gemini-1.5-pro for video processing (supports video input natively)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
    
    def analyze_video(self, video_path: str) -> List[VideoMoment]:
        """
        Analyze a video using Gemini's native video processing capabilities.
        
        Args:
            video_path: Path to the video file
            
        Returns:
            List of VideoMoment objects representing interesting moments
        """
        try:
            # Validate the video file exists and is readable
            validate_video_file(video_path)
            
            # Get video duration to use in prompt
            duration, _ = get_video_duration_and_dimensions(video_path)
            
            # Prepare the file for Gemini API
            with open(video_path, 'rb') as f:
                video_data = f.read()
            
            mime_type = "video/mp4"  # Default mime type
            # Determine the correct MIME type based on file extension
            if video_path.lower().endswith('.mp4'):
                mime_type = "video/mp4"
            elif video_path.lower().endswith('.mov'):
                mime_type = "video/mov"
            elif video_path.lower().endswith('.avi'):
                mime_type = "video/avi"
            elif video_path.lower().endswith('.webm'):
                mime_type = "video/webm"
            elif video_path.lower().endswith('.mpeg') or video_path.lower().endswith('.mpg'):
                mime_type = "video/mpeg"
                
            # Prepare the prompt for Gemini
            prompt = f"""
            Analyze this video content with duration of {int(duration)} seconds.
            Identify 2-4 interesting moments or segments in the video.
            
            For each interesting moment, provide:
            1. A start time (in seconds)
            2. An end time (in seconds)
            3. A brief description of what makes this moment interesting
            
            Return your response in this JSON format:
            [
                {{"start_time": 45, "end_time": 60, "description": "Speaker explains key concept with animated example"}},
                {{"start_time": 180, "end_time": 195, "description": "Live code demonstration of the feature"}}
            ]
            
            Only return the JSON array, nothing else.
            """
            
            # Create the content parts
            # First part is the video data as a blob
            video_part = {"mime_type": mime_type, "data": video_data}
            
            # Create the generation config - using a temperature of 0.2 for more predictable results
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.8,
                "response_mime_type": "text/plain"
            }
            
            # Call Gemini API with the video - fixed format with proper role specification
            response = self.model.generate_content(
                [
                    {"text": prompt},
                    {"inline_data": video_part}
                ],
                generation_config=generation_config
            )
            
            # Parse the response text as JSON
            response_text = response.text
            
            # Clean the response if it contains markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                moments_data = json.loads(response_text)
                
                # Convert to VideoMoment objects
                moments = []
                for moment_data in moments_data:
                    # Validate required fields
                    if all(k in moment_data for k in ["start_time", "end_time", "description"]):
                        moment = VideoMoment(
                            start_time=float(moment_data["start_time"]),
                            end_time=float(moment_data["end_time"]),
                            description=moment_data["description"],
                            engagement_score=0.5  # Default score
                        )
                        moments.append(moment)
                
                return moments
                
            except json.JSONDecodeError:
                print(f"Failed to parse Gemini response as JSON: {response_text}")
                return []
                
        except Exception as e:
            print(f"Error analyzing video: {str(e)}")
            return []
            
    def analyze_youtube_video(self, youtube_url: str) -> List[VideoMoment]:
        """
        Analyze a YouTube video using Gemini's video processing capabilities.
        
        Args:
            youtube_url: URL to a YouTube video
            
        Returns:
            List of VideoMoment objects representing interesting moments
        """
        try:
            # Prepare the prompt for Gemini
            prompt = f"""
            Analyze this YouTube video: {youtube_url}
            
            Identify 2-4 interesting moments or segments in the video.
            
            For each interesting moment, provide:
            1. A start time (in seconds)
            2. An end time (in seconds)
            3. A brief description of what makes this moment interesting
            
            Return your response in this JSON format:
            [
                {{"start_time": 45, "end_time": 60, "description": "Speaker explains key concept with animated example"}},
                {{"start_time": 180, "end_time": 195, "description": "Live code demonstration of the feature"}}
            ]
            
            Only return the JSON array, nothing else.
            """
            
            # Create the generation config
            generation_config = {
                "temperature": 0.2,
                "top_p": 0.8,
                "response_mime_type": "text/plain"
            }
            
            # Call Gemini API with the YouTube URL
            response = self.model.generate_content(
                {"text": prompt},
                generation_config=generation_config
            )
            
            # Parse the response text as JSON
            response_text = response.text
            
            # Clean the response if it contains markdown code blocks
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            try:
                moments_data = json.loads(response_text)
                
                # Convert to VideoMoment objects
                moments = []
                for moment_data in moments_data:
                    # Validate required fields
                    if all(k in moment_data for k in ["start_time", "end_time", "description"]):
                        moment = VideoMoment(
                            start_time=float(moment_data["start_time"]),
                            end_time=float(moment_data["end_time"]),
                            description=moment_data["description"],
                            engagement_score=0.5  # Default score
                        )
                        moments.append(moment)
                
                return moments
                
            except json.JSONDecodeError:
                print(f"Failed to parse Gemini response as JSON: {response_text}")
                return []
                
        except Exception as e:
            print(f"Error analyzing YouTube video: {str(e)}")
            return [] 