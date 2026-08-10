#!/usr/bin/env python3
"""
run.py — Main entry point for the BITS Hackathon solution.

Usage:
  # Full pipeline: extract → build KG → fix grading → answer questions
  python run.py --questions hidden_questions.json --output submission.jsonl

  # Just answer questions (if KG already built)
  python run.py --questions hidden_questions.json --output submission.jsonl --skip-build

  # Validate against sample questions
  python run.py --validate
"""
import argparse
import json
import os
import sqlite3
import subprocess
import sys

SOLUTION_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SOLUTION_DIR, 'knowledge_graph.db')
EXTRACTED_PATH = os.path.join(SOLUTION_DIR, 'extracted_data.json')


def run_pipeline():
    """Run the full extraction → KG build → grading fix pipeline."""
    print("=" * 60)
    print("PHASE 1: Extracting documents...")
    print("=" * 60)
    subprocess.run([sys.executable, os.path.join(SOLUTION_DIR, 'extract.py')], check=True)
    
    print("\n" + "=" * 60)
    print("PHASE 2: Building knowledge graph...")
    print("=" * 60)
    subprocess.run([sys.executable, os.path.join(SOLUTION_DIR, 'build_kg.py')], check=True)
    
    print("\n" + "=" * 60)
    print("PHASE 3: Fixing gradings from CC documents...")
    print("=" * 60)
    fix_gradings()
    
    print("\n✅ Pipeline complete!")


def fix_gradings():
    """Fix missing gradings by scanning CC documents directly."""
    import re

    import pdfplumber
    
    BASE = os.path.join(SOLUTION_DIR, '..', 'documents')
    db = sqlite3.connect(DB_PATH)
    
    missing = db.execute("""
        SELECT project_id, project_name, cc_ref
        FROM projects WHERE grading = '' OR grading IS NULL
    """).fetchall()
    
    fixed = 0
    for pid, pname, cc_ref in missing:
        grading = None
        if cc_ref:
            ref_num = re.search(r'/(\d+)$', cc_ref)
            if ref_num:
                cc_num = int(ref_num.group(1))
                cc_fname = f"DOC-CC-{cc_num:03d}.pdf"
                cc_path = os.path.join(BASE, "completion_certificate", cc_fname)
                if os.path.exists(cc_path):
                    with pdfplumber.open(cc_path) as pdf:
                        all_text = ''
                        for page in pdf.pages:
                            text = page.extract_text()
                            if text: all_text += text + '\n'
                        
                        # First try fast regex
                        grading = _extract_grading_cc(all_text)
                        
                        # If regex fails, use Gemini LLM as fallback
                        if not grading and 'GEMINI_API_KEY' in os.environ:
                            grading = _extract_grading_llm(all_text)
        
        if grading:
            db.execute("UPDATE projects SET grading = ? WHERE project_id = ?", (grading, pid))
            fixed += 1
    
    db.commit()
    still_missing = db.execute(
        "SELECT COUNT(*) FROM projects WHERE grading = '' OR grading IS NULL"
    ).fetchone()[0]
    print(f"  Fixed {fixed} gradings, {still_missing} still missing")
    db.close()

def _extract_grading_llm(text: str, model_name: str = 'gemini-3.5-flash') -> str | None:
    """Use Gemini to extract grading from prose completion certificates."""
    import os

    import google.generativeai as genai
    genai.configure(api_key=os.environ['GEMINI_API_KEY'])
    model = genai.GenerativeModel(model_name)
    
    prompt = (
        "Extract the performance/quality grading from the following completion certificate text. "
        "Valid gradings are ONLY one of: Excellent, Very Good, Good, Satisfactory. "
        "IMPORTANT: If the document ONLY says 'quality of work has been found satisfactory during the final inspection', "
        "that is just boilerplate, so you must return NONE. Only return Satisfactory if it says 'satisfactory completion' or 'assessed as Satisfactory'. "
        "If there is absolutely no mention of a formal grading, return NONE.\n\n"
        "Document Text:\n"
        f"{text}\n\n"
        "Grading:"
    )
    
    import time
    for attempt in range(5):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(temperature=0.0)
            )
            ans = response.text.strip().title()
            if ans in ['Excellent', 'Very Good', 'Good', 'Satisfactory']:
                return ans
            return None
        except Exception as e:
            if '429' in str(e):
                print("  [LLM Extraction Error] 429 Rate Limit. Sleeping 60s...")
                time.sleep(60)
            else:
                print(f"  [LLM Extraction Error] {e}")
                return None
    return None


def _extract_grading_cc(text):
    """Extract grading from CC document text."""
    import re
    
    # Explicit assessment
    m = re.search(
        r'assessed\s+(?:the\s+)?(?:completed\s+)?work\s+as\s+(Excellent|Very Good|Good|Satisfactory)',
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).title()
    
    # Table format: "Quality Assessment\nSatisfactory"
    m = re.search(
        r'Quality\s+Assessment\s+(?:Remarks\s+)?\n?\s*(Excellent|Very Good|Good|Satisfactory)',
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).title()
    
    # Standalone grade after Assessment header
    m = re.search(
        r'Assessment\s*\n\s*(Excellent|Very Good|Good|Satisfactory)\s*\n',
        text, re.IGNORECASE | re.MULTILINE
    )
    if m:
        return m.group(1).title()
    
    # "good standard"
    if re.search(r'\bgood\s+standard\b', text, re.IGNORECASE):
        return 'Good'
    if re.search(r'\bcommendable\b', text, re.IGNORECASE):
        return 'Excellent'
    
    # "satisfactory completion" (formal signal, not boilerplate)
    if re.search(r'\bsatisfactory\s+completion\b', text, re.IGNORECASE):
        return 'Satisfactory'
    
    return None


