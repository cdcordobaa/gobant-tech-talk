#!/usr/bin/env python3
"""
Video analysis pipeline with checkpoint support.
Combines the basic and checkpointed pipeline functionality.
"""

import sys
import logging
import time
from typing import Dict, Any, List, Callable, TypedDict, Optional, Tuple
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from langgraph.graph import StateGraph, START, END
from src.agents.video_analysis import video_analysis_agent
from src.utils.checkpoint_manager import CheckpointManager
from src.models.state import VideoMoment

# Define pipeline stage type
class PipelineStage:
    def __init__(self, 
                 index: int, 
                 name: str, 
                 func: Callable, 
                 description: str = ""):
        self.index = index
        self.name = name
        self.func = func
        self.description = description

# Define the pipeline state schema
class PipelineState(TypedDict):
    video_path: str
    api_key: str
    moments: List[VideoMoment]
    error: Optional[str]
    frames_extracted: Optional[List[str]]
    analysis_results: Optional[Dict[str, Any]]
    report_path: Optional[str]

# Pipeline stage definitions
STAGE_EXTRACT_FRAMES = 0
STAGE_ANALYZE_FRAMES = 1
STAGE_DETECT_MOMENTS = 2
STAGE_GENERATE_REPORT = 3

def create_pipeline(use_langgraph: bool = False) -> List[PipelineStage]:
    """
    Create a pipeline with predefined stages.
    
    Args:
        use_langgraph: Whether to use LangGraph for the analysis stage
        
    Returns:
        List of pipeline stages
    """
    # Define the pipeline stages
    stages = [
        PipelineStage(STAGE_EXTRACT_FRAMES, "extract_frames", extract_frames, 
                     "Extract key frames from video"),
        PipelineStage(STAGE_ANALYZE_FRAMES, "analyze_frames", 
                     analyze_frames_langgraph if use_langgraph else analyze_frames,
                     "Analyze extracted frames"),
        PipelineStage(STAGE_DETECT_MOMENTS, "detect_moments", detect_moments,
                     "Detect interesting moments from analysis"),
        PipelineStage(STAGE_GENERATE_REPORT, "generate_report", generate_report,
                     "Generate final analysis report")
    ]
    
    return stages

def register_pipeline_stages(checkpoint_mgr: CheckpointManager) -> None:
    """
    Register all pipeline stages with the checkpoint manager.
    
    Args:
        checkpoint_mgr: Checkpoint manager instance
    """
    stages = [
        (STAGE_EXTRACT_FRAMES, "extract_frames", "Extract key frames from video"),
        (STAGE_ANALYZE_FRAMES, "analyze_frames", "Analyze extracted frames"),
        (STAGE_DETECT_MOMENTS, "detect_moments", "Detect interesting moments from analysis"),
        (STAGE_GENERATE_REPORT, "generate_report", "Generate final analysis report")
    ]
    
    checkpoint_mgr.register_stages(stages)

def extract_frames(state: PipelineState, checkpoint_mgr: CheckpointManager) -> PipelineState:
    """
    Extract frames from video.
    
    Args:
        state: Current pipeline state
        checkpoint_mgr: Checkpoint manager instance
        
    Returns:
        Updated pipeline state
    """
    logging.info("Extracting frames from video...")
    
    # Simulate extraction
    time.sleep(1)
    
    # Update state with extracted frames (simulated)
    frames = [f"frame_{i}.jpg" for i in range(10)]
    state["frames_extracted"] = frames
    
    # Store data in checkpoint
    stage_data = {"frames": frames}
    checkpoint_mgr.mark_stage_complete(STAGE_EXTRACT_FRAMES, "extract_frames", stage_data)
    
    return state

