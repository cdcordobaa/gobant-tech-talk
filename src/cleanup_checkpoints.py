#!/usr/bin/env python3
"""
Script to clean up checkpoint backup files.
"""

import sys
import os
import argparse
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from src.utils.checkpoint_manager import CheckpointManager

def main():
    """Clean up checkpoint backup files."""
    parser = argparse.ArgumentParser(description="Clean up checkpoint backup files.")
    
    parser.add_argument(
        "--checkpoint-dir",
        default="./checkpoints",
        help="Directory containing checkpoint files (default: './checkpoints')"
    )
    
    parser.add_argument(
        "--max-backups",
        type=int,
        default=1,
        help="Maximum number of backup files to keep per checkpoint (default: 1)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    # Ensure the checkpoint directory exists
    checkpoint_dir = Path(args.checkpoint_dir)
    if not checkpoint_dir.exists():
        logging.error(f"Checkpoint directory not found: {checkpoint_dir}")
        return
    
    # Count files before cleanup
    backup_files_before = list(checkpoint_dir.glob("*_backup_*.json"))
    reset_files_before = list(checkpoint_dir.glob("*_reset_*.json"))
    total_before = len(backup_files_before) + len(reset_files_before)
    
    logging.info(f"Found {len(backup_files_before)} backup files and {len(reset_files_before)} reset files")
    
    # Perform cleanup
    logging.info(f"Cleaning up checkpoint files, keeping max {args.max_backups} backups per checkpoint...")
    CheckpointManager.cleanup_all_backups(str(checkpoint_dir), args.max_backups)
    
    # Count files after cleanup
    backup_files_after = list(checkpoint_dir.glob("*_backup_*.json"))
    reset_files_after = list(checkpoint_dir.glob("*_reset_*.json"))
    total_after = len(backup_files_after) + len(reset_files_after)
    
    # Report results
    removed_count = total_before - total_after
    logging.info(f"Cleanup complete! Removed {removed_count} files")
    logging.info(f"Remaining: {len(backup_files_after)} backup files and {len(reset_files_after)} reset files")

if __name__ == "__main__":
    main() 