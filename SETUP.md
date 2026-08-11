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

### 4. Optional API Key
The submission pipeline is deterministic by default. It writes an adjacent
`*.audit.csv` file containing the detected question shape, resolved entities,
and any unresolved questions for review.

If you want to use the optional Gemini fallback only for unresolved questions,
export a key and pass `--use-llm` explicitly:

```bash
export GEMINI_API_KEY="your-api-key-here"
python solution/run.py --questions questions.json --output submission.csv --skip-build --use-llm
```

You are now ready to run `solution/run.py`!
