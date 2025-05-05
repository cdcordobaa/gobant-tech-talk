import os
import sys
from typing import Dict, Any, List
from pathlib import Path

# Add the project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.gemini_client import GeminiClient
from src.models.state import VideoMoment

def video_analysis_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Agent function that analyzes a video using GeminiClient.
    
    Args:
        state: Dictionary containing the current state with video path and API key
        
    Returns:
        Updated state dictionary with detected video moments
    """
    try:
        # Extract video path and API key from state
        video_path = state.get("video_path")
        api_key = state.get("api_key")
        
        if not video_path or not api_key:
            state["error"] = "Missing video_path or api_key in state"
            return state
        
        # Initialize GeminiClient
        client = GeminiClient(api_key=api_key)
        
        # Analyze the video
        moments = client.analyze_video(video_path)
        
        # Update the state with detected moments
        state["moments"] = moments
        
        return state
        
    except Exception as e:
        state["error"] = f"Error in video analysis: {str(e)}"
        return state

# Simple test function to directly test the agent
def test_video_analysis_agent():
    """Test the video analysis agent with a sample video."""
    # Create a test state
    test_state = {
        "video_path": "/path/to/test_video.mp4",
        "api_key": os.environ.get("GEMINI_API_KEY")
    }
    
    # Call the agent
    result_state = video_analysis_agent(test_state)
    
    # Print the results
    if "error" in result_state:
        print(f"Error: {result_state['error']}")
    else:
        print(f"Found {len(result_state['moments'])} interesting moments:")
        for i, moment in enumerate(result_state["moments"]):
            print(f"Moment {i+1}: {moment.start_time}s - {moment.end_time}s: {moment.description}")

if __name__ == "__main__":
    test_video_analysis_agent() 