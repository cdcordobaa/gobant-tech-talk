import os
import time
from pathlib import Path
import ffmpeg # For frame extraction
import shutil # For cleaning up frames dir
import logging # Use logging for better output control

from langgraph.graph import StateGraph, END, START
from typing import Dict, Any

from src.models.state import WorkflowState, PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_LINKEDIN, SUPPORTED_PLATFORMS # Added SUPPORTED_PLATFORMS import

# Placeholder imports for agents/nodes (replace with actual)
# from src.workflows.pipeline import extract_frames_node, analyze_frames_node, detect_moments_node, generate_report_node # Assuming reuse
from src.agents.platform_router import PlatformRouterAgent
from src.agents.formatters.instagram_formatter import InstagramFormatterAgent
from src.agents.formatters.tiktok_formatter import TikTokFormatterAgent
from src.agents.formatters.linkedin_formatter import LinkedInFormatterAgent

# Import agents from the original pipeline logic (assuming they exist and work with state)
# Make sure these imports point to the correct location of your agents
try:
    from src.agents.video_analysis import video_analysis_agent # Example import path
    from src.agents.moment_selection import moment_selection_agent # Example import path
    INITIAL_AGENTS_LOADED = True
except ImportError as e:
    logging.warning(f"Could not import initial analysis/selection agents: {e}. Analysis/Selection nodes will be skipped.")
    INITIAL_AGENTS_LOADED = False
    # Define dummy functions if agents are missing to prevent graph build errors
    def video_analysis_agent(state: WorkflowState) -> WorkflowState:
        logging.warning("Skipping video analysis (agent not found).")
        state.moments = [] # Ensure moments is empty
        return state
    def moment_selection_agent(state: WorkflowState) -> WorkflowState:
        logging.warning("Skipping moment selection (agent not found).")
        state.selected_moments = [] # Ensure selected moments is empty
        return state

# --- Node Implementations (Wrappers around Agent Logic) ---

# Stage 1: Extract Frames
FRAME_EXTRACT_RATE = 1 # Extract 1 frame per second

