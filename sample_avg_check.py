#!/usr/bin/env python3
import json, sqlite3, sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine
from evaluate_utils import score_one

db = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db'))

with open('sample_questions.json') as f:
    sample = json.load(f)

for q in sample['questions']:
    if q.get('shape') == 'avg_work_size':
        intent = query_engine.classify_question(q['question'], db)
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        gold = q['answer']
        s = score_one(gold, res.value)
        client = query_engine._resolve_client_from_intent(db, intent)
        print(f"{q['qid']}: gold={gold} got={res.value} score={s:.4f} client={client}")
        
        # Show raw avg
        vals = db.execute("SELECT contract_value FROM projects WHERE client_name = ?", (client,)).fetchall()
        vals = [v[0] for v in vals if v[0]]
        raw_avg = sum(vals) / len(vals)
        print(f"  raw_avg={raw_avg} n={len(vals)} sum={sum(vals)}")

db.close()
