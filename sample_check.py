#!/usr/bin/env python3
"""Check how our engine performs on the sample questions with known gold answers."""
import json, sqlite3, sys, os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine
from evaluate_utils import score_one

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('sample_questions.json') as f:
    sample = json.load(f)

questions = sample.get('questions', sample)

total_score = 0
total = len(questions)
perfect = 0
partial = 0
wrong = 0

print("=== SAMPLE QUESTION SCORING ===\n")

shape_scores = {}

for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    res = query_engine.answer_question_with_intent(q['question'], intent, db)
    answer = res.value
    gold = q['answer']
    s = score_one(gold, answer)
    total_score += s
    shape = intent.get('shape', 'unknown')
    
    if shape not in shape_scores:
        shape_scores[shape] = {'total': 0, 'count': 0, 'perfect': 0}
    shape_scores[shape]['total'] += s
    shape_scores[shape]['count'] += 1
    if s == 1.0:
        shape_scores[shape]['perfect'] += 1
    
    if s == 1.0:
        perfect += 1
    elif s > 0:
        partial += 1
        status = "🟡"
        print(f"  {status} {q['qid']:12s} shape={shape:25s} gold={gold!s:>15} got={answer!s:>15} score={s:.4f}")
        print(f"       Q: {q['question'][:150]}")
        print(f"       Client: {intent.get('client')}, Engineer: {intent.get('engineer')}, Project: {intent.get('project')}")
    else:
        wrong += 1
        status = "❌"
        print(f"  {status} {q['qid']:12s} shape={shape:25s} gold={gold!s:>15} got={answer!s:>15} score={s:.4f}")
        print(f"       Q: {q['question'][:150]}")
        print(f"       Client: {intent.get('client')}, Engineer: {intent.get('engineer')}, Project: {intent.get('project')}")

print(f"\n{'='*80}")
print(f"PERFECT: {perfect}/{total}, PARTIAL: {partial}, WRONG: {wrong}")
print(f"SCORE: {total_score:.4f} / {total} = {total_score/total:.4%}")

print(f"\n{'shape':30s} {'score':>8s} {'n':>3s} {'perfect':>7s} {'avg':>8s}")
for shape, info in sorted(shape_scores.items(), key=lambda x: -x[1]['total']):
    avg = info['total'] / info['count'] if info['count'] else 0
    print(f"{shape:30s} {info['total']:8.2f} {info['count']:3d} {info['perfect']:3d}/{info['count']:<3d} {avg:8.4f}")

db.close()