def analyze_frames(state: PipelineState, checkpoint_mgr: CheckpointManager) -> PipelineState:
    """
    Analyze the extracted frames without using LangGraph.
    
    Args:
        state: Current pipeline state
        checkpoint_mgr: Checkpoint manager instance
        
    Returns:
        Updated pipeline state
    """
    logging.info("Analyzing frames...")
    
    # Get frames from previous stage
    frames = state.get("frames_extracted", [])
    if not frames:
        # Try to get from checkpoint
        stage_data = checkpoint_mgr.get_stage_data(STAGE_EXTRACT_FRAMES)
        if stage_data and "frames" in stage_data:
            frames = stage_data["frames"]
            state["frames_extracted"] = frames
    
    if not frames:
        error_msg = "No frames available for analysis"
        checkpoint_mgr.add_error(STAGE_ANALYZE_FRAMES, "analyze_frames", error_msg)
        state["error"] = error_msg
        return state
    
    # Simulate analysis
    time.sleep(2)
    
    # Update state with analysis results (simulated)
    analysis_results = {
        "detected_objects": ["person", "car", "dog"],
        "scene_types": ["outdoor", "city"],
        "activity_level": "high"
    }
    state["analysis_results"] = analysis_results
    
    # Store data in checkpoint
    stage_data = {"analysis_results": analysis_results}
    checkpoint_mgr.mark_stage_complete(STAGE_ANALYZE_FRAMES, "analyze_frames", stage_data)
    
    return state

def create_langgraph_workflow():
    """
    Create a LangGraph workflow for video analysis.
    
    Returns:
        A compiled StateGraph for video analysis
    """
    # Create the state graph
    workflow = StateGraph(Dict)
    
    # Add the video analysis node
    workflow.add_node("analyze_video", video_analysis_agent)
    
    # Define the flow
    workflow.add_edge(START, "analyze_video")
    workflow.add_edge("analyze_video", END)
    
    # Compile and return the graph
    return workflow.compile()

def analyze_frames_langgraph(state: PipelineState, checkpoint_mgr: CheckpointManager) -> PipelineState:
    """
    Analyze the extracted frames using LangGraph.
    
    Args:
        state: Current pipeline state
        checkpoint_mgr: Checkpoint manager instance
        
    Returns:
        Updated pipeline state
    """
    logging.info("Analyzing frames with LangGraph...")
    
    # Get frames from previous stage
    frames = state.get("frames_extracted", [])
    if not frames:
        # Try to get from checkpoint
        stage_data = checkpoint_mgr.get_stage_data(STAGE_EXTRACT_FRAMES)
        if stage_data and "frames" in stage_data:
            frames = stage_data["frames"]
            state["frames_extracted"] = frames
    
    if not frames:
        error_msg = "No frames available for analysis"
        checkpoint_mgr.add_error(STAGE_ANALYZE_FRAMES, "analyze_frames", error_msg)
        state["error"] = error_msg
        return state
    
    # Create LangGraph pipeline
    pipeline = create_langgraph_workflow()
    
    # Create input state for LangGraph
    langgraph_state = {
        "video_path": state["video_path"],
        "api_key": state["api_key"]
    }
    
    # Execute LangGraph pipeline
    try:
        result = pipeline.invoke(langgraph_state)
        
        # Extract moments from LangGraph result
        if "moments" in result:
            state["moments"] = result["moments"]
        
        # Handle potential error
        if "error" in result and result["error"]:
            error_msg = result["error"]
            checkpoint_mgr.add_error(STAGE_ANALYZE_FRAMES, "analyze_frames", error_msg)
            state["error"] = error_msg
            return state
        
        # Create placeholder analysis results
        analysis_results = {
            "langgraph_processed": True,
            "moments_found": len(result.get("moments", [])),
            "processed_at": int(time.time())
        }
        state["analysis_results"] = analysis_results
        
        # Store data in checkpoint
        stage_data = {
            "analysis_results": analysis_results,
            "moments": [moment.__dict__ for moment in result.get("moments", [])]
        }
        checkpoint_mgr.mark_stage_complete(STAGE_ANALYZE_FRAMES, "analyze_frames", stage_data)
        
        # Skip the detect_moments stage since LangGraph already did it
        checkpoint_mgr.mark_stage_complete(STAGE_DETECT_MOMENTS, "detect_moments", 
                                          {"moments": [m.__dict__ for m in result.get("moments", [])]})
        
    except Exception as e:
        error_msg = f"LangGraph analysis failed: {str(e)}"
        checkpoint_mgr.add_error(STAGE_ANALYZE_FRAMES, "analyze_frames", error_msg)
        state["error"] = error_msg
    
    return state

