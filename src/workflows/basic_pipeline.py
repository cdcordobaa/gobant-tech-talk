import sys
from typing import Dict, Any, TypedDict
from pathlib import Path

# Add the project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from langgraph.graph import StateGraph, START, END
from src.agents.video_analysis import video_analysis_agent
from src.models.state import VideoMoment

# Define the state schema
class VideoAnalysisState(TypedDict):
    video_path: str
    api_key: str
    moments: list[VideoMoment]
    error: str

def create_basic_pipeline():
    """
    Create a minimal LangGraph workflow for video analysis.
    
    Returns:
        A compiled StateGraph for video analysis
    """
    # Create the state graph
    workflow = StateGraph(VideoAnalysisState)
    
    # Add the video analysis node
    workflow.add_node("analyze_video", video_analysis_agent)
    
    # Define the flow
    workflow.add_edge(START, "analyze_video")
    workflow.add_edge("analyze_video", END)
    
    # Compile and return the graph
    return workflow.compile()

def run_pipeline(video_path: str, api_key: str):
    """
    Run the video analysis pipeline on a given video.
    
    Args:
        video_path: Path to the video file
        api_key: Gemini API key
    
    Returns:
        The final state after pipeline execution
    """
    # Create the initial state
    initial_state = {
        "video_path": video_path,
        "api_key": api_key
    }
    
    # Create and run the pipeline
    pipeline = create_basic_pipeline()
    final_state = pipeline.invoke(initial_state)
    
    return final_state

if __name__ == "__main__":
    import os
    
    # Example usage
    video_path = "input_videos/El Año en que la IA Redefinió Límites.mp4"
    api_key = os.environ.get("GEMINI_API_KEY")
    
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)
    
    result = run_pipeline(video_path, api_key)
    
    # Print the results
    if "error" in result and result["error"]:
        print(f"Error: {result['error']}")
    else:
        print(f"Found {len(result['moments'])} interesting moments:")
        for i, moment in enumerate(result["moments"]):
            print(f"Moment {i+1}: {moment.start_time}s - {moment.end_time}s: {moment.description}") 