#!/usr/bin/env python3
"""Check EVERY question where engineer was resolved via first_names dict for correctness."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

all_engs = [e[0] for e in db.execute("SELECT name FROM engineers ORDER BY name").fetchall()]

# Current first_names dict
first_names_in_code = {
    'priya': 'Priya Patel', 'tanvir': 'Tanvir Menon', 'sunita': 'Sunita Deshmukh', 
    'neha': 'Neha Chopra', 'chandan': 'Chandan Banerjee', 'amit': 'Amit Iyer', 
    'farhan': 'Farhan Rao', 'naveen': 'Naveen Roy', 'lakshmi': 'Lakshmi Ghosh', 
    'priti': 'Priti Sharma', 'suresh': 'Suresh Das', 'meera': 'Meera Roy'
}

# Check for first name 'Sunita' — is 'Sunita Deshmukh' in DB?
print("=== VERIFY first_names DICT VALUES EXIST ===")
for fn, full in first_names_in_code.items():
    exists = db.execute("SELECT * FROM engineers WHERE name = ?", (full,)).fetchone()
    if not exists:
        # Find closest match
        matches = db.execute("SELECT name FROM engineers WHERE name LIKE ?", (fn.title() + '%',)).fetchall()
        print(f"  ❌ '{full}' NOT IN DB! Possible: {[m[0] for m in matches]}")
    else:
        print(f"  ✅ '{full}' exists")

# For every question: check if engineer was resolved by fuzzy match or first_names
# and verify against the project
print("\n=== ALL ENGINEER RESOLUTIONS ===")
errors = []
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    eng = intent.get('engineer')
    proj = intent.get('project')
    quest_lower = q['question'].lower()
    
    if eng and proj:
        # Check if this engineer is actually assigned to this project
        m = re.search(r'Pkg-(\d+)', proj, re.IGNORECASE)
        if m:
            pkg = int(m.group(1))
            assigned = db.execute("""
                SELECT e.name FROM engineers e
                JOIN engineer_projects ep ON e.engineer_id = ep.engineer_id
                JOIN projects p ON ep.project_id = p.project_id
                WHERE p.pkg_number = ?
            """, (pkg,)).fetchall()
            assigned_names = [a[0] for a in assigned]
            
            if eng not in assigned_names and assigned_names:
                # Check if it's a first-name issue
                eng_fn = eng.split()[0].lower()
                correct = [a for a in assigned_names if a.split()[0].lower() == eng_fn]
                
                errors.append({
                    'qid': q['qid'],
                    'shape': intent['shape'],
                    'resolved_eng': eng,
                    'pkg': pkg,
                    'assigned': assigned_names,
                    'correct': correct[0] if correct else 'UNKNOWN',
                    'question': q['question'][:150]
                })

print(f"\nTotal engineer-project mismatches: {len(errors)}")
for e in errors:
    print(f"  ❌ {e['qid']:12s} shape={e['shape']:25s} resolved='{e['resolved_eng']}' pkg={e['pkg']} assigned={e['assigned']}")
    if e['correct'] != 'UNKNOWN':
        print(f"    Should be: '{e['correct']}'")
    print(f"    Q: {e['question']}")

db.close()
