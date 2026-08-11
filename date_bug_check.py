#!/usr/bin/env python3
"""Check date parsing for all date_span questions."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

print("=== DATE_SPAN: all questions with their date parsing ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'date_span':
        cert_date = intent.get('cert_issue_date')
        eng = intent.get('engineer')
        proj = intent.get('project')
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        
        # If no explicit date, check how the handler resolves it
        resolved_date = cert_date
        if not cert_date and eng and intent.get('cert_type'):
            c = db.execute("""
                SELECT c.issue_date FROM certifications c
                JOIN engineers e ON c.engineer_id = e.engineer_id
                WHERE e.name = ? AND c.cert_type = ?
            """, (eng, intent['cert_type'])).fetchone()
            if c:
                resolved_date = f"(from DB) {c[0]}"
        
        # Get project completion date
        comp_date = None
        if proj:
            m = re.search(r'Pkg-(\d+)', proj, re.IGNORECASE)
            if m:
                pkg = int(m.group(1))
                c = db.execute("SELECT completion_date FROM projects WHERE pkg_number = ?", (pkg,)).fetchone()
                if c: comp_date = c[0]
        
        status = "✅" if res.status.value == 'resolved' else "❌"
        print(f"  {status} {q['qid']}: eng={eng}, date={resolved_date or 'NONE'}, proj={proj}, comp={comp_date}, ans={res.value}")
        if not cert_date and not resolved_date:
            print(f"    Q: {q['question'][:200]}")

print("\n=== QUESTIONS WITH 'March 10th' FORMAT (tricky date parsing) ===")
for q in questions:
    if 'march 10th' in q['question'].lower() or 'mar 10' in q['question'].lower():
        intent = query_engine.classify_question(q['question'], db)
        cert_date = intent.get('cert_issue_date')
        print(f"  {q['qid']}: cert_date={cert_date} shape={intent['shape']} Q: {q['question'][:150]}")

# Check for all date formats in questions
print("\n=== ALL DATE FORMATS IN QUESTIONS ===")
date_patterns = set()
for q in questions:
    # ISO dates
    for m in re.finditer(r'\d{4}-\d{2}-\d{2}', q['question']):
        date_patterns.add(('ISO', m.group()))
    # Verbose dates
    for m in re.finditer(r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4}', q['question'], re.IGNORECASE):
        date_patterns.add(('Verbose', m.group()))
    for m in re.finditer(r'\d{1,2}(?:st|nd|rd|th)\s+(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec),?\s+\d{4}', q['question'], re.IGNORECASE):
        date_patterns.add(('DayFirst', m.group()))

for fmt, d in sorted(date_patterns):
    print(f"  {fmt}: '{d}'")

db.close()
