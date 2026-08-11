#!/usr/bin/env python3
"""Check impact of fixing all identified bugs."""
import json, sqlite3, sys, os, re
from dateutil import parser as dateparser

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

# ============================================================
# BUG: HV-IC-0244 — Wrong Pkg match
# "pritis pmp hit mar 10 2021 for the west bengal hospital block"
# Currently: Pkg-18 (Deepa Chatterjee), completion=2013-03-22, days=2910
# Should be: Pkg-60 (Priti Pillai), completion=2024-09-07
# ============================================================
print("=== BUG: HV-IC-0244 ===")
cert_date = dateparser.parse('2021-03-10')
# Current (wrong) answer
comp18 = dateparser.parse('2013-03-22')
days18 = abs((comp18 - cert_date).days)
# Correct answer  
comp60 = dateparser.parse('2024-09-07')
days60 = abs((comp60 - cert_date).days)
print(f"  Current (Pkg-18, Deepa): {days18} days")
print(f"  Correct (Pkg-60, Priti): {days60} days")

# ============================================================
# Check gap_awarded_invoiced — signed vs unsigned
# ============================================================
print("\n=== GAP_AWARDED_INVOICED: signed values ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'gap_awarded_invoiced':
        client = intent.get('client')
        if client:
            awarded = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ?", (client,)).fetchone()[0] or 0
            invoiced = db.execute("SELECT SUM(invoiced) FROM receivables WHERE client = ?", (client,)).fetchone()[0] or 0
            diff_signed = awarded - invoiced
            diff_abs = abs(diff_signed)
            sign = "+" if diff_signed >= 0 else "-"
            print(f"  {q['qid']}: client='{client}' awarded={awarded:>12,} invoiced={invoiced:>12,.0f} diff={diff_signed:>12,.0f} ({sign})")

# ============================================================
# Check for questions where "award" / "awarded" is mentioned but
# we're looking at contract_value vs invoiced
# ============================================================
print("\n=== QUESTION WORDING FOR GAP ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'gap_awarded_invoiced':
        quest = q['question']
        has_gap = 'gap' in quest.lower()
        has_shortfall = 'shortfall' in quest.lower()
        has_above = 'above' in quest.lower() or 'over' in quest.lower() or 'sitting above' in quest.lower()
        print(f"  {q['qid']}: gap={has_gap} shortfall={has_shortfall} above={has_above}")
        if has_above or has_shortfall:
            print(f"    Q: {quest[:200]}")

# ============================================================
# Check avg_work_size — is it always for the CLIENT's full portfolio?
# Or should it be filtered by the engineer or project?
# ============================================================
print("\n=== AVG_WORK_SIZE: Check if question asks for engineer-specific avg ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'avg_work_size':
        eng = intent.get('engineer')
        client = query_engine._resolve_client_from_intent(db, intent)
        quest = q['question'].lower()
        
        # Does the question ask for the average of the CLIENT's works or the ENGINEER's works?
        if eng and client:
            # Count client projects vs engineer projects under this client
            client_count = db.execute("SELECT COUNT(*) FROM projects WHERE client_name = ?", (client,)).fetchone()[0]
            eng_count = db.execute("""
                SELECT COUNT(*) FROM projects p
                JOIN engineer_projects ep ON p.project_id = ep.project_id
                JOIN engineers e ON ep.engineer_id = e.engineer_id
                WHERE e.name = ? AND p.client_name = ?
            """, (eng, client)).fetchone()[0]
            if client_count != eng_count:
                print(f"  {q['qid']}: eng='{eng}' client='{client}' client_projects={client_count} eng_projects={eng_count}")
                print(f"    Q: {quest[:200]}")

# ============================================================
# Check for rounding issues
# ============================================================
print("\n=== ROUNDING CHECKS ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] in ('collection_pct', 'referenced_share', 'top_client_pct', 'grading_absence'):
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        val = res.value
        # Check if rounding to 2 decimal places might lose precision
        if isinstance(val, float) and val != round(val, 2):
            print(f"  {q['qid']}: shape={intent['shape']} val={val} rounded={round(val, 2)}")

# ============================================================
# Check if "March 10th" without year in the question is handled
# ============================================================
print("\n=== DATE PARSING: 'March 10th' without year ===")
test_dates = [
    "March 10th, 2021",
    "March 10th 2021",
    "march 10th",
    "Mar 10 2021",
    "10 March 2021",
    "10th March, 2021",
]
for d in test_dates:
    result = query_engine.extract_date_from_question(f"some text about {d} and more")
    print(f"  '{d}' → {result}")

db.close()
