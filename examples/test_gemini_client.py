#!/usr/bin/env python3
"""
Test script for the GeminiClient class.
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.tools.gemini_client import GeminiClient


def main():
    """Test the GeminiClient with a sample video."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get API key from environment variable
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please create a .env file with your Gemini API key.")
        return 1
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test Gemini video analysis")
    parser.add_argument("--video", help="Path to a local video file to analyze")
    parser.add_argument("--youtube", help="YouTube URL to analyze")
    args = parser.parse_args()
    
    if not args.video and not args.youtube:
        parser.print_help()
        print("\nError: You must provide either a local video path or a YouTube URL.")
        return 1
    
    # Create GeminiClient
    client = GeminiClient(api_key=api_key)
    
    # Analyze the video
    if args.video:
        print(f"Analyzing local video: {args.video}")
        moments = client.analyze_video(args.video)
        
        # Display the results
        print(f"\nIdentified {len(moments)} interesting moments:")
        
        for i, moment in enumerate(moments, 1):
            print(f"\nMoment {i}:")
            print(f"  Time: {moment.start_time_str} - {moment.end_time_str} ({moment.duration:.1f} seconds)")
            print(f"  Description: {moment.description}")
    
    if args.youtube:
        print(f"Analyzing YouTube video: {args.youtube}")
        moments = client.analyze_youtube_video(args.youtube)
        
        # Display the results
        print(f"\nIdentified {len(moments)} interesting moments:")
        
        for i, moment in enumerate(moments, 1):
            print(f"\nMoment {i}:")
            print(f"  Time: {moment.start_time_str} - {moment.end_time_str} ({moment.duration:.1f} seconds)")
            print(f"  Description: {moment.description}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 