def detect_moments(state: PipelineState, checkpoint_mgr: CheckpointManager) -> PipelineState:
    """
    Detect interesting moments from analyzed frames.
    
    Args:
        state: Current pipeline state
        checkpoint_mgr: Checkpoint manager instance
        
    Returns:
        Updated pipeline state
    """
    logging.info("Detecting interesting moments...")
    
    # Skip if we already have moments from LangGraph
    if state.get("moments"):
        logging.info("Skipping moment detection (already processed by LangGraph)")
        return state
    
    # Get analysis results from previous stage
    analysis_results = state.get("analysis_results", {})
    if not analysis_results:
        # Try to get from checkpoint
        stage_data = checkpoint_mgr.get_stage_data(STAGE_ANALYZE_FRAMES)
        if stage_data and "analysis_results" in stage_data:
            analysis_results = stage_data["analysis_results"]
            state["analysis_results"] = analysis_results
    
    if not analysis_results:
        error_msg = "No analysis results available for moment detection"
        checkpoint_mgr.add_error(STAGE_DETECT_MOMENTS, "detect_moments", error_msg)
        state["error"] = error_msg
        return state
    
    # Simulate moment detection
    time.sleep(1.5)
    
    # Create moments (simulated)
    moments = [
        VideoMoment(start_time=10.0, end_time=15.0, 
                   description="Person walking with dog"),
        VideoMoment(start_time=30.0, end_time=40.0, 
                   description="Car driving through city"),
        VideoMoment(start_time=60.0, end_time=70.0, 
                   description="Outdoor activity with high movement")
    ]
    state["moments"] = moments
    
    # Store data in checkpoint
    stage_data = {
        "moments": [moment.__dict__ for moment in moments]
    }
    checkpoint_mgr.mark_stage_complete(STAGE_DETECT_MOMENTS, "detect_moments", stage_data)
    
    return state

def generate_report(state: PipelineState, checkpoint_mgr: CheckpointManager) -> PipelineState:
    """
    Generate final analysis report.
    
    Args:
        state: Current pipeline state
        checkpoint_mgr: Checkpoint manager instance
        
    Returns:
        Updated pipeline state
    """
    logging.info("Generating final report...")
    
    # Get moments from previous stage
    moments = state.get("moments", [])
    if not moments:
        # Try to get from checkpoint
        stage_data = checkpoint_mgr.get_stage_data(STAGE_DETECT_MOMENTS)
        if stage_data and "moments" in stage_data:
            # Convert back to VideoMoment objects
            moment_dicts = stage_data["moments"]
            moments = [VideoMoment(**m) for m in moment_dicts]
            state["moments"] = moments
    
    if not moments:
        error_msg = "No moments available for report generation"
        checkpoint_mgr.add_error(STAGE_GENERATE_REPORT, "generate_report", error_msg)
        state["error"] = error_msg
        return state
    
    # Simulate report generation
    time.sleep(1)
    
    # Update state with report path (simulated)
    report_path = "output/report.html"
    state["report_path"] = report_path
    
    # Store data in checkpoint
    stage_data = {"report_path": report_path}
    checkpoint_mgr.mark_stage_complete(STAGE_GENERATE_REPORT, "generate_report", stage_data)
    
    return state

