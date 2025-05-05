import os
import sys
from typing import Dict, Any, List
from pathlib import Path
import logging # Use logging

# Add the project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.tools.gemini_client import GeminiClient
from src.models.state import VideoMoment, WorkflowState # Import WorkflowState

def video_analysis_agent(state: WorkflowState) -> WorkflowState:
    """
    Agent function that analyzes a video using GeminiClient.
    Updates the WorkflowState object directly.
    
    Args:
        state: WorkflowState object containing video path and API key.
        
    Returns:
        The modified WorkflowState object.
    """
    try:
        # Extract video path and API key from state attributes
        video_path = state.video_path
        api_key = state.api_key
        
        if not video_path or not api_key:
            state.error = "Missing video_path or api_key in state"
            logging.error(f"Video Analysis Agent Error: {state.error}")
            return state
        
        # Initialize GeminiClient
        # TODO: Consider initializing client once if agent is part of a class
        client = GeminiClient(api_key=api_key)
        
        # Analyze the video
        # Assuming client.analyze_video returns a list of VideoMoment objects
        logging.info(f"Analyzing video file: {video_path}")
        moments = client.analyze_video(video_path) 
        
        # Update the state with detected moments using attribute access
        state.moments = moments
        logging.info(f"Analysis found {len(moments)} potential moments.")
        
        # Clear any previous error if successful
        state.error = None 
        return state
        
    except Exception as e:
        error_msg = f"Error in video analysis: {str(e)}"
        logging.exception(f"Video Analysis Agent Exception: {error_msg}") # Log traceback
        state.error = error_msg
        state.moments = [] # Ensure moments is empty list on error
        return state

# Simple test function to directly test the agent
def test_video_analysis_agent():
    """Test the video analysis agent with a sample video."""
    api_key_env = os.environ.get("GEMINI_API_KEY")
    if not api_key_env:
        print("Error: GEMINI_API_KEY environment variable not set for testing.")
        return
        
    # Create a test state using WorkflowState
    test_state = WorkflowState(
        video_path="input_videos/sample.mp4", # Use a valid sample path
        api_key=api_key_env
    )
    
    # Call the agent
    result_state = video_analysis_agent(test_state)
    
    # Print the results from the state object
    if result_state.error:
        print(f"Error: {result_state.error}")
    else:
        print(f"Found {len(result_state.moments)} interesting moments:")
        for i, moment in enumerate(result_state.moments):
            # Access attributes directly from the VideoMoment object
            print(f"Moment {i+1}: {moment.start_time}s - {moment.end_time}s: {moment.description}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Running video_analysis_agent test...")
    # This test requires a valid GEMINI_API_KEY and the sample video
    # Ensure input_videos/sample.mp4 exists or change the path
    if not Path("input_videos/sample.mp4").exists():
         print("Warning: input_videos/sample.mp4 not found, test might fail.")
    # test_video_analysis_agent() # Comment out direct execution for now
    print("Test function defined. Run manually if needed.") 