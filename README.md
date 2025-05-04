# Social Media Content Automation System

An intelligent system for automating social media content creation using agentic workflows. This system processes video content, extracts engaging moments, and formats them for different social platforms.

## Features

- Video analysis and key moment detection
- Automated clip extraction and formatting
- Platform-specific content optimization
- Multi-agent workflow orchestration

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/social-media-automation.git
cd social-media-automation
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

## Configuration

1. Copy the example environment file:

```bash
cp .env.example .env
```

2. Edit `.env` to add your API keys and customize settings:

```
GEMINI_API_KEY=your_gemini_api_key_here
```

3. Place your sample videos in the `examples/` directory.

## Usage

Basic usage example:

```python
from src.workflows import create_video_processing_workflow

# Initialize the workflow
workflow = create_video_processing_workflow()

# Run the workflow on a video
result = workflow.run("examples/your_video.mp4")
```

## Project Structure

```
social-media-automation/
├── src/                   # Source code
│   ├── models/            # State models for workflow data
│   ├── agents/            # Agent implementations
│   ├── workflows/         # Workflow definitions using LangGraph
│   ├── tools/             # External tool integrations
│   └── utils.py           # Utility functions
├── examples/              # Example videos
├── tests/                 # Test suite
├── requirements.txt       # Project dependencies
├── .env.example           # Environment variable template
└── README.md              # This file
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
