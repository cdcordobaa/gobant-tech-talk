"""FFmpeg wrapper for video processing tasks."""

import ffmpeg
import os
import logging
import subprocess
from typing import Dict, Any, Optional

from src.models.state import ProcessingRequest, ProcessingResult, SelectedMoment

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class FFmpegProcessor:
    """Handles video processing using ffmpeg-python."""

    def __init__(self):
        """Initializes the FFmpeg processor."""
        # Placeholder for future configurations (e.g., ffmpeg path)
        pass

    def _get_video_duration(self, file_path: str) -> Optional[float]:
        """Get the duration of a video file using ffprobe."""
        try:
            probe = ffmpeg.probe(file_path)
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if video_stream and 'duration' in video_stream:
                return float(video_stream['duration'])
            # Fallback for containers where duration is in format section
            if 'format' in probe and 'duration' in probe['format']:
                 return float(probe['format']['duration'])
            logger.warning(f"Could not find duration in video stream or format for {file_path}")
            return None
        except ffmpeg.Error as e:
            logger.error(f"Error probing video {file_path}: {e.stderr.decode() if e.stderr else str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting duration for {file_path}: {e}")
            return None

    def extract_clip(self, source_path: str, start_time: float, end_time: float, output_path: str) -> bool:
        """Extracts a clip from source_path between start_time and end_time to output_path."""
        logger.info(f"Extracting clip from {source_path} ({start_time:.2f}s - {end_time:.2f}s) to {output_path}")
        duration = end_time - start_time
        if duration <= 0:
             logger.error(f"Invalid time range for clip extraction: start={start_time}, end={end_time}")
             return False
        try:
            (
                ffmpeg
                .input(source_path, ss=start_time, t=duration)
                .output(output_path, codec='copy') # Use stream copy for speed if no re-encoding needed
                .overwrite_output()
                .run(capture_stdout=True, capture_stderr=True)
            )
            logger.info(f"Successfully extracted clip to {output_path}")
            return True
        except ffmpeg.Error as e:
            logger.error(f"FFmpeg error during clip extraction: {e.stderr.decode() if e.stderr else str(e)}")
            # Try without codec copy if it failed (might be format issue)
            try:
                logger.warning("Retrying extraction without codec copy...")
                (
                    ffmpeg
                    .input(source_path, ss=start_time, t=duration)
                    .output(output_path) # Default codecs
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                logger.info(f"Successfully extracted clip to {output_path} (without codec copy)")
                return True
            except ffmpeg.Error as e2:
                 logger.error(f"FFmpeg error during clip extraction (retry): {e2.stderr.decode() if e2.stderr else str(e2)}")
                 return False
        except Exception as e:
            logger.error(f"Unexpected error during clip extraction: {e}")
            return False


    def apply_transformations(self, input_path: str, output_path: str, transformations: Dict[str, Any]) -> bool:
         """Applies transformations (e.g., crop, resize) to the input video."""
         logger.info(f"Applying transformations {transformations} to {input_path} -> {output_path}")
         if not os.path.exists(input_path):
             logger.error(f"Input file for transformations not found: {input_path}")
             return False

         stream = ffmpeg.input(input_path)
         vf_filters = []

         # Cropping: expects {'crop': [width, height, x, y]}
         if 'crop' in transformations:
             crop_params = transformations['crop']
             if len(crop_params) == 4:
                 w, h, x, y = crop_params
                 vf_filters.append(f"crop={w}:{h}:{x}:{y}")
                 logger.info(f"Applying crop: w={w}, h={h}, x={x}, y={y}")
             else:
                 logger.warning(f"Invalid crop parameters: {crop_params}. Expected [w, h, x, y].")

         # Resizing: expects {'resize': [width, height]}
         if 'resize' in transformations:
             resize_params = transformations['resize']
             if len(resize_params) == 2:
                 w, h = resize_params
                 # Use -1 to maintain aspect ratio if one dimension is 0 or None
                 scale_w = w if w else -1
                 scale_h = h if h else -1
                 if scale_w == -1 and scale_h == -1:
                      logger.warning("Resize requires at least one dimension.")
                 else:
                     vf_filters.append(f"scale={scale_w}:{scale_h}")
                     logger.info(f"Applying resize: w={scale_w}, h={scale_h}")
             else:
                 logger.warning(f"Invalid resize parameters: {resize_params}. Expected [w, h].")
         
         # Add more transformations here as needed (e.g., rotation, adding text)

         if vf_filters:
             stream = stream.filter('vf', ",".join(vf_filters))

         try:
             (
                 stream
                 .output(output_path)
                 .overwrite_output()
                 .run(capture_stdout=True, capture_stderr=True)
             )
             logger.info(f"Successfully applied transformations to {output_path}")
             return True
         except ffmpeg.Error as e:
             logger.error(f"FFmpeg error during transformations: {e.stderr.decode() if e.stderr else str(e)}")
             return False
         except Exception as e:
             logger.error(f"Unexpected error during transformations: {e}")
             return False


    def process_video(self, request: ProcessingRequest) -> ProcessingResult:
        """Processes a video according to the ProcessingRequest."""
        logger.info(f"Processing video request for moment: {request.moment.description}")
        
        temp_clip_path = f"{request.output_path}.temp_clip.mp4" # Intermediate file for the extracted clip
        final_output_path = request.output_path

        # Step 1: Extract the clip
        extract_success = self.extract_clip(
            source_path=request.source_path,
            start_time=request.moment.start_time,
            end_time=request.moment.end_time,
            output_path=temp_clip_path
        )

        if not extract_success:
            logger.error("Clip extraction failed.")
            # Clean up temp file if it exists
            if os.path.exists(temp_clip_path):
                try:
                    os.remove(temp_clip_path)
                except OSError as e:
                     logger.warning(f"Could not remove temporary clip file {temp_clip_path}: {e}")
            return ProcessingResult(
                request=request,
                status="error",
                error_message="Clip extraction failed"
            )

        # Step 2: Apply transformations if specified
        transform_input = temp_clip_path
        if request.format_specs:
            transform_success = self.apply_transformations(
                input_path=temp_clip_path,
                output_path=final_output_path,
                transformations=request.format_specs
            )
            if not transform_success:
                logger.error("Applying transformations failed.")
                 # Clean up temp file
                if os.path.exists(temp_clip_path):
                    try:
                        os.remove(temp_clip_path)
                    except OSError as e:
                         logger.warning(f"Could not remove temporary clip file {temp_clip_path}: {e}")
                return ProcessingResult(
                    request=request,
                    status="error",
                    error_message="Applying transformations failed"
                )
            # Transformations were applied, final output is ready
            # Clean up the intermediate clip file
            if os.path.exists(temp_clip_path):
                 try:
                     os.remove(temp_clip_path)
                 except OSError as e:
                      logger.warning(f"Could not remove temporary clip file {temp_clip_path}: {e}")
        else:
            # No transformations, just rename the temp clip to the final output path
            logger.info("No transformations specified, renaming temporary clip.")
            try:
                os.rename(temp_clip_path, final_output_path)
            except OSError as e:
                logger.error(f"Failed to rename temporary clip {temp_clip_path} to {final_output_path}: {e}")
                 # Clean up temp file
                if os.path.exists(temp_clip_path):
                    try:
                        os.remove(temp_clip_path)
                    except OSError as e_rem:
                         logger.warning(f"Could not remove temporary clip file {temp_clip_path}: {e_rem}")
                return ProcessingResult(
                    request=request,
                    status="error",
                    error_message=f"Failed to finalize output file: {e}"
                )


        # Step 3: Get metadata of the final output
        duration = self._get_video_duration(final_output_path)
        file_size = None
        try:
            file_size = os.path.getsize(final_output_path)
        except OSError as e:
            logger.warning(f"Could not get file size for {final_output_path}: {e}")


        logger.info(f"Successfully processed video request to {final_output_path}")
        return ProcessingResult(
            request=request,
            status="success",
            output_path=final_output_path,
            duration=duration,
            file_size=file_size
        )

# Example Usage (Optional - for testing)
if __name__ == '__main__':
    # This block is for demonstration/testing purposes
    # You would typically import and use FFmpegProcessor elsewhere
    
    # Create dummy data for testing
    source_video = 'test_input.mp4' # Make sure this file exists
    output_dir = 'output_clips'
    os.makedirs(output_dir, exist_ok=True)
    
    # Create a dummy source video file if it doesn't exist (requires ffmpeg CLI)
    if not os.path.exists(source_video):
         print(f"Creating dummy source video: {source_video}")
         try:
            # Create a 10-second black video with silent audio
            cmd = [
                 'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=1280x720:r=30', 
                 '-f', 'lavfi', '-i', 'anullsrc=channel_layout=stereo:sample_rate=44100', 
                 '-t', '10', '-pix_fmt', 'yuv420p', '-c:a', 'aac', source_video
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"Dummy video created successfully.")
         except (subprocess.CalledProcessError, FileNotFoundError) as e:
             print(f"Error creating dummy video. Make sure ffmpeg CLI is installed and in PATH. Error: {e}")
             exit(1)


    processor = FFmpegProcessor()

    # Example 1: Extract a simple clip
    moment1 = SelectedMoment(start_time=2.0, end_time=5.0, description="Clip 1", selection_reason="Test", engagement_prediction=0.8, content_category="Test", target_platforms=["test"])
    request1 = ProcessingRequest(
        source_path=source_video,
        moment=moment1,
        output_path=os.path.join(output_dir, 'clip1_simple.mp4'),
        format_specs={} # No transformations
    )
    result1 = processor.process_video(request1)
    print(f"Result 1: {result1.status}, Path: {result1.output_path}, Duration: {result1.duration}, Size: {result1.file_size}, Error: {result1.error_message}")

    # Example 2: Extract and transform (crop and resize)
    moment2 = SelectedMoment(start_time=6.0, end_time=8.0, description="Clip 2", selection_reason="Test", engagement_prediction=0.9, content_category="Test", target_platforms=["test"])
    request2 = ProcessingRequest(
        source_path=source_video,
        moment=moment2,
        output_path=os.path.join(output_dir, 'clip2_transformed.mp4'),
        format_specs={
            'crop': [640, 360, 320, 180], # w, h, x, y - Crop the center
            'resize': [300, 0] # Resize width to 300px, maintain aspect ratio
        }
    )
    result2 = processor.process_video(request2)
    print(f"Result 2: {result2.status}, Path: {result2.output_path}, Duration: {result2.duration}, Size: {result2.size}, Error: {result2.error_message}")

    # Example 3: Invalid request (e.g., source file doesn't exist)
    moment3 = SelectedMoment(start_time=1.0, end_time=3.0, description="Clip 3", selection_reason="Test", engagement_prediction=0.7, content_category="Test", target_platforms=["test"])
    request3 = ProcessingRequest(
        source_path='non_existent_video.mp4',
        moment=moment3,
        output_path=os.path.join(output_dir, 'clip3_fail.mp4'),
        format_specs={}
    )
    # Manually trigger validation or let process_video handle it
    try:
         req_validated = ProcessingRequest(
             source_path='non_existent_video.mp4',
             moment=moment3,
             output_path=os.path.join(output_dir, 'clip3_fail.mp4'),
             format_specs={}
         )
         result3 = processor.process_video(req_validated)
         print(f"Result 3: {result3.status}, Error: {result3.error_message}")
    except ValueError as e:
         print(f"Result 3 (Validation Error): {e}") # Pydantic validation should catch this 