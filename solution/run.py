#!/usr/bin/env python3

# BidDesk Analytics Engine
# Authored by rigur_calypso
# This orchestration script manages the end-to-end execution of the data extraction pipeline.

import os
import sys
import json
import csv
import argparse
import subprocess
from pathlib import Path

# Parse args before chdir so relative paths resolve against original PWD
parser = argparse.ArgumentParser(description="Run BidDesk Pipeline")
parser.add_argument("--questions", default="../questions.json", help="Path to questions JSON file")
parser.add_argument("--output", default="submission.csv", help="Path to output CSV file")
parser.add_argument("--skip-build", action="store_true", help="Skip database rebuild")
parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds between LLM requests")
args = parser.parse_args()

# Resolve paths while still in original PWD
args.questions = str(Path(args.questions).resolve())
args.output = str(Path(args.output).resolve())

# Now chdir to the script directory
current_dir = Path(__file__).resolve().parent
os.chdir(current_dir)

from utils.logger import setup_logger
logger = setup_logger(name="biddesk", log_file="logs/run.log")

def run_cmd(cmd, check=True):

    logger.info(f"Executing: {' '.join(cmd)}")
    res = subprocess.run(cmd)
    if check and res.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {res.returncode}")
    return res

def convert_jsonl_to_csv(jsonl_path, csv_path):
    logger.info(f"Converting {jsonl_path} to CSV format: {csv_path}")
    if not os.path.exists(jsonl_path):
        logger.error(f"{jsonl_path} does not exist. Cannot convert to CSV.")
        return False
    try:
        with open(jsonl_path, "r", encoding="utf-8-sig") as f_in:
            lines = f_in.readlines()
            
        with open(csv_path, "w", newline="", encoding="utf-8") as f_out:
            writer = csv.writer(f_out)
            writer.writerow(["question_id", "answer"])
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                line = line.replace('\x00', '')
                line = line.strip('\ufeff')
                try:
                    item = json.loads(line)
                    writer.writerow([item.get("qid"), item.get("answer")])
                except json.JSONDecodeError as je:
                    logger.warning(f"Failed to decode line: {repr(line)}. Error: {je}")
        return True
    except Exception as e:
        logger.error(f"Error during CSV conversion: {e}", exc_info=True)
        return False
def main():
    # Create directories for logs and output
    Path("output").mkdir(exist_ok=True)
    Path("logs").mkdir(exist_ok=True)

    logger.info("=== Step 1: Install Requirements ===")
    run_cmd([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
    run_cmd([sys.executable, "-m", "pip", "install", "python-dotenv", "openai"])
    
    db_path = "knowledge_graph.db"
    if not args.skip_build:
        logger.info("=== Step 2: Build Database ===")
        try:
            run_cmd([sys.executable, "graph/build_db.py", "--db", db_path])
        except Exception as e:
            logger.warning(f"Database build failed: {e}. Proceeding with existing database.")
    
    logger.info(f"=== Step 3: Convert {args.questions} to output/questions.jsonl ===")
    src_questions = Path(args.questions).resolve()
    out_questions = Path("output/questions.jsonl")
    
    if not src_questions.exists():
        logger.error(f"Questions source path {src_questions} does not exist!")
        sys.exit(1)
        
    with open(src_questions, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    questions = data.get("questions", data.get("answers", []))
    logger.info(f"Loaded {len(questions)} questions from {src_questions}")
    
    with open(out_questions, "w", encoding="utf-8") as f:
        for q in questions:
            json.dump({
                "qid": q["qid"],
                "question": q["question"],
                "answer_type": q.get("answer_type", "money"),
            }, f)
            f.write("\n")
    logger.info(f"Wrote questions to {out_questions}")
    
    logger.info("=== Step 4: Run Pipeline ===")
    submission_jsonl = Path("output/submission.jsonl")
    run_log_json = Path("logs/run_log.json")
    
    run_cmd([
        sys.executable,
        "pipeline.py",
        "--db", db_path,
        "--questions", str(out_questions),
        "--out", str(submission_jsonl),
        "--log", str(run_log_json),
        "--delay", str(args.delay)
    ], check=False)
    
    logger.info("=== Step 5: Convert Output to CSV ===")
    submission_csv = Path("output/submission.csv")
    success = convert_jsonl_to_csv(str(submission_jsonl), str(submission_csv))
    if success and submission_csv.exists():
        import shutil
        # Copy to the exact requested output path
        shutil.copy(submission_csv, Path(args.output).resolve())
        logger.info(f"Successfully generated {args.output}")
    else:
        logger.error("CSV conversion failed.")
    
    
if __name__ == "__main__":
    main()
