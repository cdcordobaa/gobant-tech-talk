#!/usr/bin/env python3
"""
Checkpoint manager for resumable processing pipelines.
"""

import os
import json
import time
import shutil
import logging
import hashlib
import glob
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

class CheckpointManager:
    """Manages checkpoint data for resumable processing pipelines."""
    
    def __init__(self, 
                 checkpoint_dir: str = "./checkpoints", 
                 checkpoint_file: Optional[str] = None,
                 video_path: Optional[str] = None,
                 max_backups: int = 1):
        """
        Initialize checkpoint manager.
        
        Args:
            checkpoint_dir: Directory to store checkpoint files
            checkpoint_file: Optional name of the checkpoint file (if not provided, will be derived from video_path)
            video_path: Optional path to the video file being processed (used to generate checkpoint filename)
            max_backups: Maximum number of backup files to keep per checkpoint (default: 1)
        """
        self.checkpoint_dir = Path(checkpoint_dir)
        self.max_backups = max_backups
        
        # If video_path is provided, use it to create a unique checkpoint file name
        if video_path and not checkpoint_file:
            video_name = Path(video_path).stem
            # Create a safe filename by removing any problematic characters
            safe_name = ''.join(c if c.isalnum() or c in '._- ' else '_' for c in video_name)
            self.checkpoint_file = f"checkpoint_{safe_name}.json"
        else:
            # Fall back to default or provided checkpoint file
            self.checkpoint_file = checkpoint_file or "checkpoint.json"
        
        self.checkpoint_path = self.checkpoint_dir / self.checkpoint_file
        self.video_path = video_path
        
        # Create checkpoint directory if it doesn't exist
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize or load checkpoint data
        self.data = self._load_or_create()
        
        # Stage name mapping (will be populated when stages are registered)
        self.stage_names = {}
    
    def _load_or_create(self) -> Dict[str, Any]:
        """Load existing checkpoint or create a new one."""
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, 'r') as f:
                    checkpoint_data = json.load(f)
                    
                    # Add video_path to checkpoint if not present
                    if self.video_path and "video_path" not in checkpoint_data:
                        checkpoint_data["video_path"] = self.video_path
                    
                    # Restore stage name mapping if present
                    if "stage_names" in checkpoint_data:
                        self.stage_names = checkpoint_data["stage_names"]
                        
                    return checkpoint_data
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Failed to load checkpoint {self.checkpoint_path}: {e}")
                # Fall back to creating a new checkpoint
        
        # Default checkpoint structure
        return {
            "video_path": self.video_path,
            "current_stage": 0,
            "stages_completed": [],
            "stage_names": {},
            "data": {},
            "metadata": {
                "start_time": int(time.time()),
                "last_updated": int(time.time()),
                "version": "1.0"
            },
            "errors": []
        }
    
    def _cleanup_old_backups(self):
        """Remove old backup files, keeping only the most recent ones."""
        backup_pattern = f"{self.checkpoint_path.stem}_backup_*.json"
        backup_files = sorted(
            self.checkpoint_dir.glob(backup_pattern),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        # Keep only the most recent backups
        if len(backup_files) > self.max_backups:
            for old_file in backup_files[self.max_backups:]:
                try:
                    old_file.unlink()
                    logging.debug(f"Removed old backup: {old_file}")
                except OSError as e:
                    logging.warning(f"Failed to remove old backup {old_file}: {e}")
    
    def register_stages(self, stages: List[Tuple[int, str, str]]) -> None:
        """
        Register all stages with the checkpoint manager.
        
        Args:
            stages: List of tuples containing (stage_index, stage_name, stage_description)
        """
        stage_names = {}
        for stage_index, stage_name, stage_description in stages:
            stage_names[str(stage_index)] = {
                "name": stage_name,
                "description": stage_description
            }
        
        self.stage_names = stage_names
        self.data["stage_names"] = stage_names
        self.save()
    
    def save(self, create_backup: bool = True) -> None:
        """
        Save checkpoint data to file.
        
        Args:
            create_backup: Whether to create a backup of the previous checkpoint
        """
        # Update timestamp
        self.data["metadata"]["last_updated"] = int(time.time())
        
        # Ensure stage names are in the data
        if self.stage_names and "stage_names" not in self.data:
            self.data["stage_names"] = self.stage_names
        
        # Create temp file for atomic write
        temp_path = self.checkpoint_path.with_suffix('.tmp')
        
        try:
            # Write to temp file first
            with open(temp_path, 'w') as f:
                json.dump(self.data, f, indent=2)
            
            # Create backup if requested and previous file exists
            if create_backup and self.checkpoint_path.exists():
                backup_path = self.checkpoint_dir / f"{self.checkpoint_path.stem}_backup_{int(time.time())}.json"
                shutil.copy2(self.checkpoint_path, backup_path)
                # Clean up old backups
                self._cleanup_old_backups()
            
            # Perform atomic replacement
            os.replace(temp_path, self.checkpoint_path)
        
        except IOError as e:
            if temp_path.exists():
                temp_path.unlink()
            logging.error(f"Failed to save checkpoint: {e}")
            raise
    
    def mark_stage_complete(self, stage_index: int, stage_name: str, 
                           stage_data: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark a stage as complete and store its data.
        
        Args:
            stage_index: Index of the stage
            stage_name: Name of the stage
            stage_data: Data to store for this stage
        """
        # Record stage name if not already in mapping
        if str(stage_index) not in self.stage_names:
            self.stage_names[str(stage_index)] = {"name": stage_name, "description": ""}
            self.data["stage_names"] = self.stage_names
        
        # Mark stage as completed
        if stage_index not in self.data["stages_completed"]:
            self.data["stages_completed"].append(stage_index)
        
        # Sort to ensure ordering
        self.data["stages_completed"].sort()
        
        # Update current stage to next
        self.data["current_stage"] = stage_index + 1
        
        # Store stage data if provided
        if stage_data:
            if "data" not in self.data:
                self.data["data"] = {}
            self.data["data"][str(stage_index)] = stage_data
        
        # Save changes
        self.save()
    
    def is_stage_completed(self, stage_index: int) -> bool:
        """
        Check if a stage has been completed.
        
        Args:
            stage_index: Index of the stage to check
            
        Returns:
            True if the stage has been completed, False otherwise
        """
        return stage_index in self.data["stages_completed"]
    
    def get_stage_data(self, stage_index: int) -> Optional[Dict[str, Any]]:
        """
        Get data from a specific stage.
        
        Args:
            stage_index: Index of the stage
            
        Returns:
            Stage data or None if not found
        """
        return self.data.get("data", {}).get(str(stage_index))
    
    def get_stage_name(self, stage_index: int) -> str:
        """
        Get the name of a stage.
        
        Args:
            stage_index: Index of the stage
            
        Returns:
            Stage name or "Unknown Stage" if not found
        """
        stage_info = self.stage_names.get(str(stage_index), {})
        return stage_info.get("name", f"Stage {stage_index}")
    
    def reset(self) -> None:
        """Clear checkpoint data and create new empty checkpoint."""
        # Create backup of current state
        if self.checkpoint_path.exists():
            backup_path = self.checkpoint_dir / f"{self.checkpoint_path.stem}_reset_{int(time.time())}.json"
            shutil.copy2(self.checkpoint_path, backup_path)
            # Clean up excess reset backups
            self._cleanup_reset_backups()
        
        # Keep stage names from previous checkpoint
        stage_names = self.stage_names.copy() if hasattr(self, 'stage_names') else {}
        
        # Reset to initial state
        self.data = {
            "video_path": self.video_path,
            "current_stage": 0,
            "stages_completed": [],
            "stage_names": stage_names,
            "data": {},
            "metadata": {
                "start_time": int(time.time()),
                "last_updated": int(time.time()),
                "version": "1.0"
            },
            "errors": []
        }
        
        # Save the reset state
        self.save(create_backup=False)
    
    def _cleanup_reset_backups(self):
        """Remove old reset backup files, keeping only the most recent ones."""
        reset_pattern = f"{self.checkpoint_path.stem}_reset_*.json"
        reset_files = sorted(
            self.checkpoint_dir.glob(reset_pattern),
            key=lambda f: f.stat().st_mtime,
            reverse=True
        )
        
        # Keep only the 2 most recent reset backups
        if len(reset_files) > 2:
            for old_file in reset_files[2:]:
                try:
                    old_file.unlink()
                    logging.debug(f"Removed old reset backup: {old_file}")
                except OSError as e:
                    logging.warning(f"Failed to remove old reset backup {old_file}: {e}")
    
    def add_error(self, stage_index: int, stage_name: str, 
                 error_msg: str, recovered: bool = False) -> None:
        """
        Record error information.
        
        Args:
            stage_index: Index of the stage where error occurred
            stage_name: Name of the stage
            error_msg: Error message
            recovered: Whether the error was recovered from
        """
        error_info = {
            "stage": stage_index,
            "stage_name": stage_name,
            "timestamp": int(time.time()),
            "message": error_msg,
            "was_recovered": recovered
        }
        
        if "errors" not in self.data:
            self.data["errors"] = []
        
        self.data["errors"].append(error_info)
        self.save()
    
    def get_next_stage(self) -> int:
        """
        Get the next stage to execute.
        
        Returns:
            Index of the next stage to run
        """
        return self.data["current_stage"]
    
    def list_checkpoints(self) -> Dict[str, Any]:
        """
        Get checkpoint status information.
        
        Returns:
            Dictionary with checkpoint information
        """
        # Get all backup files for this checkpoint
        backup_pattern = f"{self.checkpoint_path.stem}_backup_*.json"
        backup_files = list(self.checkpoint_dir.glob(backup_pattern))
        
        # Stage information with names
        stages_completed = []
        for stage_idx in self.data["stages_completed"]:
            stage_name = self.get_stage_name(stage_idx)
            stages_completed.append(f"{stage_idx} ({stage_name})")
        
        # Current checkpoint summary
        summary = {
            "video_path": self.data.get("video_path", "unknown"),
            "checkpoint_file": self.checkpoint_file,
            "current_stage": self.data["current_stage"],
            "current_stage_name": self.get_stage_name(self.data["current_stage"]),
            "stages_completed": stages_completed,
            "start_time": self.data["metadata"]["start_time"],
            "last_updated": self.data["metadata"]["last_updated"],
            "error_count": len(self.data.get("errors", [])),
            "backup_files": [f.name for f in backup_files]
        }
        
        return summary
    
    @classmethod
    def list_all_checkpoints(cls, checkpoint_dir: str = "./checkpoints") -> List[Dict[str, Any]]:
        """
        List all checkpoint files and their basic information.
        
        Args:
            checkpoint_dir: Directory containing checkpoint files
            
        Returns:
            List of dictionaries with checkpoint information
        """
        checkpoint_dir_path = Path(checkpoint_dir)
        if not checkpoint_dir_path.exists():
            return []
        
        checkpoints = []
        
        # Find all checkpoint files, but exclude backup and reset files
        for checkpoint_file in checkpoint_dir_path.glob("checkpoint_*.json"):
            if '_backup_' in checkpoint_file.name or '_reset_' in checkpoint_file.name:
                continue  # Skip backup files
            
            try:
                with open(checkpoint_file, 'r') as f:
                    data = json.load(f)
                
                # Get stage names
                stage_names = data.get("stage_names", {})
                
                # Format completed stages with names
                formatted_stages = []
                for stage_idx in data.get("stages_completed", []):
                    stage_info = stage_names.get(str(stage_idx), {})
                    stage_name = stage_info.get("name", f"Stage {stage_idx}")
                    formatted_stages.append(f"{stage_idx} ({stage_name})")
                
                # Get current stage name
                current_stage = data.get("current_stage", 0)
                current_stage_info = stage_names.get(str(current_stage), {})
                current_stage_name = current_stage_info.get("name", f"Stage {current_stage}")
                
                # Extract basic information
                checkpoint_info = {
                    "file": checkpoint_file.name,
                    "video_path": data.get("video_path", "unknown"),
                    "current_stage": current_stage,
                    "current_stage_name": current_stage_name,
                    "stages_completed": formatted_stages,
                    "raw_stages_completed": data.get("stages_completed", []),
                    "last_updated": data.get("metadata", {}).get("last_updated", 0)
                }
                
                checkpoints.append(checkpoint_info)
            except (json.JSONDecodeError, IOError):
                # Skip invalid checkpoint files
                continue
        
        # Sort by last updated time
        checkpoints.sort(key=lambda x: x["last_updated"], reverse=True)
        
        return checkpoints
    
    @classmethod
    def cleanup_all_backups(cls, checkpoint_dir: str = "./checkpoints", max_backups_per_file: int = 5):
        """
        Clean up backup files across the entire checkpoint directory.
        
        Args:
            checkpoint_dir: Directory containing checkpoint files
            max_backups_per_file: Maximum number of backups to keep per checkpoint file
        """
        checkpoint_dir_path = Path(checkpoint_dir)
        if not checkpoint_dir_path.exists():
            return
        
        # Find all main checkpoint files
        main_checkpoints = []
        for checkpoint_file in checkpoint_dir_path.glob("checkpoint_*.json"):
            if '_backup_' not in checkpoint_file.name and '_reset_' not in checkpoint_file.name:
                main_checkpoints.append(checkpoint_file.stem)
        
        # Clean up backups for each main checkpoint
        for checkpoint_stem in main_checkpoints:
            backup_pattern = f"{checkpoint_stem}_backup_*.json"
            backup_files = sorted(
                checkpoint_dir_path.glob(backup_pattern),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            # Keep only the most recent backups
            if len(backup_files) > max_backups_per_file:
                for old_file in backup_files[max_backups_per_file:]:
                    try:
                        old_file.unlink()
                        logging.debug(f"Removed old backup: {old_file}")
                    except OSError as e:
                        logging.warning(f"Failed to remove old backup {old_file}: {e}")
            
            # Also clean up reset backups
            reset_pattern = f"{checkpoint_stem}_reset_*.json"
            reset_files = sorted(
                checkpoint_dir_path.glob(reset_pattern),
                key=lambda f: f.stat().st_mtime,
                reverse=True
            )
            
            # Keep only the 2 most recent reset backups
            if len(reset_files) > 2:
                for old_file in reset_files[2:]:
                    try:
                        old_file.unlink()
                        logging.debug(f"Removed old reset backup: {old_file}")
                    except OSError as e:
                        logging.warning(f"Failed to remove old reset backup {old_file}: {e}") 