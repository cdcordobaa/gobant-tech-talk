#!/usr/bin/env python3
"""
Simple demonstration of the video analysis pipeline with LangGraph.
Includes basic and branching workflow options.
"""

import os
import sys
import argparse
from pathlib import Path
import time
from datetime import datetime
import json

# Add the project root to the Python path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Existing pipeline imports
# from src.workflows.pipeline import run_pipeline, STAGE_EXTRACT_FRAMES, STAGE_ANALYZE_FRAMES, STAGE_DETECT_MOMENTS, STAGE_GENERATE_REPORT
# from src.workflows.pipeline import create_basic_pipeline # Assuming basic pipeline is refactored - Removed for now
from src.visualization.report import extract_thumbnails, display_analysis_results
from src.utils.checkpoint_manager import CheckpointManager
from src.models.state import WorkflowState, SelectedMoment # Import the state model
from src.tools.format_validation import generate_preview_thumbnail

# Branching workflow imports
from src.workflows.branching_workflow import create_branching_workflow

# Define stage names/constants if not already centrally defined
STAGE_EXTRACT_FRAMES = "extract_frames"
STAGE_ANALYZE_FRAMES = "analyze_frames"
STAGE_DETECT_MOMENTS = "detect_moments"
# Branching stages
STAGE_ROUTE_PLATFORMS = "route_to_platforms"
STAGE_FORMAT_INSTAGRAM = "Instagram" # Use platform names as stage identifiers
STAGE_FORMAT_TIKTOK = "TikTok"
STAGE_FORMAT_LINKEDIN = "LinkedIn"
STAGE_AGGREGATE_RESULTS = "aggregate_results"
# Report stage
STAGE_GENERATE_REPORT = "generate_report" # May need adjustment depending on workflow

ALL_STAGES = [
    STAGE_EXTRACT_FRAMES, STAGE_ANALYZE_FRAMES, STAGE_DETECT_MOMENTS,
    STAGE_ROUTE_PLATFORMS, STAGE_FORMAT_INSTAGRAM, STAGE_FORMAT_TIKTOK,
    STAGE_FORMAT_LINKEDIN, STAGE_AGGREGATE_RESULTS, STAGE_GENERATE_REPORT
]

STAGE_NAME_MAP = {i: name for i, name in enumerate(ALL_STAGES)}


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run video analysis pipeline (basic or branching) and generate visualization reports."
    )
    
    parser.add_argument(
        "video_path",
        nargs="?",
        default="input_videos/sample.mp4",
        help="Path to the video file to analyze"
    )
    
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip HTML report generation and just output results to console"
    )
    
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory to save output files (default: 'output')"
    )
    
    # Workflow selection
    parser.add_argument(
        "--workflow",
        type=str,
        default="basic",
        choices=["basic", "branching"],
        help="Select the workflow to run ('basic' or 'branching')"
    )

    # Checkpoint-related arguments (may need adjustment for graph stages)
    parser.add_argument(
        "--checkpoint-dir",
        default="checkpoints",
        help="Directory to store checkpoint files (default: 'checkpoints')"
    )
    
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear checkpoint data and start fresh (Deletes checkpoint file)"
    )
    
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="Display saved checkpoint information and exit"
    )
    
    parser.add_argument(
        "--max-backups",
        type=int,
        default=1,
        help="Maximum number of backup files to keep per checkpoint (default: 1)"
    )
    
    parser.add_argument(
        "--cleanup-only",
        action="store_true",
        help="Just clean up checkpoint backup files and exit"
    )
    
    return parser.parse_args()


def format_timestamp(timestamp):
    """Format a timestamp for display."""
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime('%Y-%m-%d %H:%M:%S')

# Helper to get stage name (adjust as needed)
def get_stage_name(stage_id):
     # Simple lookup, assuming stage_id is the name used in the graph/state
     return str(stage_id)


