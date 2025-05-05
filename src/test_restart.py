#!/usr/bin/env python3
"""
Script to test restart functionality by running only part of the pipeline.
"""

import os
import sys
import logging
import time
from pathlib import Path
import json

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.workflows.pipeline import run_pipeline, STAGE_EXTRACT_FRAMES, STAGE_ANALYZE_FRAMES, extract_frames
from src.utils.checkpoint_manager import CheckpointManager
from src.models.state import VideoMoment

# Configure logging
logging.basicConfig(level=logging.INFO)

# Path to test video
VIDEO_PATH = "input_videos/El Año en que la IA Redefinió Límites.mp4"
CHECKPOINT_DIR = "./checkpoints"

def display_checkpoint_status(checkpoint_mgr):
    """Display the current status of the checkpoint from the actual file."""
    # Get the raw data from the checkpoint file to ensure we're seeing the latest state
    checkpoint_path = checkpoint_mgr.checkpoint_path
    try:
        with open(checkpoint_path, 'r') as f:
            data = json.load(f)
            
        # Get stage names for more readable output
        stage_names = data.get("stage_names", {})
        
        # Format completed stages with names
        completed_stages = []
        for stage_idx in data.get("stages_completed", []):
            stage_info = stage_names.get(str(stage_idx), {})
            stage_name = stage_info.get("name", f"Stage {stage_idx}")
            completed_stages.append(f"{stage_idx} ({stage_name})")
            
        # Get current stage name
        current_stage = data.get("current_stage", 0)
        current_stage_info = stage_names.get(str(current_stage), {})
        current_stage_name = current_stage_info.get("name", f"Stage {current_stage}")
        
        print(f"  Checkpoint file: {checkpoint_path.name}")
        print(f"  Current stage: {current_stage} ({current_stage_name})")
        print(f"  Stages completed: {', '.join(completed_stages) if completed_stages else 'None'}")
        print(f"  Last updated: {data['metadata']['last_updated']}")
        
    except (json.JSONDecodeError, IOError, KeyError) as e:
        print(f"  Error reading checkpoint: {e}")

def test_part1():
    """Run only the first stage of the pipeline (extract_frames)."""
    print(f"Testing partial run up to stage 1 for: {VIDEO_PATH}")
    
    # Initialize checkpoint manager and reset
    checkpoint_mgr = CheckpointManager(CHECKPOINT_DIR, video_path=VIDEO_PATH)
    checkpoint_mgr.reset()
    print(f"Checkpoint reset completed for file: {checkpoint_mgr.checkpoint_file}")
    
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY", "dummy-key")
    
    # Create initial state
    state = {
        "video_path": VIDEO_PATH,
        "api_key": api_key,
        "moments": [],
        "error": None,
        "frames_extracted": None,
        "analysis_results": None,
        "report_path": None
    }
    
    # Manually run just the extract_frames stage
    print("\nRunning extract_frames stage...")
    state = extract_frames(state, checkpoint_mgr)
    
    # Check current checkpoint status
    print("\nCheckpoint status after partial run:")
    display_checkpoint_status(checkpoint_mgr)
    
    print("\nNow you can run the restart test using:")
    print(f"python src/test_restart.py restart")
    print("This will continue from where we left off.")

def test_restart():
    """Test restarting the pipeline from last successful stage."""
    print(f"Testing pipeline restart for: {VIDEO_PATH}")
    
    # Get API key from environment
    api_key = os.environ.get("GEMINI_API_KEY", "dummy-key")
    
    # Initialize checkpoint manager (no reset)
    checkpoint_mgr = CheckpointManager(CHECKPOINT_DIR, video_path=VIDEO_PATH)
    
    # Check current checkpoint before restart
    print("\nCheckpoint status before restart:")
    display_checkpoint_status(checkpoint_mgr)
    
    # Run pipeline with restart (no start_stage specified)
    result = run_pipeline(
        video_path=VIDEO_PATH,
        api_key=api_key,
        checkpoint_dir=CHECKPOINT_DIR
    )
    
    # Check if restart worked by verifying final state
    if result.get("error"):
        print(f"Error during restart: {result['error']}")
    else:
        print("\nRestart successful!")
        print(f"Found {len(result['moments'])} interesting moments:")
        for i, moment in enumerate(result['moments']):
            print(f"Moment {i+1}: {moment.start_time:.1f}s to {moment.end_time:.1f}s - {moment.description}")
        
        # Check final checkpoint status
        print("\nFinal checkpoint status:")
        display_checkpoint_status(checkpoint_mgr)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "restart":
        test_restart()
    else:
        test_part1() 