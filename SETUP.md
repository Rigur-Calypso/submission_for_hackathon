# Setup Guide

To ensure a fully reproducible environment, you should run the pipeline inside a virtual environment.

### 1. Create a virtual environment
Ensure you have Python 3.10+ installed. In the repository root, create a new virtual environment:

```bash
python3 -m venv .venv
```

### 2. Activate the virtual environment
- **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```
- **Windows**:
  ```bash
  .venv\Scripts\activate
  ```

### 3. Install requirements
Once activated, install all required dependencies using `pip`:

```bash
pip install -r solution/requirements.txt
```

### 4. Setup API Key
The pipeline defaults to using the Gemini LLM fallback for answering hidden questions that the deterministic engine cannot parse. Ensure your `GEMINI_API_KEY` is exported:

```bash
export GEMINI_API_KEY="your-api-key-here"
```

You are now ready to run `solution/run.py`!
