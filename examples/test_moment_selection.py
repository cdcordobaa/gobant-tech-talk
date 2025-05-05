#!/usr/bin/env python3
"""
Test script demonstrating the full video analysis pipeline with moment selection.
"""

import os
import sys
from pathlib import Path
import argparse

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.tools.gemini_client import GeminiClient
from src.models.state import VideoMetadata, VideoMoment, SelectedMoment, WorkflowState
from src.agents.video_analysis import video_analysis_agent
from src.agents.moment_selection import moment_selection_agent


def main():
    """Test the complete video analysis pipeline with moment selection."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test video analysis and moment selection pipeline")
    parser.add_argument("--video", help="Path to a local video file to analyze")
    parser.add_argument("--youtube", help="YouTube URL to analyze")
    args = parser.parse_args()
    
    if not args.video and not args.youtube:
        parser.print_help()
        print("\nError: You must provide either a local video path or a YouTube URL.")
        return 1
    
    # Get API key from environment
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set.")
        print("Please create a .env file with your Gemini API key.")
        return 1
    
    print("Starting pipeline demonstration...")
    print("Stage 1: Creating video metadata...")

    # Create initial state
    if args.video:
        video_path = args.video
        print(f"Analyzing local video: {video_path}")
        
        # Create VideoMetadata from file
        metadata = VideoMetadata.from_file(video_path)
        
        # Set up initial state
        state = WorkflowState(input_video=metadata)
        state.add_log_entry("initialized", {"video_path": video_path})
        
    elif args.youtube:
        print(f"Analyzing YouTube video: {args.youtube}")
        
        # For YouTube, we'll create a simplified metadata
        metadata = VideoMetadata(file_path=args.youtube, title="YouTube Video")
        
        # Set up initial state
        state = WorkflowState(input_video=metadata)
        state.add_log_entry("initialized", {"youtube_url": args.youtube})
    
    # Stage 1: Video Analysis
    print("\nStage 2: Analyzing video content...")
    
    # Prepare input for video analysis agent
    agent_input = {
        "api_key": api_key,
        "video_path": args.video if args.video else None,
        "youtube_url": args.youtube if args.youtube else None
    }
    
    # Run video analysis agent
    analysis_result = video_analysis_agent(agent_input)
    
    # Check for errors
    if "error" in analysis_result and analysis_result["error"]:
        print(f"Error during video analysis: {analysis_result['error']}")
        return 1
    
    # Get identified moments from result
    moments = analysis_result.get("moments", [])
    
    # Update state with identified moments
    state.identified_moments = moments
    state.add_log_entry("video_analyzed", {"moments_count": len(moments)})
    
    print(f"Identified {len(moments)} interesting moments in the video:")
    for i, moment in enumerate(moments, 1):
        print(f"  Moment {i}: {moment.start_time_str} - {moment.end_time_str} ({moment.duration:.1f}s)")
        print(f"    Description: {moment.description}")
    
    # Stage 2: Moment Selection
    print("\nStage 3: Selecting the best moments...")
    
    # Prepare input for moment selection agent
    selection_input = {
        "identified_moments": moments
    }
    
    # Run moment selection agent
    selection_result = moment_selection_agent(selection_input)
    
    # Check for errors
    if "error" in selection_result and selection_result["error"]:
        print(f"Error during moment selection: {selection_result['error']}")
        return 1
    
    # Get selected moments from result
    selected_moments = selection_result.get("selected_moments", [])
    
    # Update state with selected moments
    state.selected_moments = selected_moments
    state.add_log_entry("moments_selected", {"selected_count": len(selected_moments)})
    
    # Display results
    print(f"\nSelected {len(selected_moments)} moments for content creation:")
    for i, moment in enumerate(selected_moments, 1):
        print(f"\nSelected Moment {i}: {moment.start_time_str} - {moment.end_time_str} ({moment.duration:.1f}s)")
        print(f"  Description: {moment.description}")
        print(f"  Selection Reason: {moment.selection_reason}")
        print(f"  Engagement Prediction: {moment.engagement_prediction:.2f}")
        print(f"  Content Category: {moment.content_category}")
        print(f"  Target Platforms: {', '.join(moment.target_platforms)}")
    
    print("\nPipeline demonstration completed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main()) 