def main():
    """Run the selected video analysis workflow."""
    args = parse_arguments()
    
    checkpoint_dir = Path(args.checkpoint_dir)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True) # Ensure output dir exists

    if args.cleanup_only:
        print(f"Cleaning up checkpoint backup files...")
        CheckpointManager.cleanup_all_backups(str(checkpoint_dir), args.max_backups)
        print("Cleanup complete!")
        sys.exit(0)

    # Initialize Checkpoint Manager early for listing/reset
    # We need video path for unique checkpoint file, handle potential error if file not found yet
    video_path = args.video_path
    if not os.path.exists(video_path) and not args.list_checkpoints:
         print(f"Error: Video file not found: {video_path}")
         sys.exit(1)
         
    checkpoint_mgr = CheckpointManager(checkpoint_dir, video_path=video_path, max_backups=args.max_backups)

    if args.list_checkpoints:
        # Use the manager's method if available, otherwise keep the basic list logic
        checkpoints = CheckpointManager.list_all_checkpoints(checkpoint_dir) # Assuming static method
        if not checkpoints:
            print(f"No checkpoints found in {checkpoint_dir}")
        else:
            print(f"Found {len(checkpoints)} checkpoint(s):")
            print("-" * 80)
            for i, cp_info in enumerate(checkpoints):
                print(f"Checkpoint #{i+1}: {cp_info.get('file', 'Unknown File')}")
                print(f"  Video: {cp_info.get('video_path', 'Unknown')}")
                # Adapt based on how LangGraph checkpoints store state info
                last_state = cp_info.get('last_state', {})
                current_stage = last_state.get('current_stage', 'N/A')
                stages_comp = last_state.get('stages_completed', [])
                print(f"  Current stage: {current_stage}")
                print(f"  Stages completed: {', '.join(stages_comp) if stages_comp else 'None'}")
                print(f"  Last updated: {format_timestamp(cp_info.get('last_updated', 0))}")
                print("-" * 80)
        sys.exit(0)

    # Handle reset before potentially loading a checkpoint
    if args.reset:
        print(f"Resetting checkpoint data for {checkpoint_mgr.checkpoint_file}...")
        checkpoint_mgr.clear_checkpoint() # Add a method to clear the specific checkpoint
        print("Checkpoint cleared.")

    # API Key Check
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY environment variable not set")
        sys.exit(1)

    video_name = Path(video_path).name
    print(f"Analyzing video: {video_name} using '{args.workflow}' workflow.")
    print(f"Using checkpoint file: {checkpoint_mgr.checkpoint_file}")
    
    # --- Workflow Selection and Execution ---
    
    # Load checkpoint data if exists and not reset
    # LangGraph's checkpointing handles loading internally when compiling with checkpointer
    # For manual start/restart logic, we might load initial state here if needed
    
    initial_state = {"video_path": video_path}
    
    # Configure LangGraph Checkpointer (example using SqliteSaver)
    # from langgraph.checkpoint.sqlite import SqliteSaver # Old import
    # from langgraph_checkpoint_sqlite import SqliteSaver # Corrected import - Didn't work
    from langgraph.checkpoint.memory import MemorySaver # Trying memory saver import
    memory = MemorySaver() # Use MemorySaver directly, not from_conn_string
    # Use a persistent DB for actual checkpointing:
    # from langgraph_checkpoint_sqlite import SqliteSaver
    # db_path = checkpoint_dir / f"{Path(video_path).stem}_workflow_state.db"
    # memory = SqliteSaver.from_conn_string(str(db_path))
    
    config = {"configurable": {"thread_id": checkpoint_mgr.checkpoint_file}} # Use checkpoint file path as thread_id
    
    # Compile the selected workflow
    if args.workflow == "branching":
        print("Creating branching workflow...")
        graph_builder = create_branching_workflow() 
        workflow_app = graph_builder.compile(checkpointer=memory) # Compile with checkpointer
        print("Invoking branching workflow...")
        
        # Define initial state
        initial_state = WorkflowState(video_path=video_path, api_key=api_key)
        
        # Use stream to get intermediate states (optional but good for visibility)
        final_result_state_data = None # Store the actual state data dict
        try:
            for event in workflow_app.stream(initial_state, config=config, stream_mode="values"):
                 # event is the state value (WorkflowState dataclass instance)
                 # Access fields directly from the event object
                 current_stage = getattr(event, 'current_stage', 'Unknown')
                 current_error = getattr(event, 'error', None)
                 
                 print(f"--- State after node '{current_stage}' ---")
                 # Optional detailed logging:
                 # print(f"    Error: {current_error}")
                 # print(f"    Moments: {len(getattr(event, 'moments', []))}")
                 # print(f"    Selected: {len(getattr(event, 'selected_moments', []))}")
                 # print(f"    Platform Content Keys: {list(getattr(event, 'platform_content', {}).keys())}")
                 
                 # Store the latest state's data as a dictionary
                 if isinstance(event, WorkflowState):
                     final_result_state_data = event.__dict__
                 elif isinstance(event, dict): # Fallback if it yields a dict somehow
                     final_result_state_data = event
                     
                 # Stop streaming if a critical error occurred in the state
                 if current_error:
                     print(f"\nWorkflow stream stopped due to error: {current_error}")
                     # Ensure the stored state reflects the error
                     if final_result_state_data:
                          final_result_state_data['error'] = current_error
                     else: # If no state was captured yet
                          final_result_state_data = {"error": current_error}
                     break 
                     
            if final_result_state_data:
                 print("\nWorkflow stream finished.")
                 # Use the captured state dictionary directly
                 final_result = final_result_state_data
                 # Ensure essential keys exist for downstream processing
                 final_result.setdefault('moments', []) 
                 final_result.setdefault('selected_moments', [])
                 final_result.setdefault('platform_content', {})
                 final_result.setdefault('error', None)
            else:
                 print("\nWorkflow stream did not yield a final state.")
                 final_result = {"error": "Workflow execution failed or yielded no state."}

        except Exception as e:
            print(f"\nError invoking workflow stream: {e}")
            import traceback
            traceback.print_exc()
            final_result = {"error": f"Workflow invocation error: {str(e)}"}
        
        # --- Simplified Demo Path Removed --- 
        
    elif args.workflow == "basic":
        print("Creating basic workflow...")
        # Assume create_basic_pipeline returns a compiled LangGraph app
        # workflow_app = create_basic_pipeline(api_key=api_key, checkpointer=memory) # Pass API key if needed by nodes
        # print("Invoking basic workflow...")
        # final_result = workflow_app.invoke(initial_state, config=config)
        
        # TEMPORARY: Fallback to old run_pipeline if basic graph not ready
        print("Falling back to legacy run_pipeline for basic workflow...")
        from src.workflows.pipeline import run_pipeline # Use the old function for now
        result_legacy = run_pipeline(
            video_path=video_path,
            api_key=api_key,
            checkpoint_dir=str(checkpoint_dir),
            # start_stage=start_stage, # Adapt start/restart logic if keeping old func
            reset=args.reset,
            use_langgraph=False # Force old path if needed
        )
        final_result = result_legacy # Adapt the output format if necessary

    else:
        print(f"Error: Unknown workflow type '{args.workflow}'")
        sys.exit(1)

    # Clean up backup files (optional, can be part of workflow)
    # CheckpointManager.cleanup_all_backups(str(checkpoint_dir), args.max_backups)
    
    # --- Display Results ---
    print("\n" + "="*30 + " Workflow Results " + "="*30)

    if isinstance(final_result, dict) and final_result.get("error"):
        print(f"Error: {final_result['error']}")
        sys.exit(1)
    elif not isinstance(final_result, dict):
         print(f"Error: Unexpected workflow result format: {type(final_result)}")
         print(f"Result dump: {final_result}") # Print the raw result
         # Try to access state data if it's an object (like WorkflowState)
         if hasattr(final_result, 'error') and final_result.error:
              print(f"Error from state object: {final_result.error}")
         sys.exit(1)

    # Display identified moments (assuming they exist in the final state/result)
    moments = final_result.get("moments", [])
    print(f"\nIdentified {len(moments)} interesting moments:")
    print("-" * 80)
    for i, moment_data in enumerate(moments, 1):
        # Handle both object and dict representations
        start_time_str = moment_data.start_time_str if hasattr(moment_data, 'start_time_str') else str(datetime.timedelta(seconds=int(moment_data.get('start_time', 0))))
        end_time_str = moment_data.end_time_str if hasattr(moment_data, 'end_time_str') else str(datetime.timedelta(seconds=int(moment_data.get('end_time', 0))))
        duration = moment_data.duration if hasattr(moment_data, 'duration') else moment_data.get('end_time', 0) - moment_data.get('start_time', 0)
        desc = moment_data.description if hasattr(moment_data, 'description') else moment_data.get('description', 'N/A')
        print(f"Moment {i}: {start_time_str} - {end_time_str} ({duration:.1f}s)")
        print(f"  Description: {desc}")

    # Display selected moments
    selected_moments = final_result.get("selected_moments", [])
    if selected_moments:
        print(f"\nSelected {len(selected_moments)} moments for content creation:")
        print("-" * 80)
        for i, moment_data in enumerate(selected_moments, 1):
            start_time_str = moment_data.start_time_str if hasattr(moment_data, 'start_time_str') else str(datetime.timedelta(seconds=int(moment_data.get('start_time', 0))))
            end_time_str = moment_data.end_time_str if hasattr(moment_data, 'end_time_str') else str(datetime.timedelta(seconds=int(moment_data.get('end_time', 0))))
            duration = moment_data.duration if hasattr(moment_data, 'duration') else moment_data.get('end_time', 0) - moment_data.get('start_time', 0)
            desc = moment_data.description if hasattr(moment_data, 'description') else moment_data.get('description', 'N/A')
            reason = moment_data.selection_reason if hasattr(moment_data, 'selection_reason') else moment_data.get('selection_reason', 'N/A')
            eng = moment_data.engagement_prediction if hasattr(moment_data, 'engagement_prediction') else moment_data.get('engagement_prediction', 0.0)
            cat = moment_data.content_category if hasattr(moment_data, 'content_category') else moment_data.get('content_category', 'N/A')
            plats = moment_data.target_platforms if hasattr(moment_data, 'target_platforms') else moment_data.get('target_platforms', [])
            
            print(f"Selected Moment {i}: {start_time_str} - {end_time_str} ({duration:.1f}s)")
            print(f"  Description: {desc}")
            print(f"  Selection Reason: {reason}")
            print(f"  Engagement Prediction: {eng:.2f}")
            print(f"  Content Category: {cat}")
            print(f"  Target Platforms (Initial): {', '.join(plats)}")
            print()

    # Display Platform Routing and Formatting (Specific to Branching Workflow)
    if args.workflow == "branching":
        platform_content_map = final_result.get("platform_content", {})
        print(f"\nPlatform Routing & Formatting Decisions:")
        print("-" * 80)
        if not platform_content_map:
             print("No platform content generated.")
        else:
            preview_dir = output_dir / "previews" # Define preview dir based on output_dir
            preview_dir.mkdir(parents=True, exist_ok=True)
            
            generated_previews = []
            for platform, content_list in platform_content_map.items():
                print(f"Platform: {platform} ({len(content_list)} items)")
                if not content_list:
                    print("  No content routed to this platform.")
                    continue
                for j, content_item_data in enumerate(content_list, 1):
                     # Handle dict vs object again
                     if isinstance(content_item_data, dict):
                         # If it's a dict, try to reconstruct the objects or access keys
                         # This might happen if the state wasn't properly maintained as objects
                         moment_data = content_item_data.get('source_moment', {})
                         moment_desc = moment_data.get('description', 'Unknown Moment')
                         moment_start = moment_data.get('start_time', 0)
                         moment_end = moment_data.get('end_time', 0)
                         moment_start_str = str(datetime.timedelta(seconds=int(moment_start)))
                         status = content_item_data.get('processing_status', 'unknown')
                         ffmpeg_params = content_item_data.get('ffmpeg_params', {})
                         
                         print(f"  Item {j}: Moment '{moment_desc}' ({moment_start_str})")
                         print(f"    Status: {status}")
                         print(f"    FFmpeg Params: {json.dumps(ffmpeg_params)}")
                         # Cannot generate preview if data is just dicts without reconstructing objects fully
                         print("    Preview Generation Skipped (Requires PlatformContent object)")

                     elif hasattr(content_item_data, 'source_moment') and hasattr(content_item_data, 'target_specs'):
                         content_item = content_item_data # Assume it's the dataclass object
                         moment = content_item.source_moment
                         specs = content_item.target_specs
                         print(f"  Item {j}: Moment {moment.start_time_str} - {moment.end_time_str}")
                         print(f"    Status: {content_item.processing_status}")
                         print(f"    Target Specs: {specs.resolution} ({specs.aspect_ratio}), Max Duration: {specs.max_duration}s")
                         if content_item.ffmpeg_params:
                             print(f"    FFmpeg Params: {content_item.ffmpeg_params}")
                             # Generate preview thumbnail
                             preview_path = generate_preview_thumbnail(
                                 video_path=video_path,
                                 content_item=content_item,
                                 output_dir=str(preview_dir)
                             )
                             if preview_path:
                                 generated_previews.append(preview_path)
                                 print(f"    Preview Thumbnail: {preview_path}")
                             else:
                                 print(f"    Preview Thumbnail Generation Failed.")
                         else:
                             print("    FFmpeg Params: Not defined.")
                         print() # Spacer
                     else:
                         print(f"  Item {j}: Invalid content data format - {type(content_item_data)}")

            if generated_previews:
                 print(f"\nGenerated {len(generated_previews)} preview thumbnails in: {preview_dir}")

    print("-" * 80)
    print("="*35 + " End Results " + "="*35)


    # --- Optional Report Generation ---
    if args.no_report:
        print("\nHTML Report generation skipped (--no-report flag provided)")
        return

    print("\nGenerating HTML report...")
    try:
        # Extract thumbnails for the *original* selected moments for the report
        thumbnail_dir = output_dir / "thumbnails"
        print(f"Extracting base thumbnails to {thumbnail_dir}...")
        # Need to ensure 'selected_moments' are available and correctly formatted
        thumbnails = extract_thumbnails(video_path, selected_moments, output_dir=str(thumbnail_dir))
        
        # Pass the final result (which should contain all state info)
        report_path = display_analysis_results(video_path, final_result, thumbnails)
        print(f"Report generated and opened in browser: {report_path}")
    except Exception as e:
        print(f"Error generating HTML report: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Note: Need to install langgraph, Pillow, ffmpeg-python, google-generativeai
    # pip install langgraph langchain langchain-core Pillow ffmpeg-python google-generativeai
    main() 