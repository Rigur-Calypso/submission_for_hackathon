#!/usr/bin/env python3
"""Deep audit: re-run all 333 questions, show intent details for every answer."""
import json, sqlite3, sys, os, re, csv

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)

questions = data['questions']

# Group by shape
shape_counts = {}
shape_questions = {}

for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    res = query_engine.answer_question_with_intent(q['question'], intent, db)
    val = res.value
    shape = intent.get('shape', 'unknown')
    
    if shape not in shape_counts:
        shape_counts[shape] = 0
        shape_questions[shape] = []
    shape_counts[shape] += 1
    shape_questions[shape].append({
        'qid': q['qid'],
        'question': q['question'][:200],
        'answer_type': q.get('answer_type', ''),
        'shape': shape,
        'status': res.status.value,
        'client': intent.get('client') or '',
        'engineer': intent.get('engineer') or '',
        'project': intent.get('project') or '',
        'threshold': intent.get('threshold') or '',
        'grading': intent.get('grading') or '',
        'exclude_category': intent.get('exclude_category') or '',
        'role_filter': intent.get('role_filter') or '',
        'cert_type': intent.get('cert_type') or '',
        'cert_issue_date': intent.get('cert_issue_date') or '',
        'years': str(intent.get('years') or ''),
        'answer': val,
    })

print("=== SHAPE DISTRIBUTION ===")
for shape, count in sorted(shape_counts.items(), key=lambda x: -x[1]):
    print(f"  {shape:30s}: {count:3d}")

print(f"\n  TOTAL: {sum(shape_counts.values())}")

# Check for suspicious patterns
print("\n=== ZERO ANSWERS ===")
for shape, qs in shape_questions.items():
    for q in qs:
        if q['answer'] == 0:
            print(f"  {q['qid']:12s} shape={shape:25s} status={q['status']:12s} client={q['client'][:30]:30s} eng={q['engineer'][:20]:20s}")

print("\n=== UNSUPPORTED/NO_MATCH STATUS ===")
for shape, qs in shape_questions.items():
    for q in qs:
        if q['status'] in ('unsupported', 'no_match'):
            print(f"  {q['qid']:12s} shape={shape:25s} status={q['status']:12s} client={q['client'][:30]:30s} eng={q['engineer'][:20]:20s}")

# Write full audit
with open('deep_audit.csv', 'w', newline='') as f:
    fields = ['qid', 'answer_type', 'shape', 'status', 'client', 'engineer', 'project', 
              'threshold', 'grading', 'exclude_category', 'role_filter', 'cert_type', 
              'cert_issue_date', 'years', 'answer', 'question']
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for shape, qs in sorted(shape_questions.items()):
        for q in qs:
            writer.writerow(q)

print("\n✅ Full audit written to deep_audit.csv")

# Now look at each shape more carefully
print("\n=== POTENTIAL MISCLASSIFICATIONS ===")
for shape, qs in shape_questions.items():
    for q in qs:
        quest = q['question'].lower()
        # Questions asking about money but classified as count
        if q['answer_type'] == 'money' and shape in ('distinct_count', 'absence', 'grading_absence'):
            print(f"  TYPE MISMATCH: {q['qid']} answer_type=money but shape={shape}")
        if q['answer_type'] == 'percent' and shape not in ('collection_pct', 'referenced_share', 'grading_absence', 'top_client_pct'):
            print(f"  TYPE MISMATCH: {q['qid']} answer_type=percent but shape={shape}")
        if q['answer_type'] == 'days' and shape != 'date_span':
            print(f"  TYPE MISMATCH: {q['qid']} answer_type=days but shape={shape}")
        if q['answer_type'] == 'count' and shape not in ('distinct_count', 'absence', 'grading_absence', 'shared_projects', 'client_distinct_units'):
            print(f"  TYPE MISMATCH: {q['qid']} answer_type=count but shape={shape}")

db.close()
