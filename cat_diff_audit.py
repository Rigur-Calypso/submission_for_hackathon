#!/usr/bin/env python3
"""Detailed audit of all category_difference questions."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)

questions = data['questions']

# Show all distinct categories in DB
categories = db.execute("SELECT DISTINCT category FROM projects WHERE category IS NOT NULL ORDER BY category").fetchall()
print("=== ALL CATEGORIES IN DB ===")
for c in categories:
    total = db.execute("SELECT SUM(contract_value) FROM projects WHERE category = ?", (c[0],)).fetchone()[0] or 0
    cnt = db.execute("SELECT COUNT(*) FROM projects WHERE category = ?", (c[0],)).fetchone()[0]
    print(f"  {c[0]:30s}: {cnt:3d} projects, total={total:>15,}")

print("\n=== CATEGORY_DIFFERENCE QUESTIONS (56 total) ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'category_difference':
        client = intent.get('client')
        quest = q['question'].lower()
        
        # Find matched categories
        found_cats = [
            cat for cat, pattern in query_engine._CATEGORY_PATTERNS.items()
            if cat in {r[0] for r in categories} and re.search(pattern, quest, re.IGNORECASE)
        ]
        
        cat1, cat2 = found_cats[:2] if len(found_cats) >= 2 else (found_cats[0] if found_cats else 'NONE', 'NONE')
        
        if client and len(found_cats) >= 2:
            v1 = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND category = ?", (client, cat1)).fetchone()[0] or 0
            v2 = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND category = ?", (client, cat2)).fetchone()[0] or 0
            diff = abs(v1 - v2)
            
            # Check if client has both categories
            client_cats = [r[0] for r in db.execute("SELECT DISTINCT category FROM projects WHERE client_name = ?", (client,)).fetchall()]
            has_both = cat1 in client_cats and cat2 in client_cats
            
            status = "✅" if has_both else "⚠️ MISSING CAT"
            print(f"  {status} {q['qid']}: client='{client}' {cat1}={v1:>12,} vs {cat2}={v2:>12,} diff={diff:>12,}")
            if not has_both:
                print(f"    Client categories: {client_cats}")
                print(f"    Q: {q['question'][:200]}")
        else:
            print(f"  ❌ {q['qid']}: client='{client}' cats={found_cats}")
            print(f"    Q: {q['question'][:200]}")

db.close()
