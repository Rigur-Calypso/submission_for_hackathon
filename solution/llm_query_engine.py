#!/usr/bin/env python3
"""
llm_query_engine.py — LLM-powered Text-to-SQL engine for the BITS Hackathon.

Replaces the regex-based classifier with a Gemini-powered engine that can
dynamically generate SQL for all 21 reasoning patterns.
"""
import os
import sys
import sqlite3
import re
import google.generativeai as genai
import itertools

# Allow multiple comma-separated keys
API_KEY_STRING = os.environ.get("GEMINI_API_KEY")
API_KEYS = [k.strip() for k in API_KEY_STRING.split(",")] if API_KEY_STRING else []
API_KEY_CYCLE = itertools.cycle(API_KEYS) if API_KEYS else None

CURRENT_API_KEY = next(API_KEY_CYCLE) if API_KEY_CYCLE else None

def switch_api_key():
    global CURRENT_API_KEY
    if API_KEYS and len(API_KEYS) > 1:
        CURRENT_API_KEY = next(API_KEY_CYCLE)
        genai.configure(api_key=CURRENT_API_KEY)
        print(f"  [LLM Engine] Switched to next API key.")
    else:
        print("  [LLM Engine] Only 1 API key provided. Cannot switch.")

SOLUTION_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SOLUTION_DIR)
import query_engine

DB_PATH = os.path.join(SOLUTION_DIR, 'knowledge_graph.db')

# To be set via CLI or env var before calling answer_question
API_KEY = os.environ.get('GEMINI_API_KEY', '')

# Schema context to provide to the LLM
SCHEMA_PROMPT = """
You are an expert SQLite SQL data analyst. You are given a question and the schema of a database.
Write a valid SQLite SQL query to answer the question.

Here is the schema for the knowledge graph database:

CREATE TABLE projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL,
    pkg_number INTEGER,               -- extracted from "Pkg-NNN"
    client_name TEXT,                  -- clean client name
    client_type TEXT,                  -- government, psu, private
    category TEXT,                     -- Bridges Flyovers, Buildings, etc.
    contract_value INTEGER,            -- in rupees
    completion_date TEXT,              -- ISO format YYYY-MM-DD
    grading TEXT,                      -- Excellent, Very Good, Good, Satisfactory
    role TEXT,                         -- Prime, Subcontractor, JV Partner
    project_lead TEXT,                 -- engineer who led
    cc_ref TEXT,                       -- Certificate ref: CC/34/2011/001
    has_reference_letter INTEGER DEFAULT 0,  -- boolean (1=true, 0=false)
    source_ccc TEXT,                   -- source CCC filename
    source_cc TEXT                     -- source CC filename
);

CREATE TABLE engineers (
    engineer_id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    employee_id TEXT                    -- EMP-001, EMP-004, etc.
);

CREATE TABLE certifications (
    cert_id TEXT PRIMARY KEY,           -- PMI-200006, 6S-500156
    engineer_id INTEGER,
    cert_type TEXT,                    -- PMP, Six Sigma Black Belt, Six Sigma Green Belt
    issuing_authority TEXT,            -- PMI, ASQ
    issue_date TEXT,                   -- ISO date (YYYY-MM-DD)
    valid_through TEXT,                -- ISO date (YYYY-MM-DD)
    source_file TEXT,
    FOREIGN KEY (engineer_id) REFERENCES engineers(engineer_id)
);

CREATE TABLE engineer_projects (
    engineer_id INTEGER,
    project_id INTEGER,
    role_in_project TEXT,              -- Project Lead, Project Manager
    PRIMARY KEY (engineer_id, project_id),
    FOREIGN KEY (engineer_id) REFERENCES engineers(engineer_id),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE TABLE reference_letters (
    ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file TEXT,
    project_name TEXT,
    project_id INTEGER,
    contract_value INTEGER,
    issuing_authority TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE TABLE boq_items (
    boq_id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_number INTEGER,
    item_no INTEGER,
    description TEXT,
    unit TEXT,
    quantity REAL,
    rate REAL,
    amount REAL
);

CREATE TABLE measurements (
    meas_id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_number INTEGER,
    ra_no INTEGER,
    measured_on TEXT,
    item_no INTEGER,
    description TEXT,
    qty_measured REAL,
    amount REAL
);

CREATE TABLE receivables (
    recv_id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no TEXT,
    client TEXT,
    invoice_date TEXT,
    invoiced REAL,
    status TEXT,
    received REAL,
    outstanding REAL
);

CREATE TABLE plant_register (
    asset_id INTEGER PRIMARY KEY,
    type TEXT,
    make TEXT,
    acquired INTEGER,
    cost REAL,
    condition TEXT,
    location TEXT,
    ownership TEXT,
    safety_certified INTEGER
);

CREATE TABLE trial_balance (
    tb_id INTEGER PRIMARY KEY AUTOINCREMENT,
    fiscal_year TEXT,
    account TEXT,
    debit REAL,
    credit REAL,
    balance REAL
);

-- Extra table for full text from documents (useful if structured tables lack the info)
CREATE TABLE documents_text (
    doc_id TEXT PRIMARY KEY,
    doc_type TEXT,
    filename TEXT,
    full_text TEXT
);

SAMPLE ROWS:

projects:
| project_id | project_name | pkg_number | client_name | client_type | category | contract_value | completion_date | grading | role | project_lead | project_lead_role | cc_ref | has_reference_letter | source_ccc | source_cc |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | RCC Bridge — Gujarat Pkg-1 | 1 | National Special Projects Office | government | Bridges Flyovers | 333800000 | 2011-02-06 | Good | JV Partner | Suresh Desai | | CC/34/2011/001 | 1 | DOC-CCC-001.pdf | DOC-CC-001.pdf |

certifications:
| cert_id | engineer_id | cert_type | issuing_authority | issue_date | valid_through | source_file |
|---|---|---|---|---|---|---|
| PMI-200006 | 22 | PMP | PMI | 2021-03-10 | 2027-08-31 | DOC-PCERT-006.pdf |

reference_letters:
| ref_id | source_file | project_name | project_id | contract_value | issuing_authority |
|---|---|---|---|---|---|
| 1 | DOC-REF-001.pdf | RCC Bridge — Gujarat Pkg-1 | 1 | 333800000 | National Special Projects Office |

RULES:
1. Always output ONLY the raw SQL query. Do not wrap in ```sql ... ``` block or add any conversational text.
2. The query must return exactly ONE row and ONE column (a single numerical value). 
3. The answer should be a number: total rupees, a count, a percentage out of 100, or number of days. 
4. If a threshold is specified in words (e.g., "twenty crore"), you must convert it to a number (e.g., 200000000). 1 Crore = 10,000,000. 1 Lakh = 100,000.
5. If calculating a percentage, do: CAST(SUM(...) AS FLOAT) * 100.0 / COUNT(...)
6. Use LIKE with wildcards '%' if you are not sure of exact names, but prefer exact matches if provided precisely.
7. Use julianday() for date differences if calculating days. Example: abs(julianday(date1) - julianday(date2)).
"""

