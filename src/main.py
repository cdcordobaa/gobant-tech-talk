#!/usr/bin/env python3
"""
Simple demonstration of the video analysis pipeline with LangGraph.
"""

import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.basic_pipeline import run_pipeline


def main(video_path):
    """
    Run the video analysis pipeline on the provided video file.
    
    Args:
        video_path: Path to the video file to analyze
    """
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    print(f"Analyzing video: {video_path}")
    
    # Run the pipeline
    result = run_pipeline(video_path, api_key)
    
    # Display results
    if "error" in result and result["error"]:
        print(f"Error: {result['error']}")
        sys.exit(1)
    
    print(f"Analysis complete. Found {len(result['moments'])} interesting moments:")
    for i, moment in enumerate(result["moments"]):
        print(f"Moment {i+1}: {moment.start_time:.1f}s to {moment.end_time:.1f}s - {moment.description}")


if __name__ == "__main__":
    # Get video path from command line argument or use default
    video_path = sys.argv[1] if len(sys.argv) > 1 else "input_videos/sample.mp4"
    
    # Check if video exists
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        print("Usage: python src/main.py [path_to_video]")
        sys.exit(1)
        
    main(video_path) 