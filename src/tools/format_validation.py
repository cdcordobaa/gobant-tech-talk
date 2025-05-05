import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import ffmpeg
from typing import Optional

from src.models.state import PlatformContent

def validate_format_specs(content: PlatformContent) -> bool:
    """Placeholder function to validate FFmpeg parameters."""
    if not content.ffmpeg_params or not isinstance(content.ffmpeg_params, dict):
        print(f"Validation Error: Missing or invalid ffmpeg_params for {content.platform}")
        return False
    # Add more specific validation logic here (e.g., check keys, value types)
    print(f"Validation OK: ffmpeg_params for {content.platform} seem valid.")
    return True

def calculate_crop_parameters():
    """Placeholder for calculating crop parameters based on content analysis."""
    # This would involve analyzing frame content (e.g., salient object detection)
    # and video metadata (dimensions) to determine optimal crop box [x, y, w, h]
    pass

def generate_preview_thumbnail(
    video_path: str,
    content_item: PlatformContent,
    output_dir: str = "output/previews",
    timestamp: float = -1, # Time in seconds for the thumbnail, -1 for middle frame
    font_size: int = 20,
) -> Optional[str]:
    """Generates a thumbnail applying the planned FFmpeg transformations (approximated)."""
    if not content_item.ffmpeg_params:
        print(f"Cannot generate preview for {content_item.platform}: No ffmpeg_params.")
        return None

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    # Use a middle frame if no specific timestamp is given
    if timestamp < 0:
        timestamp = content_item.source_moment.start_time + content_item.source_moment.duration / 2

    base_filename = f"{Path(video_path).stem}_moment_{content_item.source_moment.start_time:.1f}s_{content_item.platform}_preview.jpg"
    output_path = output_dir_path / base_filename

    print(f"Generating preview thumbnail for {content_item.platform} at {timestamp:.2f}s -> {output_path}")

    try:
        # Get video dimensions
        probe = ffmpeg.probe(video_path)
        video_stream = next((s for s in probe['streams'] if s['codec_type'] == 'video'), None)
        if not video_stream:
            print(f"Error: Could not find video stream in {video_path}")
            return None
        width = int(video_stream['width'])
        height = int(video_stream['height'])

        # Extract frame using ffmpeg
        (ffmpeg
            .input(video_path, ss=timestamp)
            .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
            .run(capture_stdout=True, capture_stderr=True, quiet=True))

    except ffmpeg.Error as e:
        print(f"Error extracting frame with ffmpeg: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"Error during frame extraction setup: {e}")
        return None

    # Apply transformations using PIL (approximation of FFmpeg filtergraph)
    # This is complex to replicate perfectly. We'll handle simple cases.
    # A full solution might involve actually running ffmpeg.
    try:
        # Extract the raw frame first without transformations
        out_bytes, err_bytes = (
            ffmpeg
            .input(video_path, ss=timestamp)
            .output('pipe:', vframes=1, format='image2', vcodec='mjpeg')
            .run(capture_stdout=True, capture_stderr=True)
        )
        if not out_bytes:
            print(f"FFmpeg Error extracting frame: {err_bytes.decode()}")
            return None
        
        from io import BytesIO
        img = Image.open(BytesIO(out_bytes))
        original_width, original_height = img.size
        
        # --- Apply Approximate Transformations --- 
        # WARNING: This is a simplified simulation of ffmpeg filters
        vf_filter = content_item.ffmpeg_params.get("vf", "")
        target_aspect = content_item.target_specs.aspect_ratio # e.g., "1:1"
        target_w, target_h = content_item.target_specs.resolution

        # Example: Simple Center Crop logic based on target aspect
        current_aspect = original_width / original_height
        target_aspect_val = eval(target_aspect.replace(':', '/')) # Calculate float aspect

        crop_w, crop_h = original_width, original_height
        if current_aspect > target_aspect_val: # Wider than target -> crop sides
            crop_w = int(original_height * target_aspect_val)
            crop_h = original_height
        elif current_aspect < target_aspect_val: # Taller than target -> crop top/bottom
            crop_w = original_width
            crop_h = int(original_width / target_aspect_val)
        
        # Center crop calculation
        left = (original_width - crop_w) // 2
        top = (original_height - crop_h) // 2
        right = left + crop_w
        bottom = top + crop_h
        
        img = img.crop((left, top, right, bottom))
        
        # Resize to target resolution
        img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)
        # --- End Transformation Approximation ---

        # Add text overlay with platform and specs
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype("arial.ttf", font_size) # Requires font file
        except IOError:
            font = ImageFont.load_default()
            print("Warning: Arial font not found, using default PIL font.")
        
        text = f"{content_item.platform}\n{target_w}x{target_h} ({target_aspect})\nCrop/Scale Approx."
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        padding = 5
        rect_x0 = padding
        rect_y0 = padding
        rect_x1 = rect_x0 + text_width + 2 * padding
        rect_y1 = rect_y0 + text_height + 2 * padding
        draw.rectangle([rect_x0, rect_y0, rect_x1, rect_y1], fill="rgba(0, 0, 0, 128)")
        draw.text((rect_x0 + padding, rect_y0 + padding), text, fill="white", font=font)
        
        img.save(output_path, "JPEG")
        content_item.preview_thumbnail_path = str(output_path)
        print(f"  -> Preview saved: {output_path}")
        return str(output_path)

    except ffmpeg.Error as e:
        print(f"FFmpeg Error generating preview for {content_item.platform}: {e.stderr.decode()}")
        return None
    except Exception as e:
        print(f"Error processing image for preview {content_item.platform}: {e}")
        # Consider adding traceback here for debugging
        import traceback
        traceback.print_exc()
        return None 