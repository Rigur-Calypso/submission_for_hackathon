#!/usr/bin/env python3
"""Continue deep audit - find specific bugs."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

# ============================================================
# 1. HV-IC-0244: "pritis pmp" — engineer is None!
#    The first_names dict has 'priti' but "pritis" won't match \bpriti\b
# ============================================================
print("=== BUG 1: HV-IC-0244 — 'pritis' not matching 'priti' ===")
q244 = [q for q in questions if q['qid'] == 'HV-IC-0244'][0]
print(f"  Q: {q244['question']}")
# Check if "pritis" matches the pattern
import re
result = re.search(r'\bpriti\b', q244['question'], re.IGNORECASE)
result2 = re.search(r"\bpriti's\b", q244['question'], re.IGNORECASE)
print(f"  \\bpriti\\b match: {result}")
print(f"  \\bpriti's\\b match: {result2}")
# It says "pritis" not "priti's" — the apostrophe is missing!
result3 = re.search(r'\bpritis\b', q244['question'], re.IGNORECASE)
print(f"  \\bpritis\\b match: {result3}")

# Check all engineers in DB
all_engs = db.execute("SELECT name FROM engineers ORDER BY name").fetchall()
print(f"\n  All engineers: {[e[0] for e in all_engs]}")

# ============================================================
# 2. HV-IC-0348: temporal_chain with cert_date=None
# ============================================================
print("\n=== BUG 2: HV-IC-0348 — temporal_chain with cert_date=None ===")
q348 = [q for q in questions if q['qid'] == 'HV-IC-0348'][0]
print(f"  Q: {q348['question']}")
intent = query_engine.classify_question(q348['question'], db)
print(f"  Intent: engineer={intent.get('engineer')}, cert_date={intent.get('cert_issue_date')}, cert_type={intent.get('cert_type')}")
# The handler should fallback to cert_type + engineer to find the date
res = query_engine.answer_question_with_intent(q348['question'], intent, db)
print(f"  Answer: {res.value} Status: {res.status}")

# ============================================================
# 3. Check ALL date_span questions for correct engineer resolution
# ============================================================
print("\n=== DATE_SPAN: Full engineer+date check ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'date_span':
        eng = intent.get('engineer')
        cert_date = intent.get('cert_issue_date')
        proj = intent.get('project')
        if not eng:
            print(f"  NO ENG {q['qid']}: Q={q['question'][:150]}")
        if not cert_date:
            print(f"  NO DATE {q['qid']}: eng={eng} Q={q['question'][:100]}")
        if not proj:
            print(f"  NO PROJ {q['qid']}: eng={eng} Q={q['question'][:100]}")

# ============================================================
# 4. Check ALL questions for engineer=None where question mentions a name
# ============================================================
print("\n=== MISSING ENGINEER EXTRACTION ===")
# Get all engineer names
all_eng_names = [e[0] for e in db.execute("SELECT name FROM engineers").fetchall()]
# Also get first names
first_names_map = {}
for e in all_eng_names:
    parts = e.split()
    if len(parts) >= 2:
        first_names_map[parts[0].lower()] = e

for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if not intent.get('engineer'):
        quest_lower = q['question'].lower()
        # Check if any engineer name appears in the question
        for eng in all_eng_names:
            if eng.lower() in quest_lower:
                print(f"  MISSED FULL NAME {q['qid']}: '{eng}' in question but engineer=None")
                print(f"    Q: {q['question'][:150]}")
                break
        else:
            # Check first names
            for fn, full in first_names_map.items():
                # Check for possessive forms without apostrophe (e.g., "pritis" instead of "priti's")
                if re.search(rf'\b{fn}s?\b', quest_lower):
                    print(f"  MISSED FIRST NAME {q['qid']}: '{fn}' (={full}) in question but engineer=None")
                    print(f"    Shape={intent['shape']} Q: {q['question'][:120]}")
                    break

# ============================================================
# 5. Check engineer first_names dict completeness
# ============================================================
print("\n=== FIRST_NAMES DICT COMPLETENESS ===")
first_names_in_code = {'priya': 'Priya Patel', 'tanvir': 'Tanvir Menon', 'sunita': 'Sunita Deshmukh', 'neha': 'Neha Chopra', 'chandan': 'Chandan Banerjee', 'amit': 'Amit Iyer', 'farhan': 'Farhan Rao', 'naveen': 'Naveen Roy', 'lakshmi': 'Lakshmi Ghosh', 'priti': 'Priti Sharma', 'suresh': 'Suresh Das', 'meera': 'Meera Roy'}
for eng in all_eng_names:
    fn = eng.split()[0].lower()
    if fn not in first_names_in_code:
        print(f"  MISSING from first_names dict: {eng} (first name: {fn})")

# Check for ambiguous first names
from collections import Counter
fn_counts = Counter(e.split()[0].lower() for e in all_eng_names)
for fn, count in fn_counts.items():
    if count > 1:
        matches = [e for e in all_eng_names if e.split()[0].lower() == fn]
        print(f"  AMBIGUOUS first name '{fn}' ({count}x): {matches}")

db.close()
