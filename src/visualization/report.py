"""
Report generation for video analysis results.
"""

import os
import json
import webbrowser
import subprocess
import shutil
from pathlib import Path


def extract_thumbnails(video_path, moments, output_dir="output/thumbnails"):
    """
    Extract thumbnail images for each identified moment using FFmpeg.
    
    Args:
        video_path: Path to the video file
        moments: List of VideoMoment objects
        output_dir: Directory to save thumbnails
        
    Returns:
        Dictionary mapping moment index to thumbnail path
    """
    # Create output directory if it doesn't exist
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    thumbnails = {}
    video_path = Path(video_path)
    
    for i, moment in enumerate(moments):
        # Generate output filename
        timestamp = f"{moment.start_time:.1f}s"
        output_file = output_path / f"moment_{i+1}_{timestamp}.jpg"
        
        # Use FFmpeg to extract the frame
        try:
            cmd = [
                "ffmpeg", 
                "-y",  # Overwrite output file if it exists
                "-ss", str(moment.start_time),  # Seek to start time
                "-i", str(video_path),  # Input file
                "-vframes", "1",  # Extract one frame
                "-q:v", "2",  # High quality
                str(output_file)  # Output file
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            thumbnails[i] = str(output_file)
        except subprocess.CalledProcessError as e:
            print(f"Error extracting thumbnail for moment {i+1}: {e}")
            continue
    
    return thumbnails


def get_video_metadata(video_path):
    """
    Get basic metadata about the video file.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        Dictionary containing video metadata
    """
    try:
        cmd = [
            "ffprobe", 
            "-v", "quiet", 
            "-print_format", "json", 
            "-show_format", 
            "-show_streams", 
            str(video_path)
        ]
        
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        data = json.loads(result.stdout)
        
        # Extract relevant metadata
        metadata = {}
        if "format" in data:
            metadata["duration"] = float(data["format"].get("duration", 0))
            metadata["size"] = int(data["format"].get("size", 0))
            metadata["bitrate"] = int(data["format"].get("bit_rate", 0))
            
        # Find video stream
        video_stream = None
        for stream in data.get("streams", []):
            if stream.get("codec_type") == "video":
                video_stream = stream
                break
                
        if video_stream:
            metadata["width"] = video_stream.get("width", 0)
            metadata["height"] = video_stream.get("height", 0)
            metadata["framerate"] = eval(video_stream.get("r_frame_rate", "0/1"))
            
        return metadata
    except (subprocess.CalledProcessError, json.JSONDecodeError, ValueError) as e:
        print(f"Error getting video metadata: {e}")
        return {}


def generate_timeline_html(metadata, moments):
    """
    Generate HTML for a visual timeline of the video.
    
    Args:
        metadata: Video metadata
        moments: List of VideoMoment objects
        
    Returns:
        HTML string for the timeline
    """
    duration = metadata.get("duration", 0)
    
    if duration <= 0:
        return "<p>Timeline unavailable: Invalid video duration</p>"
    
    # Generate timeline HTML
    html = """
    <div class="timeline-container">
        <div class="timeline">
            <div class="timeline-track"></div>
    """
    
    # Add time markers
    marker_interval = max(int(duration / 10), 1)  # Create ~10 markers
    for i in range(0, int(duration) + 1, marker_interval):
        position = (i / duration) * 100
        mins = i // 60
        secs = i % 60
        html += f"""
        <div class="time-marker" style="left: {position}%;">
            <div class="marker-line"></div>
            <div class="marker-time">{mins:02d}:{secs:02d}</div>
        </div>
        """
    
    # Add moments
    for i, moment in enumerate(moments):
        start_pos = (moment.start_time / duration) * 100
        end_pos = (moment.end_time / duration) * 100
        width = end_pos - start_pos
        
        # Use engagement score to determine color (red to green)
        color = "hsl(120, 70%, 60%)"  # Default to green
        if hasattr(moment, "engagement_score"):
            # Map 0-1 to hue 0-120 (red to green)
            hue = int(moment.engagement_score * 120)
            color = f"hsl({hue}, 70%, 60%)"
        
        html += f"""
        <div class="moment-marker" style="left: {start_pos}%; width: {width}%; background-color: {color};" 
             title="Moment {i+1}: {moment.description}">
            <span class="moment-label">{i+1}</span>
        </div>
        """
    
    html += """
        </div>
    </div>
    """
    
    return html


def generate_html_report(video_path, result, thumbnails=None):
    """
    Generate an HTML report of the analysis results.
    
    Args:
        video_path: Path to the video file
        result: Result dictionary from the analysis pipeline
        thumbnails: Dictionary mapping moment index to thumbnail path
        
    Returns:
        Tuple of (report_path, html_content)
    """
    if thumbnails is None:
        thumbnails = {}
    
    # Create output directory
    output_dir = Path("output/report")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Copy thumbnails to report directory
    report_images_dir = output_dir / "images"
    report_images_dir.mkdir(exist_ok=True)
    
    # Update thumbnail paths to be relative to the report
    report_thumbnails = {}
    for idx, path in thumbnails.items():
        src_path = Path(path)
        dest_path = report_images_dir / src_path.name
        shutil.copy2(src_path, dest_path)
        report_thumbnails[idx] = f"images/{src_path.name}"
    
    # Get video metadata
    metadata = get_video_metadata(video_path)
    
    # Generate HTML report
    moments = result.get("moments", [])
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Video Analysis Report</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1, h2, h3 {{
            color: #2c3e50;
        }}
        .metadata {{
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
        .metadata-item {{
            margin-bottom: 5px;
        }}
        .timeline-container {{
            margin: 30px 0;
        }}
        .timeline {{
            position: relative;
            height: 70px;
            background-color: #f8f9fa;
            border-radius: 5px;
            padding: 10px;
        }}
        .timeline-track {{
            position: absolute;
            top: 35px;
            left: 0;
            right: 0;
            height: 4px;
            background-color: #ddd;
        }}
        .time-marker {{
            position: absolute;
            top: 0;
            height: 70px;
        }}
        .marker-line {{
            position: absolute;
            top: 20px;
            height: 15px;
            width: 1px;
            background-color: #999;
        }}
        .marker-time {{
            position: absolute;
            top: 40px;
            transform: translateX(-50%);
            font-size: 12px;
            color: #666;
        }}
        .moment-marker {{
            position: absolute;
            height: 20px;
            top: 27px;
            border-radius: 3px;
            cursor: pointer;
        }}
        .moment-label {{
            display: inline-block;
            background-color: rgba(255, 255, 255, 0.7);
            border-radius: 50%;
            width: 20px;
            height: 20px;
            text-align: center;
            line-height: 20px;
            font-size: 12px;
            font-weight: bold;
        }}
        .moments-container {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
            gap: 20px;
        }}
        .moment-card {{
            border: 1px solid #ddd;
            border-radius: 5px;
            overflow: hidden;
        }}
        .moment-thumb {{
            width: 100%;
            height: 180px;
            object-fit: cover;
        }}
        .moment-info {{
            padding: 15px;
        }}
        .moment-time {{
            color: #666;
            font-size: 14px;
            margin-bottom: 5px;
        }}
        .moment-desc {{
            margin: 0;
        }}
    </style>
</head>
<body>
    <h1>Video Analysis Report</h1>
    
    <div class="metadata">
        <h2>Video Metadata</h2>
        <div class="metadata-item"><strong>Filename:</strong> {Path(video_path).name}</div>
        <div class="metadata-item"><strong>Duration:</strong> {int(metadata.get("duration", 0) // 60)}m {int(metadata.get("duration", 0) % 60)}s</div>
        <div class="metadata-item"><strong>Resolution:</strong> {metadata.get("width", 0)}×{metadata.get("height", 0)}</div>
        <div class="metadata-item"><strong>File Size:</strong> {metadata.get("size", 0) // (1024*1024)} MB</div>
        <div class="metadata-item"><strong>Framerate:</strong> {metadata.get("framerate", 0):.2f} fps</div>
    </div>
    
    <h2>Timeline Visualization</h2>
    {generate_timeline_html(metadata, moments)}
    
    <h2>Identified Moments ({len(moments)})</h2>
    <div class="moments-container">
    """
    
    # Add moment cards
    for i, moment in enumerate(moments):
        thumb_path = report_thumbnails.get(i, "")
        thumb_html = f'<img src="{thumb_path}" class="moment-thumb" alt="Moment {i+1}">' if thumb_path else ""
        
        start_mins = int(moment.start_time // 60)
        start_secs = int(moment.start_time % 60)
        end_mins = int(moment.end_time // 60)
        end_secs = int(moment.end_time % 60)
        duration = moment.end_time - moment.start_time
        
        html += f"""
        <div class="moment-card">
            {thumb_html}
            <div class="moment-info">
                <h3>Moment {i+1}</h3>
                <div class="moment-time">
                    {start_mins:02d}:{start_secs:02d} - {end_mins:02d}:{end_secs:02d} (Duration: {duration:.1f}s)
                </div>
                <p class="moment-desc">{moment.description}</p>
            </div>
        </div>
        """
    
    html += """
    </div>
</body>
</html>
    """
    
    # Write HTML to file
    report_path = output_dir / "analysis_report.html"
    with open(report_path, "w") as f:
        f.write(html)
    
    return str(report_path), html


def display_analysis_results(video_path, result, thumbnails=None):
    """
    Create an HTML report of the analysis results and open it in a browser.
    
    Args:
        video_path: Path to the video file
        result: Result dictionary from the analysis pipeline
        thumbnails: Dictionary mapping moment index to thumbnail path
        
    Returns:
        Path to the generated report
    """
    report_path, _ = generate_html_report(video_path, result, thumbnails)
    
    # Open in browser
    webbrowser.open(f"file://{Path(report_path).absolute()}")
    
    return report_path 