def run_pipeline(
    video_path: str, 
    api_key: str, 
    checkpoint_dir: str = "./checkpoints",
    start_stage: Optional[int] = None,
    reset: bool = False,
    use_langgraph: bool = False
) -> Dict[str, Any]:
    """
    Run the video analysis pipeline with checkpoint support.
    
    Args:
        video_path: Path to video file
        api_key: API key for video processing service
        checkpoint_dir: Directory for checkpoints
        start_stage: Index of stage to start from (None for auto-detect)
        reset: Whether to reset checkpoint data
        use_langgraph: Whether to use LangGraph for the analysis stage
        
    Returns:
        Final pipeline state
    """
    # Initialize checkpoint manager with video-specific checkpoint
    checkpoint_mgr = CheckpointManager(
        checkpoint_dir=checkpoint_dir,
        video_path=video_path
    )
    
    # Register pipeline stages
    register_pipeline_stages(checkpoint_mgr)
    
    # Reset if requested
    if reset:
        checkpoint_mgr.reset()
    
    # Create pipeline stages
    stages = create_pipeline(use_langgraph)
    
    # Determine starting stage
    if start_stage is not None:
        next_stage_index = start_stage
    else:
        next_stage_index = checkpoint_mgr.get_next_stage()
    
    # Create initial state
    state: PipelineState = {
        "video_path": video_path,
        "api_key": api_key,
        "moments": [],
        "error": None,
        "frames_extracted": None,
        "analysis_results": None,
        "report_path": None
    }
    
    # Load data from checkpoint for stages that were already completed
    for stage in stages:
        if checkpoint_mgr.is_stage_completed(stage.index):
            stage_data = checkpoint_mgr.get_stage_data(stage.index)
            if stage_data:
                if stage.index == STAGE_EXTRACT_FRAMES and "frames" in stage_data:
                    state["frames_extracted"] = stage_data["frames"]
                elif stage.index == STAGE_ANALYZE_FRAMES and "analysis_results" in stage_data:
                    state["analysis_results"] = stage_data["analysis_results"]
                    # Also check for moments in case LangGraph was used
                    if "moments" in stage_data:
                        state["moments"] = [VideoMoment(**m) for m in stage_data["moments"]]
                elif stage.index == STAGE_DETECT_MOMENTS and "moments" in stage_data:
                    # Convert moment dicts back to objects
                    moment_dicts = stage_data["moments"]
                    state["moments"] = [VideoMoment(**m) for m in moment_dicts]
                elif stage.index == STAGE_GENERATE_REPORT and "report_path" in stage_data:
                    state["report_path"] = stage_data["report_path"]
    
    # Execute pipeline from the starting stage
    for stage in stages:
        if stage.index < next_stage_index:
            logging.info(f"Skipping stage {stage.index}: {stage.name} (already completed)")
            continue
        
        # Skip detect_moments if using LangGraph and we already have moments
        if stage.index == STAGE_DETECT_MOMENTS and use_langgraph and state.get("moments"):
            logging.info(f"Skipping stage {stage.index}: {stage.name} (handled by LangGraph)")
            continue
        
        logging.info(f"Executing stage {stage.index}: {stage.name}")
        
        try:
            # Execute the stage function
            state = stage.func(state, checkpoint_mgr)
            
            # Check for errors
            if state.get("error"):
                logging.error(f"Pipeline failed at stage {stage.index}: {state['error']}")
                break
                
        except Exception as e:
            error_msg = f"Exception in stage {stage.index}: {str(e)}"
            logging.exception(error_msg)
            checkpoint_mgr.add_error(stage.index, stage.name, error_msg)
            state["error"] = error_msg
            break
    
    return state

if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.INFO)
    
    # Example usage
    video_path = "input_videos/sample.mp4"
    api_key = os.environ.get("GEMINI_API_KEY", "dummy-key")
    
    # Run pipeline
    result = run_pipeline(
        video_path=video_path, 
        api_key=api_key, 
        reset=True,
        use_langgraph=True
    )
    
    # Print results
    if result.get("error"):
        print(f"Error: {result['error']}")
    else:
        print(f"Pipeline completed successfully!")
        print(f"Found {len(result['moments'])} interesting moments:")
        for i, moment in enumerate(result["moments"]):
            print(f"Moment {i+1}: {moment.start_time}s - {moment.end_time}s: {moment.description}")
        print(f"Report generated at: {result.get('report_path')}") 