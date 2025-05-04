#!/usr/bin/env python3
"""
Demonstration of social media automation system core functionality.
"""

import argparse
import os
import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.models.state import VideoMetadata, VideoMoment, WorkflowState
from src.tools.video_utils import extract_thumbnail


def main():
    """Process a video file and demonstrate the workflow state functionality."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Demo for social media automation system")
    parser.add_argument("video_path", help="Path to the video file to process")
    args = parser.parse_args()
    
    # Validate and process the video file
    try:
        print(f"Processing video: {args.video_path}")
        
        # Create VideoMetadata with extracted data
        video_metadata = VideoMetadata.from_file(args.video_path)
        print(f"\nVideo Metadata:")
        print(f"  Title: {video_metadata.title}")
        print(f"  Duration: {video_metadata.duration:.2f} seconds")
        print(f"  Dimensions: {video_metadata.dimensions[0]}x{video_metadata.dimensions[1]}")
        if video_metadata.creation_date:
            print(f"  Creation Date: {video_metadata.creation_date}")
        
        # Create a sample VideoMoment
        # Choose a moment from 10-20% of the way through the video
        start_time = video_metadata.duration * 0.1
        end_time = video_metadata.duration * 0.2
        
        moment = VideoMoment(
            start_time=start_time,
            end_time=end_time,
            description="Sample interesting moment in the video",
            engagement_score=0.75
        )
        
        print(f"\nSample Video Moment:")
        print(f"  Timeframe: {moment.start_time_str} - {moment.end_time_str}")
        print(f"  Duration: {moment.duration:.2f} seconds")
        print(f"  Description: {moment.description}")
        print(f"  Engagement Score: {moment.engagement_score}")
        
        # Create a WorkflowState with the video and moment
        workflow = WorkflowState(
            input_video=video_metadata,
            identified_moments=[moment],
            status="demo"
        )
        
        # Add some log entries
        workflow.add_log_entry("video_loaded", {"file_path": args.video_path})
        workflow.add_log_entry("moment_identified", {"start": moment.start_time, "end": moment.end_time})
        
        print(f"\nWorkflow State:")
        print(f"  Status: {workflow.status}")
        print(f"  Video: {workflow.input_video.title}")
        print(f"  Moments identified: {len(workflow.identified_moments)}")
        print(f"  Log entries: {len(workflow.execution_log)}")
        
        # Extract and save a thumbnail from the sample moment
        # Use the middle of the moment for the thumbnail
        thumbnail_time = (moment.start_time + moment.end_time) / 2
        thumbnail_path = extract_thumbnail(args.video_path, thumbnail_time)
        
        print(f"\nExtracted thumbnail at {thumbnail_time:.2f}s and saved to:")
        print(f"  {thumbnail_path}")
        
        workflow.add_log_entry("thumbnail_extracted", {"path": thumbnail_path, "time": thumbnail_time})
        
        print("\nDemo completed successfully!")
        
    except ValueError as e:
        print(f"Error: {e}")
        return 1
        
    return 0


if __name__ == "__main__":
    sys.exit(main()) 