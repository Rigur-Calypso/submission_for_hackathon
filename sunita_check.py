#!/usr/bin/env python3
"""Check if Sunita Deshmukh causes actual bugs."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

# Check if any question references 'sunita' first-name-only (not full "Sunita Joshi")
print("=== QUESTIONS MENTIONING SUNITA ===")
for q in questions:
    quest_lower = q['question'].lower()
    if 'sunita' in quest_lower:
        intent = query_engine.classify_question(q['question'], db)
        eng = intent.get('engineer')
        # Check if full name is in the question
        has_full = 'sunita joshi' in quest_lower
        if not has_full:
            print(f"  FIRST-NAME ONLY {q['qid']}: eng='{eng}' Q: {q['question'][:150]}")
        else:
            print(f"  FULL NAME {q['qid']}: eng='{eng}'")

# Check HV-IC-0244 more carefully: 
# "pritis pmp hit mar 10 2021 for the west bengal hospital block"
# Priti Pillai has "Hospital Block — West Bengal Pkg-60"
# But Pkg-18 is "Hospital Block — West Bengal Pkg-18" (Deepa Chatterjee)
# The fuzzy match of "west bengal hospital block" will match both Pkg-18 and Pkg-60
print("\n=== PKG-18 vs PKG-60 ===")
for pkg in [18, 60]:
    p = db.execute("SELECT project_name, client_name, completion_date FROM projects WHERE pkg_number = ?", (pkg,)).fetchone()
    engs = db.execute("""
        SELECT e.name FROM engineers e
        JOIN engineer_projects ep ON e.engineer_id = ep.engineer_id
        JOIN projects p ON ep.project_id = p.project_id
        WHERE p.pkg_number = ?
    """, (pkg,)).fetchall()
    print(f"  Pkg-{pkg}: {p[0]}, client={p[1]}, comp={p[2]}, engineers={[e[0] for e in engs]}")

# The correct Pkg for Priti Pillai is Pkg-60
# Current: project='Hospital Block — West Bengal Pkg-18' (wrong! should be Pkg-60)
# This needs fixing in the project resolution

# Check the date_span handler for HV-IC-0318 (Meera issue)
print("\n=== HV-IC-0318 DATE_SPAN ===")
q318 = [q for q in questions if q['qid'] == 'HV-IC-0318'][0]
print(f"  Q: {q318['question']}")
intent = query_engine.classify_question(q318['question'], db)
print(f"  Intent: eng={intent.get('engineer')}, proj={intent.get('project')}")
# Pkg-9 completion date
p = db.execute("SELECT completion_date FROM projects WHERE pkg_number = 9").fetchone()
print(f"  Pkg-9 completion_date: {p[0]}")
# With Meera Roy's cert date
cert_meera_roy = db.execute("""
    SELECT c.issue_date FROM certifications c
    JOIN engineers e ON c.engineer_id = e.engineer_id
    WHERE e.name = 'Meera Roy'
""").fetchall()
cert_meera_ch = db.execute("""
    SELECT c.issue_date FROM certifications c
    JOIN engineers e ON c.engineer_id = e.engineer_id
    WHERE e.name = 'Meera Chatterjee'
""").fetchall()
print(f"  Meera Roy certs: {cert_meera_roy}")
print(f"  Meera Chatterjee certs: {cert_meera_ch}")

# Calculate correct answer with Meera Chatterjee
from dateutil import parser as dateparser
cert_date = dateparser.parse('2021-03-10')
comp_date = dateparser.parse(p[0])
days = abs((comp_date - cert_date).days)
print(f"  Days from 2021-03-10 to {p[0]}: {days}")

# Current answer
res = query_engine.answer_question_with_intent(q318['question'], intent, db)
print(f"  Current answer: {res.value}")

# Check what the CORRECT answer should be
# The question says "Meera's March 10, 2021 PMP on the Tamil Nadu Pkg-9"
# Meera Chatterjee is on Pkg-9, cert date should be looked up
cert_ch_date = db.execute("""
    SELECT c.issue_date, c.cert_type FROM certifications c
    JOIN engineers e ON c.engineer_id = e.engineer_id
    WHERE e.name = 'Meera Chatterjee'
""").fetchall()
print(f"  Meera Chatterjee all certs: {cert_ch_date}")

db.close()
