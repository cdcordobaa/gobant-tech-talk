#!/usr/bin/env python3
"""
Simple demonstration of the video analysis pipeline with LangGraph.
"""

import os
import sys
import argparse
from pathlib import Path
import time
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.pipeline import run_pipeline, STAGE_EXTRACT_FRAMES, STAGE_ANALYZE_FRAMES, STAGE_DETECT_MOMENTS, STAGE_GENERATE_REPORT
from src.visualization.report import extract_thumbnails, display_analysis_results
from src.utils.checkpoint_manager import CheckpointManager


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run video analysis pipeline and generate visualization reports."
    )
    
    parser.add_argument(
        "video_path",
        nargs="?",
        default="input_videos/sample.mp4",
        help="Path to the video file to analyze"
    )
    
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip report generation and just output results to console"
    )
    
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to save output files (default: 'output')"
    )
    
    # Checkpoint-related arguments
    parser.add_argument(
        "--checkpoint-dir",
        default="checkpoints",
        help="Directory to store checkpoint files (default: 'checkpoints')"
    )
    
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Continue from the last successful stage"
    )
    
    parser.add_argument(
        "--stage",
        type=int,
        help="Start from a specific stage (0-3)",
        choices=[STAGE_EXTRACT_FRAMES, STAGE_ANALYZE_FRAMES, STAGE_DETECT_MOMENTS, STAGE_GENERATE_REPORT]
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear checkpoint data and start fresh"
    )
    
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="Display saved checkpoint information and exit"
    )
    
    parser.add_argument(
        "--use-langgraph",
        action="store_true",
        help="Use LangGraph for the analysis stage (combines analyze_frames and detect_moments stages)"
    )
    
    parser.add_argument(
        "--max-backups",
        type=int,
        default=1,
        help="Maximum number of backup files to keep per checkpoint (default: 1)"
    )
    
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Just clean up checkpoint backup files and exit"
    )
    
    return parser.parse_args()


def format_timestamp(timestamp):
    """Format a timestamp for display."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def main():
    """Run the video analysis pipeline with checkpoint support and optional report generation."""
    # Parse command line arguments
    args = parse_arguments()
    
    # Create checkpoint directory if needed
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    # Handle --cleanup-only flag
    if args.cleanup_only:
        print(f"Cleaning up checkpoint backup files...")
        CheckpointManager.cleanup_all_backups(str(checkpoint_dir), args.max_backups)
        print("Cleanup complete!")
        sys.exit(0)
    
    # Handle --list-checkpoints
    if args.list_checkpoints:
        checkpoints = CheckpointManager.list_all_checkpoints(checkpoint_dir)
        
        if not checkpoints:
            print(f"No checkpoints found in {checkpoint_dir}")
            sys.exit(0)
        
        print(f"Found {len(checkpoints)} checkpoint(s):")
        print("-" * 80)
        
        for i, checkpoint in enumerate(checkpoints):
            video_path = checkpoint["video_path"] or "unknown"
            print(f"Checkpoint #{i+1}: {checkpoint['file']}")
            print(f"  Video: {video_path}")
            print(f"  Current stage: {checkpoint['current_stage']} ({checkpoint['current_stage_name']})")
            if checkpoint['stages_completed']:
                print(f"  Stages completed: {', '.join(checkpoint['stages_completed'])}")
            else:
                print(f"  Stages completed: None")
            print(f"  Last updated: {format_timestamp(checkpoint['last_updated'])}")
            print("-" * 80)
        
        sys.exit(0)
    
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Check if video exists
    video_path = args.video_path
    if not os.path.exists(video_path):
        print(f"Error: Video file not found: {video_path}")
        print("Usage: python src/main.py [path_to_video]")
        sys.exit(1)
    
    # Get video filename for display
    video_name = Path(video_path).name
    print(f"Analyzing video: {video_name}")
    
    # Initialize checkpoint manager to show which checkpoint file will be used
    checkpoint_mgr = CheckpointManager(checkpoint_dir, video_path=video_path, max_backups=args.max_backups)
    print(f"Using checkpoint file: {checkpoint_mgr.checkpoint_file}")
    
    # Determine starting stage
    start_stage = None
    if args.stage is not None:
        start_stage = args.stage
        stage_name = {
            STAGE_EXTRACT_FRAMES: "extract_frames",
            STAGE_ANALYZE_FRAMES: "analyze_frames",
            STAGE_DETECT_MOMENTS: "detect_moments",
            STAGE_GENERATE_REPORT: "generate_report"
        }.get(start_stage, f"Stage {start_stage}")
        print(f"Starting from stage {start_stage} ({stage_name})")
    elif args.restart:
        next_stage = checkpoint_mgr.get_next_stage()
        next_stage_name = checkpoint_mgr.get_stage_name(next_stage)
        print(f"Resuming from stage {next_stage} ({next_stage_name})")
    
    # Run pipeline with checkpoints
    result = run_pipeline(
        video_path=video_path,
        api_key=api_key,
        checkpoint_dir=str(checkpoint_dir),
        start_stage=start_stage,
        reset=args.reset,
        use_langgraph=args.use_langgraph
    )
    
    # Clean up backup files
    CheckpointManager.cleanup_all_backups(str(checkpoint_dir), args.max_backups)
    
    # Display results
    if "error" in result and result["error"]:
        print(f"Error: {result['error']}")
        sys.exit(1)
    
    # Print analysis results to console
    print(f"Analysis complete. Found {len(result['moments'])} interesting moments:")
    for i, moment in enumerate(result["moments"]):
        print(f"Moment {i+1}: {moment.start_time:.1f}s to {moment.end_time:.1f}s - {moment.description}")
    
    # Skip report generation if requested
    if args.no_report:
        print("Report generation skipped (--no-report flag provided)")
        return
    
    # Extract thumbnails for each moment
    output_thumbnails_dir = Path(args.output_dir) / "thumbnails"
    print(f"Extracting thumbnails to {output_thumbnails_dir}...")
    thumbnails = extract_thumbnails(video_path, result["moments"], output_dir=str(output_thumbnails_dir))
    
    # Display analysis results in HTML report
    print("Generating analysis report...")
    report_path = display_analysis_results(video_path, result, thumbnails)
    print(f"Report generated and opened in browser: {report_path}")


if __name__ == "__main__":
    main() 