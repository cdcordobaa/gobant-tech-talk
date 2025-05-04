"""State models for workflow data processing."""

from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, ClassVar
import os

from pydantic import BaseModel, Field, validator, root_validator
import ffmpeg

from src.tools.video_utils import extract_video_metadata, validate_video_file


class VideoMetadata(BaseModel):
    """Metadata for a video file including technical details."""
    
    file_path: str
    title: Optional[str] = None
    duration: Optional[float] = None  # in seconds
    dimensions: Optional[Tuple[int, int]] = None  # (width, height)
    creation_date: Optional[datetime] = None
    
    @validator('file_path')
    def validate_file_exists(cls, v):
        """Ensure the video file exists."""
        if not os.path.isfile(v):
            raise ValueError(f"Video file not found: {v}")
        return v
    
    @root_validator(skip_on_failure=True)
    def extract_title_from_filename(cls, values):
        """Extract title from filename if not provided."""
        if values.get('title') is None and values.get('file_path'):
            filename = os.path.basename(values['file_path'])
            title, _ = os.path.splitext(filename)
            values['title'] = title
        return values
    
    @classmethod
    def from_file(cls, file_path: str) -> 'VideoMetadata':
        """Create VideoMetadata by extracting information from a video file."""
        validate_video_file(file_path)
        metadata = extract_video_metadata(file_path)
        
        return cls(
            file_path=file_path,
            duration=metadata.get('duration'),
            dimensions=metadata.get('dimensions'),
            creation_date=metadata.get('creation_date')
        )


class VideoMoment(BaseModel):
    """A specific moment or clip within a video."""
    
    start_time: float  # seconds from video start
    end_time: float  # seconds from video start
    description: str
    engagement_score: float = 0.0
    
    @validator('end_time')
    def end_time_must_be_after_start_time(cls, v, values):
        """Ensure end_time is greater than start_time."""
        if 'start_time' in values and v <= values['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v
    
    @validator('start_time')
    def start_time_must_be_positive(cls, v):
        """Ensure start_time is positive."""
        if v < 0:
            raise ValueError('start_time must be greater than or equal to 0')
        return v
    
    @property
    def start_time_str(self) -> str:
        """Format start time as MM:SS string."""
        minutes = int(self.start_time // 60)
        seconds = int(self.start_time % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def end_time_str(self) -> str:
        """Format end time as MM:SS string."""
        minutes = int(self.end_time // 60)
        seconds = int(self.end_time % 60)
        return f"{minutes:02d}:{seconds:02d}"
    
    @property
    def duration(self) -> float:
        """Get the duration of this moment in seconds."""
        return self.end_time - self.start_time


class WorkflowState(BaseModel):
    """Main workflow state tracking all processing steps and data."""
    
    input_video: VideoMetadata
    identified_moments: List[VideoMoment] = Field(default_factory=list)
    status: str = "initialized"
    errors: List[str] = Field(default_factory=list)
    execution_log: List[Dict[str, Any]] = Field(default_factory=list)
    
    def add_log_entry(self, action: str, details: Dict[str, Any] = None) -> None:
        """Add a timestamped log entry to the execution log."""
        if details is None:
            details = {}
            
        entry = {
            "timestamp": datetime.now(),
            "action": action,
            **details
        }
        
        self.execution_log.append(entry) 