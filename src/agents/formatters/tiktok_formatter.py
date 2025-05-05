import os
import google.generativeai as genai
import re

from src.models.state import WorkflowState, PlatformContent

class TikTokFormatterAgent:
    """
    Formats content specifically for TikTok using Gemini API for suggestions.
    """
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("Gemini API key is required.")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.platform_name = "TikTok"
        print(f"{self.platform_name}FormatterAgent initialized with Gemini model.")

    def _generate_format_prompt(self, content_item: PlatformContent) -> str:
        """Creates the prompt for Gemini API formatting analysis."""
        moment = content_item.source_moment
        specs = content_item.target_specs
        prompt = (
            f"Analyze the following video moment description for formatting on {self.platform_name}:\n"
            f"- Description: {moment.description}\n"
            f"- Duration: {moment.duration:.1f} seconds\n"
            f"- Content Category: {moment.content_category}\n\n"
            f"Target {self.platform_name} Specifications:\n"
            f"- Aspect Ratio: {specs.aspect_ratio}\n"
            f"- Resolution: {specs.resolution[0]}x{specs.resolution[1]}\n"
            f"- Optimal Format: {specs.optimal_format}\n\n"
            f"Based *only* on the description, suggest FFmpeg parameters for the 'vf' (video filter) option to best format this moment. "
            f"Focus on cropping and scaling for a vertical {specs.aspect_ratio} output. Assume the main subject is centered unless the description implies otherwise. "
            f"Provide *only* the parameter string suitable for an ffmpeg command, like this:\n"
            f"vf_params: crop=iw*9/16:ih,scale=1080:1920\n"
            f"(Ensure the output resolution matches {specs.resolution[0]}x{specs.resolution[1]})."
        )
        return prompt

    def _parse_ffmpeg_params(self, response_text: str) -> dict:
        """Extracts vf parameters from Gemini response (simple parsing)."""
        match = re.search(r"^vf_params:\s*(.*)", response_text, re.MULTILINE | re.IGNORECASE)
        if match:
            vf_filter = match.group(1).strip()
            if 'crop=' in vf_filter or 'scale=' in vf_filter:
                 return {"vf": vf_filter, "aspect": "9:16"}
        print("    ! Failed to parse vf_params from Gemini response, using default.")
        return {"vf": "crop=iw*9/16:ih,scale=1080:1920", "aspect": "9:16"} # Default

    def format_content(self, state: WorkflowState) -> WorkflowState:
        """
        Processes content routed to TikTok, using Gemini to define formatting specs.
        """
        print(f"--- Running {self.platform_name} Formatter Agent (using Gemini API) ---")
        if self.platform_name in state.platform_content:
            for content_item in state.platform_content[self.platform_name]:
                 if content_item.processing_status == "pending_format":
                    print(f"  Formatting for {self.platform_name}: Moment {content_item.source_moment.start_time_str} ({content_item.source_moment.description[:30]}...)")
                    prompt = self._generate_format_prompt(content_item)
                    try:
                        print("    > Calling Gemini API for formatting analysis...")
                        response = self.model.generate_content(prompt)
                        analysis_text = response.text
                        print(f"    < Gemini Response:\n{analysis_text}")
                        
                        ffmpeg_params = self._parse_ffmpeg_params(analysis_text)
                        content_item.ffmpeg_params = ffmpeg_params
                        content_item.processing_status = "formatting_specs_defined"
                        print(f"    -> Specs defined (via Gemini): {content_item.ffmpeg_params}")
                        
                    except Exception as e:
                        print(f"    ! Error calling Gemini API or parsing response: {e}")
                        content_item.ffmpeg_params = {"vf": "crop=iw*9/16:ih,scale=1080:1920", "aspect": "9:16"}
                        content_item.processing_status = "formatting_specs_defined"
                        print(f"    -> Specs defined (Default Fallback): {content_item.ffmpeg_params}")
                        state.error = f"Gemini formatting failed for {self.platform_name} moment {content_item.source_moment.start_time_str}: {e}"

        print(f"--- {self.platform_name} Formatter Agent Finished ---")
        return state 