def answer_questions(questions_path: str, output_path: str, use_llm: bool = False, model_name: str = 'gemini-3.5-flash'):
    """Answer questions and write submission JSONL."""
    sys.path.insert(0, SOLUTION_DIR)
    
    import query_engine
    if use_llm:
        import llm_query_engine
    
    db = sqlite3.connect(DB_PATH)
    
    # Load questions
    with open(questions_path) as f:
        data = json.load(f)
    
    questions = data.get('questions', data) if isinstance(data, dict) else data
    
    print(f"\nAnswering {len(questions)} questions...")
    
    results = []
    with open(output_path, 'w') as f:
        f.write("question_id,answer\n")
        for q in questions:
            res = query_engine.answer_question(q['question'], db)
            val = res.value
            
            # Controlled LLM fallback if enabled and regex engine unsupported
            if use_llm and res.status == query_engine.AnswerStatus.UNSUPPORTED:
                print(f"  Fallback to LLM classification for: {q['qid']}")
                intent = llm_query_engine.llm_classify_question(q['question'], model_name=model_name)
                
                # Resolve fuzzy entity names returned by LLM
                clients = [row[0] for row in db.execute("SELECT DISTINCT client_name FROM projects").fetchall()]
                engineers = [row[0] for row in db.execute("SELECT DISTINCT name FROM engineers").fetchall()]
                categories = [row[0] for row in db.execute("SELECT DISTINCT category FROM projects").fetchall()]
                
                if intent.get('client'):
                    intent['client'] = query_engine.find_best_entity_match(intent['client'], clients)
                if intent.get('engineer'):
                    intent['engineer'] = query_engine.find_best_entity_match(intent['engineer'], engineers)
                if intent.get('exclude_category'):
                    intent['exclude_category'] = query_engine.find_best_entity_match(intent['exclude_category'], categories, threshold=60)
                
                print(f"    Classified Intent: {intent}")
                res = query_engine.answer_question_with_intent(q['question'], intent, db)
                
                # Raw-SQL fallback if the shape is unknown or unsupported
                if res.status == query_engine.AnswerStatus.UNSUPPORTED:
                    print(f"    Intent-based routing unsupported. Falling back to raw-SQL for: {q['qid']}")
                    val = llm_query_engine.answer_question(q['question'], db, model_name=model_name)
                else:
                    val = res.value
            else:
                val = res.value
            
            qid = q['qid']
            ans_str = str(int(val)) if isinstance(val, float) and val.is_integer() else str(val)
            f.write(f"{qid},{ans_str}\n")
            results.append({'qid': qid, 'answer': ans_str})
            
            print(f"  {qid}: answer={ans_str}")
    
    print(f"\n✅ Submission written to {output_path}")
    print(f"   {len(results)} answers")
    
    db.close()
    return results


def validate(use_llm: bool = False, model_name: str = 'gemini-3.5-flash'):
    """Validate against sample questions using the official evaluator."""
    sample_path = os.path.join(SOLUTION_DIR, '..', 'sample_questions.json')
    out_dir = os.path.join(SOLUTION_DIR, '..', 'output')
    os.makedirs(out_dir, exist_ok=True)
    output_path = os.path.join(out_dir, 'sample_submission.csv')
    
    # Generate answers
    answer_questions(sample_path, output_path, use_llm, model_name)
    
    # Run official evaluator
    evaluator_path = os.path.join(SOLUTION_DIR, '..', 'evaluate.py')
    print("\n" + "=" * 60)
    print("OFFICIAL EVALUATOR RESULTS:")
    print("=" * 60)
    subprocess.run([
        sys.executable, evaluator_path,
        '--submission', output_path,
        '--questions', sample_path,
        '--per-question'
    ])


def load_env():
    """Load environment variables from .env file manually."""
    env_path = os.path.join(SOLUTION_DIR, '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

def main():
    parser = argparse.ArgumentParser(description="BITS Hackathon Pipeline")
    parser.add_argument('--questions', help='Path to questions JSON file')
    parser.add_argument('--output', default='output/submission.csv', help='Output CSV path')
    parser.add_argument('--skip-build', action='store_true', help="Skip rebuilding the DB if it exists")
    parser.add_argument('--validate', action='store_true', help="Run evaluation after building")
    parser.add_argument('--use-llm', action=argparse.BooleanOptionalAction, default=True, help="Use Gemini LLM fallback instead of deterministic only")
    parser.add_argument('--model-name', default='gemini-3.5-flash', help="Gemini Model to use for fallback")
    parser.add_argument('--api-key', type=str, help="Gemini API Key (overrides env var)")
    args = parser.parse_args()

    load_env()

    if args.api_key:
        os.environ['GEMINI_API_KEY'] = args.api_key
    
    if args.validate:
        if not os.path.exists(DB_PATH):
            run_pipeline()
        validate(args.use_llm, args.model_name)
        return
    
    if not args.skip_build:
        run_pipeline()
    elif not os.path.exists(DB_PATH):
        print("ERROR: Knowledge graph not found. Run without --skip-build first.")
        sys.exit(1)
    
    if args.questions:
        answer_questions(args.questions, args.output, args.use_llm, args.model_name)
    else:
        # Default: validate against sample questions
        validate(args.use_llm, args.model_name)


if __name__ == '__main__':
    main()