def extract_sql(text: str) -> str:
    """Extract SQL from markdown block if present, else return stripped text."""
    text = text.strip()
    if text.startswith('```'):
        # Find the first ```sql or ``` and extract contents until next ```
        m = re.search(r'```(?:sql)?\s+(.*?)\s+```', text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return text.strip('`').strip()

def ask_gemini(prompt: str, model_name: str = 'gemini-3.5-flash') -> str:
    if not CURRENT_API_KEY:
        raise ValueError("No API Key configured.")
    genai.configure(api_key=CURRENT_API_KEY)
    model = genai.GenerativeModel(model_name)
    import time
    for attempt in range(5):
        try:
            response = model.generate_content(
                prompt, 
                generation_config=genai.types.GenerationConfig(temperature=0.0)
            )
            return extract_sql(response.text)
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower() or 'exhausted' in str(e).lower():
                print(f"  [LLM Engine] Rate limit/Quota hit on attempt {attempt+1}. Error: {e}")
                if len(API_KEYS) > 1:
                    switch_api_key()
                else:
                    print("  [LLM Engine] Sleeping 60s...")
                    time.sleep(60)
            else:
                raise
    raise ValueError("Failed after 5 attempts due to rate limit/quota.")

def answer_question(question: str, db: sqlite3.Connection, model_name: str = 'gemini-3.5-flash') -> tuple[float, dict]:
    """
    Answers a question by asking Gemini to write a SQL query.
    Returns (answer, intent_dict) to match the interface of query_engine.py.
    """
    if not API_KEYS:
        print("  [LLM Engine] No GEMINI_API_KEY found, falling back to regex engine.")
        return query_engine.answer_question(question, db)

    prompt = f"{SCHEMA_PROMPT}\n\nQuestion: {question}\n\nSQL Query:"
    
    sql = ""
    result = 0.0
    intent = {'shape': 'llm_generated'}
    
    try:
        def authorizer(action, arg1, arg2, dbname, trigger_name):
            if action in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION):
                return sqlite3.SQLITE_OK
            return sqlite3.SQLITE_DENY
        
        db.set_authorizer(authorizer)
        
        sql = ask_gemini(prompt, model_name)
        cursor = db.execute(sql)
        row = cursor.fetchone()
        if row is None:
            raise ValueError("Query returned no results.")
        if len(row) != 1:
            raise ValueError(f"Query returned {len(row)} columns, expected exactly 1.")
        if cursor.fetchone() is not None:
            raise ValueError("Query returned multiple rows, expected exactly 1.")
        if row[0] is not None:
            result = float(row[0])
    except Exception as e:
        # Retry once with the error message
        retry_prompt = f"{prompt}\n\nThe previous query failed with error: {e!s}\nPlease fix the SQL query and try again. Ensure it returns exactly one numeric cell. Output ONLY the raw SQL."
        try:
            sql = ask_gemini(retry_prompt, model_name)
            cursor = db.execute(sql)
            row = cursor.fetchone()
            if row is None:
                raise ValueError("Query returned no results.")
            if len(row) != 1:
                raise ValueError(f"Query returned {len(row)} columns, expected exactly 1.")
            if cursor.fetchone() is not None:
                raise ValueError("Query returned multiple rows, expected exactly 1.")
            if row[0] is not None:
                result = float(row[0])
        except Exception as e2:
            print(f"  [LLM Engine Error] {e2}, falling back to regex engine")
            res = query_engine.answer_question(question, db)
            return res.value, res.plan.__dict__ if res.plan else {}
    finally:
        db.set_authorizer(None)

    intent['sql'] = sql
    return result, intent

