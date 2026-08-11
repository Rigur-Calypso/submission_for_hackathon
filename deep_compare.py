#!/usr/bin/env python3
"""Deep compare: look at every question, show current answer, identify potential issues."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

# Check temporal_chain: HV-IC-0305 has cert_date "10 Mar 2021" instead of ISO date
print("=== TEMPORAL_CHAIN: cert_date format check ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'temporal_chain':
        cert_date = intent.get('cert_issue_date')
        print(f"  {q['qid']}: cert_date='{cert_date}' (raw from question)")

# Check HV-IC-0305 specifically
print("\n=== HV-IC-0305 deep check ===")
for q in questions:
    if q['qid'] == 'HV-IC-0305':
        print(f"  Q: {q['question']}")
        intent = query_engine.classify_question(q['question'], db)
        print(f"  Intent: {intent}")
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        print(f"  Answer: {res.value} Status: {res.status}")

# Check HV-IC-0373 — was changed from 1833300000 to 58
print("\n=== HV-IC-0373 deep check ===")
for q in questions:
    if q['qid'] == 'HV-IC-0373':
        print(f"  Q: {q['question']}")
        intent = query_engine.classify_question(q['question'], db)
        print(f"  Intent: {intent}")
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        print(f"  Answer: {res.value} Status: {res.status}")

# Check HV-IC-0260 — went from 0 to 8563200000
print("\n=== HV-IC-0260 deep check ===")
for q in questions:
    if q['qid'] == 'HV-IC-0260':
        print(f"  Q: {q['question']}")
        intent = query_engine.classify_question(q['question'], db)
        print(f"  Intent: {intent}")
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        print(f"  Answer: {res.value} Status: {res.status}")

# Check HV-IC-0371 — went from 0 to 629771836
print("\n=== HV-IC-0371 deep check ===")
for q in questions:
    if q['qid'] == 'HV-IC-0371':
        print(f"  Q: {q['question']}")
        intent = query_engine.classify_question(q['question'], db)
        print(f"  Intent: {intent}")
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        print(f"  Answer: {res.value} Status: {res.status}")

# Check HV-IC-0244 — went from 0 to 2910
print("\n=== HV-IC-0244 deep check ===")  
for q in questions:
    if q['qid'] == 'HV-IC-0244':
        print(f"  Q: {q['question']}")
        intent = query_engine.classify_question(q['question'], db)
        print(f"  Intent: {intent}")
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        print(f"  Answer: {res.value} Status: {res.status}")

db.close()