def extract_frames_node(state: WorkflowState) -> WorkflowState:
    """Extracts frames from the video file using ffmpeg."""
    print("\n--- Running Frame Extraction Node ---")
    state.current_stage = "extract_frames"
    video_path = state.video_path
    if not Path(video_path).exists():
        state.error = f"Video file not found at: {video_path}"
        print(f"  ! Error: {state.error}")
        return state
        
    video_filename = Path(video_path).stem
    # Create a unique directory for frames
    output_base = Path("output/staging") # Base directory for intermediate files
    frames_dir = output_base / f"{video_filename}_frames_{int(time.time())}"
    
    # Clean up old directory if it exists (simple approach)
    if frames_dir.exists():
         shutil.rmtree(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    state.frames_dir = str(frames_dir)
    print(f"  Extracting frames to: {frames_dir} at {FRAME_EXTRACT_RATE} FPS")
    
    output_pattern = str(frames_dir / "frame_%04d.jpg")
    frame_paths = []

    try:
        # Check video duration first (optional, but good for large files)
        probe = ffmpeg.probe(video_path)
        duration = float(probe['format']['duration'])
        print(f"  Video duration: {duration:.2f} seconds.")
        if duration > 300: # Example limit: 5 minutes
             print("  Warning: Video is long, frame extraction might take time.")

        process = (
            ffmpeg
            .input(video_path)
            .filter('fps', fps=FRAME_EXTRACT_RATE)
            .output(output_pattern, start_number=0)
            # Add -loglevel error to suppress verbose ffmpeg output
            .run_async(pipe_stdout=True, pipe_stderr=True, quiet=False) 
        )
        out, err = process.communicate()
        
        if process.returncode != 0:
             # Try to decode stderr for better error message
             try:
                 error_details = err.decode()
             except Exception:
                 error_details = "Unknown FFmpeg error (failed to decode stderr)"
             raise ffmpeg.Error(f"FFmpeg failed with exit code {process.returncode}", stdout=out, stderr=err)

        
        frame_paths = sorted([str(f) for f in frames_dir.glob("frame_*.jpg")])
        state.frame_paths = frame_paths
        if not frame_paths:
             # Check if ffmpeg produced output even if return code was 0
             raise ValueError("FFmpeg ran but no frames were extracted.")
             
        print(f"  Successfully extracted {len(frame_paths)} frames.")
        state.stages_completed.append("extract_frames")

    except ffmpeg.Error as e:
        # Attempt to decode stderr for a more informative error message
        try:
            stderr_decoded = e.stderr.decode()
        except Exception:
            stderr_decoded = "Could not decode stderr"
        error_msg = f"FFmpeg error during frame extraction: {stderr_decoded}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
    except Exception as e:
        error_msg = f"Error during frame extraction: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        # import traceback # Uncomment for detailed debug
        # traceback.print_exc() # Uncomment for detailed debug
        
    print("--- Frame Extraction Node Finished ---")
    return state

# Stage 2: Analyze Video (using existing agent)
def analyze_video_node(state: WorkflowState) -> WorkflowState:
    """Analyzes video using the video_analysis_agent."""
    print("\n--- Running Video Analysis Node ---")
    state.current_stage = "analyze_video"
    if state.error: # Skip if previous stage failed
        print("  Skipping due to previous error.")
        return state
    
    if not state.frame_paths:
        state.error = "No frames available for analysis."
        print(f"  ! Error: {state.error}")
        return state
        
    if not INITIAL_AGENTS_LOADED:
         state.error = "Video analysis agent not loaded. Skipping analysis."
         print(f"  ! Error: {state.error}")
         return state

    try:
        print(f"  Calling video_analysis_agent for {state.video_path}...") 
        # Assumes video_analysis_agent can work with the WorkflowState object
        # It should use state.api_key, state.video_path, state.frame_paths
        # and update state.moments
        result_state_or_dict = video_analysis_agent(state)

        # Update the main state based on the agent's return type
        if isinstance(result_state_or_dict, WorkflowState):
            state.moments = result_state_or_dict.moments if result_state_or_dict.moments else []
            state.analysis_summary = result_state_or_dict.analysis_summary
            if result_state_or_dict.error:
                state.error = result_state_or_dict.error
        elif isinstance(result_state_or_dict, dict):
            state.moments = result_state_or_dict.get('moments', []) # Default to empty list
            state.analysis_summary = result_state_or_dict.get('analysis_summary')
            if result_state_or_dict.get('error'):
                 state.error = result_state_or_dict['error']
        else:
             raise TypeError(f"Unexpected return type from video_analysis_agent: {type(result_state_or_dict)}")

        # Ensure moments is a list
        if state.moments is None:
             state.moments = []
             
        if not state.error:
            print(f"  Analysis complete. Found {len(state.moments)} potential moments.")
            state.stages_completed.append("analyze_video")
        else:
            print(f"  ! Error during analysis: {state.error}")
            
    except Exception as e:
        error_msg = f"Exception in video_analysis_agent: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        state.moments = [] # Ensure empty list on exception
        # import traceback # Uncomment for detailed debug
        # traceback.print_exc() # Uncomment for detailed debug

    print("--- Video Analysis Node Finished ---")
    return state

# Stage 3: Select Moments (using existing agent)
def select_moments_node(state: WorkflowState) -> WorkflowState:
    """Selects key moments using the moment_selection_agent."""
    print("\n--- Running Moment Selection Node ---")
    state.current_stage = "select_moments"
    if state.error or not state.moments: # Skip if previous stage failed or no moments
        print("  Skipping due to previous error or no moments identified.")
        state.selected_moments = [] # Ensure empty list
        return state
        
    if not INITIAL_AGENTS_LOADED:
         state.error = "Moment selection agent not loaded. Skipping selection."
         print(f"  ! Error: {state.error}")
         state.selected_moments = []
         return state
         
    try:
        print(f"  Calling moment_selection_agent with {len(state.moments)} moments...")
        # Assumes moment_selection_agent works with WorkflowState object
        result_state_or_dict = moment_selection_agent(state)

        # Update the main state
        if isinstance(result_state_or_dict, WorkflowState):
            state.selected_moments = result_state_or_dict.selected_moments
            if result_state_or_dict.error:
                state.error = result_state_or_dict.error
        elif isinstance(result_state_or_dict, dict):
            state.selected_moments = result_state_or_dict.get('selected_moments', [])
            if result_state_or_dict.get('error'):
                 state.error = result_state_or_dict['error']
        else:
             raise TypeError(f"Unexpected return type from moment_selection_agent: {type(result_state_or_dict)}")

        # Ensure selected_moments is a list
        if state.selected_moments is None:
            state.selected_moments = []
            
        if not state.error:
            print(f"  Selection complete. Selected {len(state.selected_moments)} moments.")
            state.stages_completed.append("select_moments")
        else:
             print(f"  ! Error during selection: {state.error}")

    except Exception as e:
        error_msg = f"Exception in moment_selection_agent: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        state.selected_moments = [] # Ensure empty list on exception
        # import traceback # Uncomment for detailed debug
        # traceback.print_exc() # Uncomment for detailed debug
        
    print("--- Moment Selection Node Finished ---")
    return state

# Rename original routing function
def route_to_platforms_node(state: WorkflowState) -> WorkflowState:
    """Routes selected moments to platforms using Gemini (runs once)."""
    print("\n--- Running Platform Routing Node ---")
    state.current_stage = "route_to_platforms"
    if state.error or not state.selected_moments:
         print("  Skipping due to previous error or no moments selected.")
         state.platform_content = {p: [] for p in SUPPORTED_PLATFORMS} 
         return state
         
    if not state.api_key:
        state.error = "API key not found in workflow state for routing."
        print(f"  ! Error: {state.error}")
        return state
        
    try:
        router = PlatformRouterAgent(api_key=state.api_key)
        returned_state = router.route_moments(state) # Modifies state directly or returns new one
        if isinstance(returned_state, WorkflowState):
             state = returned_state 
        if not hasattr(state, 'platform_content') or state.platform_content is None:
             state.platform_content = {p: [] for p in SUPPORTED_PLATFORMS}
             
        state.stages_completed.append("route_to_platforms")
    except Exception as e:
        error_msg = f"Exception in PlatformRouterAgent: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        state.platform_content = {p: [] for p in SUPPORTED_PLATFORMS}
        
    print("--- Platform Routing Node Finished ---")
    return state

# New node to act as the conditional check point
def check_formatting_node(state: WorkflowState) -> WorkflowState:
    """Placeholder node before the formatting conditional check. Does nothing."""
    print("--- Reached Formatting Check Point --- ")
    state.current_stage = "check_formatting"
    # This node doesn't change the state, just acts as a target for edges
    return state

# --- Formatting Nodes (remain the same) ---
def format_for_instagram(state: WorkflowState) -> WorkflowState:
    """Formats content for Instagram using Gemini."""
    print("\n--- Running Instagram Formatting Node ---")
    state.current_stage = PLATFORM_INSTAGRAM 
    platform_name = PLATFORM_INSTAGRAM
    if state.error:
         print("  Skipping due to previous error.")
         return state
         
    if not state.platform_content.get(platform_name):
         print(f"  Skipping: No content routed to {platform_name}.")
         return state 
         
    if not state.api_key:
        state.error = f"API key not found in workflow state for {platform_name} formatting."
        print(f"  ! Error: {state.error}")
        return state
        
    try:
        formatter = InstagramFormatterAgent(api_key=state.api_key)
        returned_state = formatter.format_content(state) 
        if isinstance(returned_state, WorkflowState):
             state = returned_state
        # Note: We don't mark stage completed here, only after aggregation if successful?
        # Or mark it here? Let's mark it here for now.
        if platform_name not in state.stages_completed:
             state.stages_completed.append(platform_name) 
    except Exception as e:
        error_msg = f"Exception in InstagramFormatterAgent: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        
    print(f"--- {platform_name} Formatting Node Finished ---")
    return state

def format_for_tiktok(state: WorkflowState) -> WorkflowState:
    """Formats content for TikTok using Gemini."""
    print("\n--- Running TikTok Formatting Node ---")
    state.current_stage = PLATFORM_TIKTOK
    platform_name = PLATFORM_TIKTOK
    if state.error:
         print("  Skipping due to previous error.")
         return state
         
    if not state.platform_content.get(platform_name):
         print(f"  Skipping: No content routed to {platform_name}.")
         return state
         
    if not state.api_key:
        state.error = f"API key not found in workflow state for {platform_name} formatting."
        print(f"  ! Error: {state.error}")
        return state
        
    try:
        formatter = TikTokFormatterAgent(api_key=state.api_key)
        returned_state = formatter.format_content(state) 
        if isinstance(returned_state, WorkflowState):
             state = returned_state
        state.stages_completed.append(platform_name)
    except Exception as e:
        error_msg = f"Exception in TikTokFormatterAgent: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        
    print(f"--- {platform_name} Formatting Node Finished ---")
    return state

def format_for_linkedin(state: WorkflowState) -> WorkflowState:
    """Formats content for LinkedIn using Gemini."""
    print("\n--- Running LinkedIn Formatting Node ---")
    state.current_stage = PLATFORM_LINKEDIN
    platform_name = PLATFORM_LINKEDIN
    if state.error:
         print("  Skipping due to previous error.")
         return state
         
    if not state.platform_content.get(platform_name):
         print(f"  Skipping: No content routed to {platform_name}.")
         return state
         
    if not state.api_key:
        state.error = f"API key not found in workflow state for {platform_name} formatting."
        print(f"  ! Error: {state.error}")
        return state
        
    try:
        formatter = LinkedInFormatterAgent(api_key=state.api_key)
        returned_state = formatter.format_content(state) 
        if isinstance(returned_state, WorkflowState):
             state = returned_state
        state.stages_completed.append(platform_name)
    except Exception as e:
        error_msg = f"Exception in LinkedInFormatterAgent: {str(e)}"
        print(f"  ! Error: {error_msg}")
        state.error = error_msg
        
    print(f"--- {platform_name} Formatting Node Finished ---")
    return state

def should_continue_or_finish(state: WorkflowState) -> str:
    """Determines if the workflow should continue to the next sequential step or end due to error."""
    if state.error:
        print(f"\nConditional Edge: Error detected after stage '{state.current_stage}', routing to END.")
        return END 
    else:
        # Determine the next sequential node based on the last completed stage name
        last_completed = state.current_stage 
        print(f"\nConditional Edge: Completed '{last_completed}'. Determining next step...")
        if last_completed == "extract_frames":
            return "analyze_video"
        elif last_completed == "analyze_video":
            return "select_moments"
        elif last_completed == "select_moments":
            # This is the end of the linear part, now decide if we go to routing or end
             if not state.selected_moments:
                 print("  No moments selected, routing to END.")
                 return END
             else:
                 print("  Moments selected, proceeding to routing.")
                 return "route_to_platforms"
        else:
            # If the stage isn't part of the main sequence before branching, maybe go to END or handle differently
            logging.warning(f"Unhandled stage '{last_completed}' in should_continue_or_finish. Routing to END.")
            return END

def check_formatting_needed(state: WorkflowState) -> str:
    """Determines which platform formatters need to run or if we should aggregate."""
    print("\nConditional Edge: Checking if formatting is needed...")
    if state.error:
         print("  Error detected, routing to aggregate/END.")
         return "aggregate_results"
         
    order = [PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_LINKEDIN]
    for platform in order:
        content_list = state.platform_content.get(platform, [])
        if content_list and any(c.processing_status == "pending_format" for c in content_list):
            print(f"  Next platform to format is {platform}.")
            return platform
    
    print("  No platforms require formatting. Proceeding to aggregate.")
    return "aggregate_results"

def aggregate_formatted_content(state: WorkflowState) -> WorkflowState:
    """Node to potentially aggregate results after formatting branches."""
    print("\n--- Running Aggregate Formatted Content Node ---")
    state.current_stage = "aggregate_results"
    # In this simple setup, state is already updated by formatters. 
    # We could add logic here to clean up temporary files, finalize statuses, etc.
    
    # Example: Clean up frames directory if it exists
    if state.frames_dir and Path(state.frames_dir).exists():
        try:
            print(f"  Cleaning up frames directory: {state.frames_dir}")
            shutil.rmtree(state.frames_dir)
            state.frames_dir = None # Clear from state
        except Exception as e:
            logging.warning(f"Could not clean up frames directory {state.frames_dir}: {e}")

    state.stages_completed.append("aggregate_results")
    print("--- Aggregate Formatted Content Node Finished ---")
    return state

# --- Workflow Definition ---

def create_branching_workflow():
    """Creates the LangGraph workflow with platform-specific branching."""
    workflow = StateGraph(WorkflowState)

    # Add analysis nodes
    workflow.add_node("extract_frames", extract_frames_node)
    workflow.add_node("analyze_video", analyze_video_node)
    workflow.add_node("select_moments", select_moments_node)

    # Add routing node (runs once)
    workflow.add_node("route_to_platforms", route_to_platforms_node) 
    
    # Add check node (acts as conditional source)
    workflow.add_node("check_formatting", check_formatting_node) 

    # Add formatters and aggregator
    workflow.add_node(PLATFORM_INSTAGRAM, format_for_instagram)
    workflow.add_node(PLATFORM_TIKTOK, format_for_tiktok)
    workflow.add_node(PLATFORM_LINKEDIN, format_for_linkedin)
    workflow.add_node("aggregate_results", aggregate_formatted_content)

    # --- Define Edges --- 

    # Initial sequence
    workflow.set_entry_point("extract_frames")
    workflow.add_conditional_edges(
        "extract_frames",
        should_continue_or_finish, 
        { "analyze_video": "analyze_video", END: END }
    )
    workflow.add_conditional_edges(
        "analyze_video",
        should_continue_or_finish, 
        { "select_moments": "select_moments", END: END }
    )
    workflow.add_conditional_edges(
        "select_moments",
        should_continue_or_finish, # Checks for errors AND if moments exist
        { "route_to_platforms": "route_to_platforms", END: END } # Go to routing node
    )
    
    # After routing, always go to the check node
    workflow.add_edge("route_to_platforms", "check_formatting")

    # Conditional branching from the check node
    workflow.add_conditional_edges(
        "check_formatting",       # Source is the check node
        check_formatting_needed, # Function decides where to go
        {
            PLATFORM_INSTAGRAM: PLATFORM_INSTAGRAM,
            PLATFORM_TIKTOK: PLATFORM_TIKTOK,
            PLATFORM_LINKEDIN: PLATFORM_LINKEDIN,
            "aggregate_results": "aggregate_results" # If no formatting needed or error
        }
    )

    # Connect formatters back to the check node to re-evaluate the condition
    workflow.add_edge(PLATFORM_INSTAGRAM, "check_formatting") 
    workflow.add_edge(PLATFORM_TIKTOK, "check_formatting")
    workflow.add_edge(PLATFORM_LINKEDIN, "check_formatting")

    # Final node
    workflow.add_edge("aggregate_results", END)

    print("\nBranching workflow graph created with separated routing and checking nodes.")
    return workflow

# Example check: Compile and draw the graph (optional, requires graphviz)
# if __name__ == '__main__':
#     graph = create_branching_workflow()
#     app = graph.compile()
#     try:
#         # Draw the graph to a file
#         output_path = Path("output/branching_workflow_graph.png")
#         output_path.parent.mkdir(parents=True, exist_ok=True)
#         app.get_graph().draw_mermaid_png(output_path=str(output_path))
#         print(f"Workflow graph drawn to {output_path}")
#     except Exception as e:
#         print(f"Could not draw graph (requires graphviz): {e}") 