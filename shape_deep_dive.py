#!/usr/bin/env python3
"""Cross-check each shape handler against the DB to find subtle errors."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)

questions = data['questions']

# ============================================================
# 1. Check hop_aggregate: do we correctly resolve client via project hop?
# ============================================================
print("=== HOP_AGGREGATE: Check client resolution ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'hop_aggregate':
        client = query_engine._resolve_client_from_intent(db, intent)
        if not client:
            print(f"  PROBLEM {q['qid']}: No client resolved!")
            print(f"    Q: {q['question'][:150]}")
        elif intent.get('engineer'):
            # Check if this engineer actually works for this client
            c = db.execute("""
                SELECT DISTINCT p.client_name FROM projects p
                JOIN engineer_projects ep ON p.project_id = ep.project_id
                JOIN engineers e ON ep.engineer_id = e.engineer_id
                WHERE e.name = ?
            """, (intent['engineer'],)).fetchall()
            eng_clients = [r[0] for r in c]
            if client not in eng_clients:
                print(f"  MISMATCH {q['qid']}: Client '{client}' not in engineer {intent['engineer']}'s portfolio")
                print(f"    Engineer's actual clients: {eng_clients}")
                print(f"    Q: {q['question'][:150]}")

# ============================================================
# 2. Check avg_work_size: client resolution + avg calculation
# ============================================================
print("\n=== AVG_WORK_SIZE: Check values ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'avg_work_size':
        client = query_engine._resolve_client_from_intent(db, intent)
        if not client:
            print(f"  PROBLEM {q['qid']}: No client resolved!")
            print(f"    Q: {q['question'][:150]}")
        else:
            # Show count and average
            c = db.execute("SELECT COUNT(*), AVG(contract_value), SUM(contract_value) FROM projects WHERE client_name = ?", (client,)).fetchone()
            print(f"  {q['qid']}: client='{client}' count={c[0]} avg={c[1]:.0f} sum={c[2]}")

# ============================================================
# 3. Check collection_pct: verify client resolution via project hop
# ============================================================
print("\n=== COLLECTION_PCT: Check client+receivable matching ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'collection_pct':
        client = intent.get('client')
        if not client and intent.get('project'):
            m = re.search(r'Pkg-(\d+)', intent['project'], re.IGNORECASE)
            if m:
                pkg = int(m.group(1))
                c = db.execute("SELECT client_name FROM projects WHERE pkg_number = ?", (pkg,)).fetchone()
                if c: client = c[0]
        if not client:
            print(f"  PROBLEM {q['qid']}: No client resolved!")
            print(f"    Q: {q['question'][:150]}")
        else:
            recv = db.execute("SELECT SUM(received), SUM(invoiced) FROM receivables WHERE client = ?", (client,)).fetchone()
            if not recv or not recv[1]:
                print(f"  PROBLEM {q['qid']}: No receivables for client '{client}'")
            else:
                pct = round(recv[0] / recv[1] * 100, 2)
                print(f"  {q['qid']}: client='{client}' received={recv[0]:.0f} invoiced={recv[1]:.0f} pct={pct}%")

# ============================================================
# 4. Check category_difference: do we correctly match 2 categories?
# ============================================================
print("\n=== CATEGORY_DIFFERENCE: Check category matching ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'category_difference':
        client = intent.get('client')
        quest = q['question'].lower()
        categories = {row[0] for row in db.execute("SELECT DISTINCT category FROM projects WHERE category IS NOT NULL").fetchall()}
        found_cats = [
            cat for cat, pattern in query_engine._CATEGORY_PATTERNS.items()
            if cat in categories and re.search(pattern, quest, re.IGNORECASE)
        ]
        if len(found_cats) < 2:
            print(f"  PROBLEM {q['qid']}: Only found {len(found_cats)} categories: {found_cats}")
            print(f"    Q: {q['question'][:200]}")
        elif client:
            cat1, cat2 = found_cats[:2]
            v1 = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND category = ?", (client, cat1)).fetchone()[0] or 0
            v2 = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND category = ?", (client, cat2)).fetchone()[0] or 0
            if v1 == 0 and v2 == 0:
                print(f"  PROBLEM {q['qid']}: Both categories zero for client '{client}': {cat1}={v1}, {cat2}={v2}")
                print(f"    Q: {q['question'][:200]}")
            elif v1 == 0 or v2 == 0:
                print(f"  WARNING {q['qid']}: One category zero for client '{client}': {cat1}={v1}, {cat2}={v2}")

# ============================================================
# 5. Check mean_minus_median: verify client resolution
# ============================================================
print("\n=== MEAN_MINUS_MEDIAN: Check client resolution ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'mean_minus_median':
        client = query_engine._resolve_client_from_intent(db, intent)
        engineer = intent.get('engineer')
        if client:
            vals = db.execute("SELECT contract_value FROM projects WHERE client_name = ? ORDER BY contract_value", (client,)).fetchall()
            vals = [x[0] for x in vals if x[0]]
            mean = sum(vals) / len(vals)
            n = len(vals)
            if n % 2 == 0:
                median = (vals[n//2 - 1] + vals[n//2]) / 2
            else:
                median = vals[n//2]
            diff = mean - median
            print(f"  {q['qid']}: client='{client}' n={n} mean={mean:.0f} median={median:.0f} diff={diff:.0f}")
        elif engineer:
            vals = db.execute("""
                SELECT p.contract_value FROM projects p
                JOIN engineer_projects ep ON p.project_id = ep.project_id
                JOIN engineers e ON ep.engineer_id = e.engineer_id
                WHERE e.name = ?
                ORDER BY p.contract_value
            """, (engineer,)).fetchall()
            vals = [x[0] for x in vals if x[0]]
            if vals:
                mean = sum(vals) / len(vals)
                n = len(vals)
                if n % 2 == 0:
                    median = (vals[n//2 - 1] + vals[n//2]) / 2
                else:
                    median = vals[n//2]
                diff = mean - median
                print(f"  {q['qid']}: engineer='{engineer}' (no client) n={n} mean={mean:.0f} median={median:.0f} diff={diff:.0f}")
            else:
                print(f"  PROBLEM {q['qid']}: No projects for engineer '{engineer}'!")
        else:
            print(f"  PROBLEM {q['qid']}: No client or engineer!")
            print(f"    Q: {q['question'][:150]}")

# ============================================================
# 6. Check unpaid_balance: compare outstanding vs invoiced-received
# ============================================================
print("\n=== UNPAID_BALANCE: Cross-check outstanding vs (invoiced-received) ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'unpaid_balance':
        client = intent.get('client')
        if client:
            r1 = db.execute("SELECT SUM(outstanding) FROM receivables WHERE client = ?", (client,)).fetchone()[0] or 0
            r2 = db.execute("SELECT SUM(invoiced) - SUM(received) FROM receivables WHERE client = ?", (client,)).fetchone()[0] or 0
            if abs(r1 - r2) > 1:
                print(f"  DISCREPANCY {q['qid']}: client='{client}' outstanding={r1} (invoiced-received)={r2:.0f} diff={r1-r2:.0f}")
            else:
                print(f"  {q['qid']}: client='{client}' outstanding={r1}")

db.close()
