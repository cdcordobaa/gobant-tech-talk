import os
import google.generativeai as genai
from typing import List, Dict
import logging

from src.models.state import WorkflowState, SelectedMoment, PlatformContent, PlatformRequirements, SUPPORTED_PLATFORMS, PLATFORM_INSTAGRAM, PLATFORM_TIKTOK, PLATFORM_LINKEDIN

# Platform requirements (keep these defined)
PLATFORM_SPECS = {
    PLATFORM_INSTAGRAM: PlatformRequirements(
        platform_name=PLATFORM_INSTAGRAM, aspect_ratio="1:1", max_duration=60.0,
        optimal_format="square", resolution=(1080, 1080)
    ),
    PLATFORM_TIKTOK: PlatformRequirements(
        platform_name=PLATFORM_TIKTOK, aspect_ratio="9:16", max_duration=180.0,
        optimal_format="vertical", resolution=(1080, 1920)
    ),
    PLATFORM_LINKEDIN: PlatformRequirements(
        platform_name=PLATFORM_LINKEDIN, aspect_ratio="16:9", max_duration=600.0,
        optimal_format="landscape", resolution=(1920, 1080)
    ),
}

class PlatformRouterAgent:
    """
    Analyzes selected moments using the Gemini API and routes them to appropriate platforms.
    Uses a single batch API call for efficiency.
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash') # Or choose another appropriate model
        print("PlatformRouterAgent initialized with Gemini model.")

    def _generate_batch_routing_prompt(self, moments: List[SelectedMoment]) -> str:
        """Creates a single prompt for Gemini API routing analysis for multiple moments."""
        moments_text = ""
        for i, moment in enumerate(moments):
            moments_text += (
                f"Moment {i+1}:\n"
                f"- ID: MOMENT_{i+1}\n" # Assign temporary ID for easy reference in response
                f"- Description: {moment.description}\n"
                f"- Duration: {moment.duration:.1f} seconds\n"
                f"- Content Category: {moment.content_category}\n\n"
            )

        prompt = (
            f"Analyze the following {len(moments)} video moments:\n\n"
            f"{moments_text}"
            f"For each moment identified by its ID (e.g., MOMENT_1), determine its suitability for these platforms: {', '.join(SUPPORTED_PLATFORMS)}.\n"
            f"Consider typical content, audience, and format for each platform.\n"
            f"Provide the results strictly in the following JSON format, with one entry per moment:\n"
            f"```json\n"
            f"{{\"results\": [\n"
            f"  {{\"moment_id\": \"MOMENT_1\", \"routing\": {{ \"Instagram\": {{\"suitable\": true/false, \"reason\": \"brief justification\"}}, \"TikTok\": {{...}}, \"LinkedIn\": {{...}} }} }},\n"
            f"  {{\"moment_id\": \"MOMENT_2\", \"routing\": {{ ... }} }},\n"
            f"  // ... other moments ...\n"
            f"]}}\n"
            f"```\n"
            f"Ensure the output is valid JSON. Provide suitability (true/false) and a brief reason for each platform for every moment."
        )
        return prompt

    def _parse_batch_response(self, response_text: str, moments: List[SelectedMoment]) -> Dict[str, List[PlatformContent]]:
        """Parses the Gemini response using regex for more robustness."""
        import re
        
        routed_content: dict[str, list[PlatformContent]] = {p: [] for p in SUPPORTED_PLATFORMS}
        moment_map = {f"MOMENT_{i+1}": moment for i, moment in enumerate(moments)}

        # Regex to find blocks for each moment_id
        # It looks for "moment_id": "MOMENT_X" and captures everything until the next potential moment_id or end of results array
        moment_blocks = re.findall(r'{\s*"moment_id":\s*"(MOMENT_\d+)",\s*"routing":\s*({.*?})\s*}', response_text, re.DOTALL)

        if not moment_blocks:
             logging.warning(f"Could not find any moment blocks using regex in response:\n{response_text}")
             # Try a simpler regex if the above failed, looking just for suitability lines per platform
             # This is a fallback and less structured
             print("  Attempting fallback regex parsing...")
             # Example fallback (less reliable): extract suitability per platform based on keywords
             # This would need significant refinement based on observed response variations.
             # For now, let's raise an error if the primary regex fails.
             raise ValueError("Failed to extract moment routing blocks via regex.")

        for moment_id, routing_block_str in moment_blocks:
            moment = moment_map.get(moment_id)
            if not moment:
                logging.warning(f"Found block for unknown {moment_id}, skipping.")
                continue
                
            print(f"  Processing routing for {moment_id} ({moment.description[:30]}...)")

            # Parse suitability for each platform within this moment's block
            for platform_name in SUPPORTED_PLATFORMS:
                # Regex to find platform suitability (true/false) and reason within the block
                # Makes reason optional and non-greedy
                platform_match = re.search(
                    r'"' + platform_name + r'":\s*{\s*"suitable":\s*(true|false),\s*"reason":\s*"(.*?)"\s*}',
                    routing_block_str,
                    re.IGNORECASE | re.DOTALL
                )
                
                is_suitable = False
                reason = "Parsing failed"
                
                if platform_match:
                    suitability_str = platform_match.group(1).lower()
                    is_suitable = (suitability_str == 'true')
                    reason = platform_match.group(2).strip().replace('\n', ' ') # Clean reason
                    print(f"    -> Parsed for {platform_name}: Suitable={is_suitable}. Reason: {reason}")
                else:
                    logging.warning(f"Could not parse details for {platform_name} in block for {moment_id}")
                    print(f"    -> Failed to parse details for {platform_name}")
                    # Attempt to find suitability just by keyword as a last resort
                    if f'"{platform_name}":' in routing_block_str and '"suitable": true' in routing_block_str.split(f'"{platform_name}":')[1]:
                         is_suitable = True
                         reason = "Parsed fallback: suitable=true"
                         print(f"    -> Fallback Parse for {platform_name}: Suitable=true")
                    elif f'"{platform_name}":' in routing_block_str and '"suitable": false' in routing_block_str.split(f'"{platform_name}":')[1]:
                         is_suitable = False
                         reason = "Parsed fallback: suitable=false"
                         print(f"    -> Fallback Parse for {platform_name}: Suitable=false")

                # Add to routed_content if suitable and passes duration check
                if is_suitable and platform_name in PLATFORM_SPECS:
                    specs = PLATFORM_SPECS[platform_name]
                    if moment.duration <= specs.max_duration:
                        print(f"    --> Adding {platform_name} to routing list.")
                        content = PlatformContent(
                            platform=platform_name,
                            source_moment=moment,
                            target_specs=specs,
                            processing_status="pending_format"
                        )
                        routed_content[platform_name].append(content)
                    else:
                        print(f"    --> Skipped {platform_name} (duration {moment.duration:.1f}s > max {specs.max_duration:.1f}s)")
                elif not is_suitable:
                     print(f"    -> Determined Unsuitable for {platform_name}. Reason: {reason}")
            
        return routed_content

    def route_moments(self, state: WorkflowState) -> WorkflowState:
        """
        Uses a single Gemini API call to determine platform suitability and updates the state.
        """
        print("--- Running Platform Router Agent (using Gemini API - Batch Mode) ---")
        
        if not state.selected_moments:
             print("  No moments selected, skipping routing.")
             state.platform_content = {p: [] for p in SUPPORTED_PLATFORMS}
             return state
             
        prompt = self._generate_batch_routing_prompt(state.selected_moments)
            
        try:
            print(f"    > Calling Gemini API for batch routing analysis ({len(state.selected_moments)} moments)...")
            # Consider adding safety_settings if needed
            response = self.model.generate_content(prompt)
            analysis_text = response.text
            print(f"    < Gemini Batch Response:\n{analysis_text}")

            routed_content = self._parse_batch_response(analysis_text, state.selected_moments)
            state.platform_content = routed_content
            state.error = None # Clear error if successful

        except Exception as e:
            error_msg = f"Error during batch Gemini call or parsing: {e}"
            print(f"    ! {error_msg}")
            state.error = error_msg
            # Ensure platform_content is empty dict on error to prevent partial states
            state.platform_content = {p: [] for p in SUPPORTED_PLATFORMS}
                
        print(f"--- Platform Router Agent Finished ---")
        return state 