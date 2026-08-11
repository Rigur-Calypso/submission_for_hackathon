#!/usr/bin/env python3
"""Analyze first name references and their correctness."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

# Get all engineer names and their projects
all_engs = [e[0] for e in db.execute("SELECT name FROM engineers ORDER BY name").fetchall()]
eng_projects = {}
for eng in all_engs:
    projects = db.execute("""
        SELECT p.project_name, p.pkg_number, p.client_name 
        FROM projects p JOIN engineer_projects ep ON p.project_id = ep.project_id
        JOIN engineers e ON ep.engineer_id = e.engineer_id
        WHERE e.name = ?
    """, (eng,)).fetchall()
    eng_projects[eng] = projects

# Current first_names dict
first_names_in_code = {
    'priya': 'Priya Patel', 'tanvir': 'Tanvir Menon', 'sunita': 'Sunita Deshmukh', 
    'neha': 'Neha Chopra', 'chandan': 'Chandan Banerjee', 'amit': 'Amit Iyer', 
    'farhan': 'Farhan Rao', 'naveen': 'Naveen Roy', 'lakshmi': 'Lakshmi Ghosh', 
    'priti': 'Priti Sharma', 'suresh': 'Suresh Das', 'meera': 'Meera Roy'
}

print("=== FIRST NAME AMBIGUITY CHECK ===")
# For ambiguous first names, check if the question has enough context to disambiguate
ambiguous = {
    'amit': ['Amit Iyer', 'Amit Mukherjee'],
    'farhan': ['Farhan Khan', 'Farhan Rao', 'Farhan Roy'],
    'meera': ['Meera Banerjee', 'Meera Chatterjee', 'Meera Roy'],
    'priya': ['Priya Gupta', 'Priya Patel'],
    'priti': ['Priti Pillai', 'Priti Sharma'],  # Priti Sharma doesn't exist!
    'suresh': ['Suresh Chopra', 'Suresh Das', 'Suresh Desai'],
    'tanvir': ['Tanvir Malhotra', 'Tanvir Menon'],
    'rahul': ['Rahul Das', 'Rahul Menon'],
    'pooja': ['Pooja Bose', 'Pooja Sen'],
    'manoj': ['Manoj Kapoor', 'Manoj Verma'],
    'asha': ['Asha Bose', 'Asha Nair'],
}

# Check if 'Priti Sharma' actually exists
priti_check = db.execute("SELECT * FROM engineers WHERE name LIKE '%Priti%'").fetchall()
print(f"  Engineers with 'Priti': {priti_check}")

# For questions that use only a first name, check which full name matches 
# based on the project context
print("\n=== QUESTIONS USING FIRST-NAME-ONLY REFERENCE ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    eng = intent.get('engineer')
    proj = intent.get('project')
    quest_lower = q['question'].lower()
    
    # Check if engineer was resolved via first_names dict 
    for fn, candidates in ambiguous.items():
        if fn in quest_lower and eng:
            # Was it resolved correctly?
            if eng in candidates:
                # Verify engineer works on the mentioned project
                if proj:
                    m = re.search(r'Pkg-(\d+)', proj, re.IGNORECASE)
                    if m:
                        pkg = int(m.group(1))
                        actual = db.execute("""
                            SELECT e.name FROM engineers e
                            JOIN engineer_projects ep ON e.engineer_id = ep.engineer_id
                            JOIN projects p ON ep.project_id = p.project_id
                            WHERE p.pkg_number = ?
                        """, (pkg,)).fetchall()
                        actual_names = [a[0] for a in actual]
                        if eng not in actual_names:
                            # Check which candidate IS on this project
                            correct_eng = [c for c in candidates if c in actual_names]
                            print(f"  WRONG MATCH {q['qid']}: eng='{eng}' but Pkg-{pkg} has {actual_names}")
                            if correct_eng:
                                print(f"    Should be: {correct_eng[0]}")
                            print(f"    Q: {q['question'][:150]}")

# Check if HV-IC-0244's "pritis" can be matched to a specific Priti
print("\n=== HV-IC-0244 ANALYSIS ===")
q244 = [q for q in questions if q['qid'] == 'HV-IC-0244'][0]
print(f"  Q: {q244['question']}")
# Check which Priti works on Hospital Block — West Bengal Pkg-18
pkg18_engs = db.execute("""
    SELECT e.name FROM engineers e
    JOIN engineer_projects ep ON e.engineer_id = ep.engineer_id
    JOIN projects p ON ep.project_id = p.project_id
    WHERE p.pkg_number = 18
""", ).fetchall()
print(f"  Engineers on Pkg-18: {[e[0] for e in pkg18_engs]}")

# Check all Priti engineers
for priti in ['Priti Pillai', 'Priti Sharma']:
    check = db.execute("SELECT * FROM engineers WHERE name = ?", (priti,)).fetchone()
    if check:
        projs = db.execute("""
            SELECT p.project_name, p.pkg_number FROM projects p
            JOIN engineer_projects ep ON p.project_id = ep.project_id
            WHERE ep.engineer_id = ?
        """, (check[0],)).fetchall()
        print(f"  {priti}: id={check[0]}, projects={projs}")
    else:
        print(f"  {priti}: NOT IN DATABASE")

# Verify the current answer for HV-IC-0244
# The question says "pritis pmp hit mar 10 2021 for the west bengal hospital block, how many days to wrap up?"
# cert_date=2021-03-10, project=Hospital Block — West Bengal Pkg-18
# completion_date for Pkg-18:
comp = db.execute("SELECT completion_date FROM projects WHERE pkg_number = 18").fetchone()
print(f"  Pkg-18 completion_date: {comp[0] if comp else 'NOT FOUND'}")
# Currently engineer=None, so date_span handler needs cert from... the question provides it directly (2021-03-10)
# But without an engineer, the handler still works if it has cert_date + project
# Let's trace through the handler...

db.close()
