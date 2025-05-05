"""Agent for selecting the most promising video moments for processing."""

import os
import sys
from typing import Dict, Any, List
from pathlib import Path

# Add the project root directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.state import VideoMoment, SelectedMoment

def calculate_engagement_score(moment: VideoMoment) -> float:
    """
    Calculate an engagement score for a video moment based on various factors.
    
    Args:
        moment: The video moment to evaluate
        
    Returns:
        A score between 0.0 and 1.0 indicating potential engagement
    """
    # Initialize score
    score = 0.5  # Start with a neutral score
    
    # Adjust score based on duration - prefer 10-60 second clips
    duration = moment.duration
    if 10 <= duration <= 60:
        score += 0.2
    elif duration < 5 or duration > 120:
        score -= 0.2
    
    # Look for engaging keywords in description
    engaging_keywords = [
        "amazing", "incredible", "exciting", "surprising", "fascinating",
        "beautiful", "action", "highlight", "key", "important", "critical",
        "reveal", "demonstrate", "show", "explain", "tutorial", "guide",
        "demo", "walkthrough", "insight", "discovery"
    ]
    
    # Count matches
    keyword_matches = sum(1 for keyword in engaging_keywords if keyword.lower() in moment.description.lower())
    score += min(0.3, keyword_matches * 0.05)  # Cap the bonus at 0.3
    
    # Cap score between 0 and 1
    return max(0.0, min(1.0, score))

def generate_selection_reason(moment: VideoMoment, score: float) -> str:
    """
    Generate a reason for why this moment was selected.
    
    Args:
        moment: The selected video moment
        score: The calculated engagement score
        
    Returns:
        A brief explanation for why this moment was selected
    """
    # Base reason on duration
    duration = moment.duration
    
    if duration < 15:
        reason = "Short, focused clip suitable for social media"
    elif 15 <= duration <= 45:
        reason = "Optimal length for social sharing"
    else:
        reason = "Detailed segment with comprehensive content"
    
    # Add score-based assessment
    if score > 0.8:
        reason += " with excellent engagement potential"
    elif score > 0.6:
        reason += " with good engagement potential"
    
    return reason

def determine_content_category(moment: VideoMoment) -> str:
    """
    Determine the content category based on the moment description.
    
    Args:
        moment: The video moment to categorize
        
    Returns:
        A category string
    """
    description = moment.description.lower()
    
    # Simple keyword-based categorization
    if any(word in description for word in ["explain", "tutorial", "how", "learn", "guide"]):
        return "tutorial"
    elif any(word in description for word in ["demo", "demonstration", "showing", "showcase"]):
        return "demo"
    elif any(word in description for word in ["highlight", "key", "important", "critical"]):
        return "highlight"
    elif any(word in description for word in ["insight", "analysis", "perspective", "thought"]):
        return "insight"
    else:
        return "general"

def determine_suitable_platforms(moment: VideoMoment) -> List[str]:
    """
    Determine which platforms this content is suitable for.
    
    Args:
        moment: The video moment to evaluate
        
    Returns:
        List of suitable platform names
    """
    platforms = []
    duration = moment.duration
    
    # Platform suitability based on duration
    if duration <= 15:
        platforms.extend(["tiktok", "instagram", "twitter"])
    elif duration <= 60:
        platforms.extend(["instagram", "twitter", "linkedin"])
    else:
        platforms.extend(["youtube", "linkedin"])
    
    # Add or remove platforms based on content
    description = moment.description.lower()
    if any(word in description for word in ["professional", "business", "insight", "industry"]):
        platforms.append("linkedin")
    if any(word in description for word in ["educational", "tutorial", "learn", "how to"]):
        platforms.append("youtube")
    
    # Remove duplicates and return
    return list(set(platforms))

def moment_selection_agent(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Agent function that selects the most promising moments for processing.
    
    Args:
        state: Dictionary containing the current state with identified moments
        
    Returns:
        Updated state dictionary with selected moments
    """
    try:
        # Get previously identified moments
        identified_moments = state.get("identified_moments", [])
        
        # Check if moments exist in the "moments" field (for compatibility)
        if not identified_moments and "moments" in state:
            identified_moments = state["moments"]
            
        selected_moments = []
        
        # Score and select the best moments
        for moment in identified_moments:
            score = calculate_engagement_score(moment)
            
            # Only select moments with good potential
            if score > 0.6:
                selected = SelectedMoment(
                    start_time=moment.start_time,
                    end_time=moment.end_time,
                    description=moment.description,
                    engagement_score=moment.engagement_score,
                    engagement_prediction=score,
                    selection_reason=generate_selection_reason(moment, score),
                    content_category=determine_content_category(moment),
                    target_platforms=determine_suitable_platforms(moment)
                )
                selected_moments.append(selected)
        
        # Update state
        state["selected_moments"] = selected_moments
        return state
        
    except Exception as e:
        state["error"] = f"Error in moment selection: {str(e)}"
        return state

# Simple test function to directly test the agent
def test_moment_selection_agent():
    """Test the moment selection agent with sample moments."""
    # Create test moments
    test_moments = [
        VideoMoment(
            start_time=10.0, 
            end_time=25.0, 
            description="Tutorial explaining how to set up the environment"
        ),
        VideoMoment(
            start_time=45.0, 
            end_time=55.0, 
            description="Demo of the key features in action"
        ),
        VideoMoment(
            start_time=120.0, 
            end_time=240.0, 
            description="Detailed walkthrough of advanced techniques"
        )
    ]
    
    # Create a test state
    test_state = {
        "identified_moments": test_moments
    }
    
    # Call the agent
    result_state = moment_selection_agent(test_state)
    
    # Print the results
    if "error" in result_state:
        print(f"Error: {result_state['error']}")
    else:
        print(f"Selected {len(result_state['selected_moments'])} moments from {len(test_moments)} identified moments:")
        for i, moment in enumerate(result_state["selected_moments"]):
            print(f"Selected Moment {i+1}: {moment.start_time_str} - {moment.end_time_str}")
            print(f"  Description: {moment.description}")
            print(f"  Engagement: {moment.engagement_prediction:.2f}")
            print(f"  Reason: {moment.selection_reason}")
            print(f"  Category: {moment.content_category}")
            print(f"  Platforms: {', '.join(moment.target_platforms)}")
            print()

if __name__ == "__main__":
    test_moment_selection_agent() 