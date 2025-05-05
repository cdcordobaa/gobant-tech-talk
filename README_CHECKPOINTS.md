# Video Analysis Pipeline with Checkpoint Support

This project implements a robust checkpointing system for a multi-stage video processing pipeline. The system allows for resuming processing from specific points, saving state after completing each stage.

## Features

- **Video-Specific Checkpoints**: Separate checkpoint files for each video processed
- **Named Stages**: Stages are identified by both index and name in checkpoint files
- **Detailed Stage Data**: All stage-specific data preserved for resumption
- **Atomic Writes**: Prevents file corruption with atomic file operations
- **Error Tracking**: Records errors with timestamps for debugging

## Usage

### Command Line Arguments

The pipeline supports the following checkpoint-related arguments:

```
--checkpoint-dir DIR    Directory to store checkpoint files (default: 'checkpoints')
--restart               Continue from the last successful stage
--stage N               Start from a specific stage (0-3)
--reset                 Clear checkpoint data and start fresh
--list-checkpoints      Display saved checkpoint information and exit
--use-langgraph         Use LangGraph for analysis (combines analyze_frames and detect_moments)
```

### Examples

#### Run the pipeline normally

```bash
python src/main.py input_videos/sample.mp4
```

#### Resume from last checkpoint

```bash
python src/main.py input_videos/sample.mp4 --restart
```

#### Start from a specific stage

```bash
python src/main.py input_videos/sample.mp4 --stage 3
```

#### Clear all checkpoints and start fresh

```bash
python src/main.py input_videos/sample.mp4 --reset
```

#### View all checkpoints

```bash
python src/main.py --list-checkpoints
```

## Pipeline Stages

The pipeline consists of the following stages:

1. **Extract Frames** (Stage 0): Extracts key frames from the video
2. **Analyze Frames** (Stage 1): Analyzes the extracted frames
3. **Detect Moments** (Stage 2): Identifies interesting moments from the analysis
4. **Generate Report** (Stage 3): Creates a final report with findings

### LangGraph Mode

When using the `--use-langgraph` option, the pipeline's behavior changes:

- Stage 1 uses LangGraph for frame analysis
- LangGraph directly identifies interesting moments
- Stage 2 is automatically skipped/marked as complete
- The final report still processes normally

## Checkpoint Structure

Checkpoints are stored as JSON files with the following structure:

```json
{
    "video_path": "input_videos/sample.mp4",  // Path to the video file
    "current_stage": 2,                      // Integer index of the next stage to run
    "stages_completed": [0, 1],              // List of completed stage indexes
    "stage_names": {                         // Mapping of stage indices to names
        "0": {"name": "extract_frames", "description": "Extract key frames from video"},
        "1": {"name": "analyze_frames", "description": "Analyze extracted frames"}
    },
    "data": {                                // Stage-specific data dictionary
        "0": {"frames": ["frame_0.jpg", ...]},
        "1": {"analysis_results": {...}}
    },
    "metadata": {                            // Additional metadata
        "start_time": 1623456789,            // When the process started
        "last_updated": 1623457000,          // When the checkpoint was last updated
        "version": "1.0"                     // Checkpoint format version
    },
    "errors": []                             // Error history
}
```

## Implementation Details

### CheckpointManager Class

The core functionality is provided by the `CheckpointManager` class, which handles:

- Creating video-specific checkpoint files
- Loading and saving checkpoint data
- Tracking stage completion with named stages
- Managing stage data
- Error recording and recovery

### Integrating New Stages

To add a new stage to the pipeline:

1. Add a new stage constant in `src/workflows/pipeline.py`
2. Add it to the `create_pipeline` and `register_pipeline_stages` functions
3. Implement the stage function with checkpoint support
4. Update the CLI arguments in `main.py` if needed 