def llm_classify_question(question: str, model_name: str = 'gemini-3.5-flash') -> dict:
    """Classifies the question intent using the LLM and returns a dictionary."""
    if not API_KEYS:
        print("  [LLM Engine] No GEMINI_API_KEY found, cannot classify.")
        return {'shape': 'unknown', 'table_focus': 'projects', 'answer_type': 'count'}

    prompt = f"""
You are an expert intent classifier. Analyze the following question and extract the intent parameters as a JSON object.

Valid shapes are: absence, date_span, distinct_count, hop_aggregate, temporal_chain, avg_work_size, doc_filtered_aggregate, exclusion_aggregate, gap_to_threshold, grading_absence, rank_value, referenced_share, role_split, threshold_aggregate.
Valid table_focus are: projects, receivables, plant_register, boq_items, trial_balance.
Valid answer_type are: count, money, days, percent.

The output MUST be a JSON object with exactly these keys:
{{
    "shape": "one of the valid shapes or unknown",
    "table_focus": "one of the valid table_focus",
    "client": "client name from the question, or null",
    "engineer": "engineer name from the question, or null",
    "project": "project name or Pkg-NNN from the question, or null",
    "cert_type": "certification type (e.g., PMP) or null",
    "cert_id": "certification ID (e.g., PMI-123) or null",
    "threshold": numeric threshold value if applicable, or null,
    "threshold_op": ">=" or ">" or null,
    "grading": "grading value (Excellent, Very Good, Good, Satisfactory) or null",
    "exclude_category": "category to exclude, or null",
    "role_filter": "Prime, Subcontractor, JV Partner, or null",
    "cert_issue_date": "YYYY-MM-DD or null",
    "answer_type": "one of the valid answer_types"
}}

Output exactly the exact names as they appear in the question so they can be fuzzy matched later. For threshold, convert string words (like 'twenty crore') to raw numbers (200000000).

Question: {question}
JSON:
"""
    genai.configure(api_key=CURRENT_API_KEY)
    model = genai.GenerativeModel(model_name)
    import time
    for attempt in range(3):
        try:
            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.0,
                    response_mime_type="application/json"
                )
            )
            import json
            parsed = json.loads(response.text)
            return parsed
        except Exception as e:
            if '429' in str(e) or 'quota' in str(e).lower() or 'exhausted' in str(e).lower():
                print(f"  [LLM Engine] Rate limit/Quota hit on classification attempt {attempt+1}. Error: {e}")
                if len(API_KEYS) > 1:
                    switch_api_key()
                    genai.configure(api_key=CURRENT_API_KEY)
                    model = genai.GenerativeModel(model_name)
                else:
                    print("  [LLM Engine] Sleeping 60s...")
                    time.sleep(60)
            else:
                print(f"  [LLM Classification Error] {e}")
                return {'shape': 'unknown', 'table_focus': 'projects', 'answer_type': 'count'}
    return {'shape': 'unknown', 'table_focus': 'projects', 'answer_type': 'count'}

if __name__ == '__main__':
    # Test script if run directly
    if not API_KEYS:
        print("Set GEMINI_API_KEY to test.")
        sys.exit(1)
    db = sqlite3.connect(DB_PATH)
    q = "Cross-checking against the Public Health Engineering Dept, Gujarat, how many works have no client reference letter on file?"
    ans, intent = answer_question(q, db)
    print(f"Q: {q}")
    print(f"SQL: {intent.get('sql')}")
    print(f"A: {ans}")
    db.close()
