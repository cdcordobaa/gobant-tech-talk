"""State models for workflow data processing."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any, ClassVar
import os

from pydantic import BaseModel, Field, field_validator, model_validator
import ffmpeg
from dataclasses import dataclass, field
from PIL import Image

from src.tools.video_utils import extract_video_metadata, validate_video_file


class VideoMetadata(BaseModel):
    """Metadata for a video file including technical details."""
    
    file_path: str
    title: Optional[str] = None
    duration: Optional[float] = None  # in seconds
    dimensions: Optional[Tuple[int, int]] = None  # (width, height)
    creation_date: Optional[datetime] = None
    
    @field_validator('file_path')
    @classmethod
    def validate_file_exists(cls, v):
        """Ensure the video file exists."""
        if not os.path.isfile(v):
            raise ValueError(f"Video file not found: {v}")
        return v
    
    @model_validator(mode='after')
    def extract_title_from_filename(self):
        """Extract title from filename if not provided."""
        if self.title is None and self.file_path:
            filename = os.path.basename(self.file_path)
            title, _ = os.path.splitext(filename)
            self.title = title
        return self
    
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
    
    @field_validator('end_time')
    @classmethod
    def end_time_must_be_after_start_time(cls, v, info):
        """Ensure end_time is greater than start_time."""
        if 'start_time' in info.data and v <= info.data['start_time']:
            raise ValueError('end_time must be greater than start_time')
        return v
    
    @field_validator('start_time')
    @classmethod
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


@dataclass
class SelectedMoment:
    """Represents a moment selected for potential content creation."""
    start_time: float
    end_time: float
    description: str
    selection_reason: str
    engagement_prediction: float
    content_category: str
    target_platforms: list[str]  # Added from initial selection logic
    frame_paths: List[str] = field(default_factory=list)
    thumbnail_path: Optional[str] = None

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def start_time_str(self) -> str:
        return str(timedelta(seconds=int(self.start_time)))

    @property
    def end_time_str(self) -> str:
        return str(timedelta(seconds=int(self.end_time)))


@dataclass
class PlatformRequirements:
    """Specifies the technical requirements for a specific platform."""
    platform_name: str
    aspect_ratio: str  # e.g., "1:1", "9:16", "16:9"
    max_duration: float  # seconds
    optimal_format: str  # e.g., "square", "vertical", "landscape"
    resolution: tuple[int, int]  # (width, height)


@dataclass
class PlatformContent:
    """Represents a piece of content tailored for a specific platform."""
    platform: str
    source_moment: SelectedMoment
    target_specs: PlatformRequirements
    output_path: Optional[str] = None
    processing_status: str = "pending"  # e.g., pending, formatting_specs_defined, processing, complete, failed
    ffmpeg_params: Optional[dict[str, Any]] = None # To store cropping, resizing params etc.
    preview_thumbnail_path: Optional[str] = None # Path for formatted preview


# Define platform constants
PLATFORM_INSTAGRAM = "Instagram"
PLATFORM_TIKTOK = "TikTok"
PLATFORM_LINKEDIN = "LinkedIn"

SUPPORTED_PLATFORMS = [PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_LINKEDIN]


@dataclass
class WorkflowState:
    """Represents the state of the video analysis workflow."""
    video_path: str
    api_key: str # Added API Key to state
    frames_dir: Optional[str] = None
    frame_paths: List[str] = field(default_factory=list)
    frame_analysis: List[dict] = field(default_factory=list) # Analysis per frame
    analysis_summary: Optional[str] = None
    moments: List[VideoMoment] = field(default_factory=list) # Initially identified moments
    selected_moments: List[SelectedMoment] = field(default_factory=list) # Moments selected for content creation
    platform_content: Dict[str, List[PlatformContent]] = field(default_factory=lambda: {p: [] for p in SUPPORTED_PLATFORMS}) # Content formatted per platform
    report_path: Optional[str] = None
    error: Optional[str] = None
    current_stage: Optional[str] = None # Name of the current stage running
    stages_completed: List[str] = field(default_factory=list) # Names of stages completed
    checkpoint_data: Dict[str, Any] = field(default_factory=dict) # Data to save/load from checkpoint

    def update_checkpoint(self):
        """Prepares data for checkpointing."""
        # Exclude non-serializable or large data if necessary
        self.checkpoint_data = {
            "video_path": self.video_path,
            "frames_dir": self.frames_dir,
            "frame_paths": self.frame_paths,
            "frame_analysis": self.frame_analysis, # Consider if this gets too large
            "analysis_summary": self.analysis_summary,
            "moments": [m.__dict__ for m in self.moments],
            "selected_moments": [sm.__dict__ for sm in self.selected_moments],
            # Use __dict__ for now, assuming nested dataclasses are serializable enough for checkpoint
            "platform_content": {p: [pc.__dict__ for pc in pcs] for p, pcs in self.platform_content.items()},
            "report_path": self.report_path,
            "current_stage": self.current_stage,
            "stages_completed": self.stages_completed,
            # Don't save api_key in checkpoint for security
        }

    @classmethod
    def from_checkpoint(cls, data: Dict[str, Any]) -> 'WorkflowState':
        """Creates WorkflowState from checkpoint data."""
        # API key should be re-injected after loading, not loaded from checkpoint
        state = cls(video_path=data.get("video_path"), api_key="") # Initialize with empty key
        state.frames_dir = data.get("frames_dir")
        state.frame_paths = data.get("frame_paths", [])
        state.frame_analysis = data.get("frame_analysis", [])
        state.analysis_summary = data.get("analysis_summary")
        state.moments = [VideoMoment(**m) for m in data.get("moments", [])]
        state.selected_moments = [SelectedMoment(**sm) for sm in data.get("selected_moments", [])]

        # Reconstruct platform_content carefully
        raw_platform_content = data.get("platform_content", {})
        platform_content = {p: [] for p in SUPPORTED_PLATFORMS}
        for platform, content_list in raw_platform_content.items():
             if platform in platform_content:
                 for content_data in content_list:
                     # Reconstruct nested objects
                     source_moment_data = content_data.pop("source_moment", {})
                     target_specs_data = content_data.pop("target_specs", {})
                     if source_moment_data and target_specs_data:
                         # Ensure nested dataclasses are reconstructed if needed
                         content_data["source_moment"] = SelectedMoment(**source_moment_data)
                         content_data["target_specs"] = PlatformRequirements(**target_specs_data)
                         platform_content[platform].append(PlatformContent(**content_data))
                     else:
                         print(f"Warning: Skipping platform content reconstruction due to missing data: {content_data}")
                         
        state.platform_content = platform_content

        state.report_path = data.get("report_path")
        state.current_stage = data.get("current_stage")
        state.stages_completed = data.get("stages_completed", [])
        # Store the loaded data itself in checkpoint_data for potential reuse/inspection
        state.checkpoint_data = data
        return state 