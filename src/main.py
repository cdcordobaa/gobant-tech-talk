#!/usr/bin/env python3
"""
Simple demonstration of the video analysis pipeline with LangGraph.
"""

import os
import sys
import argparse
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.basic_pipeline import run_pipeline
from src.visualization.report import extract_thumbnails, display_analysis_results


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
    
    return parser.parse_args()


def main():
    """Run the video analysis pipeline with optional report generation."""
    # Parse command line arguments
    args = parse_arguments()
    
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
    
    print(f"Analyzing video: {video_path}")
    
    # Run the pipeline
    result = run_pipeline(video_path, api_key)
    
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