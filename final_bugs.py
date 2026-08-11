#!/usr/bin/env python3
"""Final bug identification — check all remaining edge cases."""
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
# 1. Check which questions have "March 10th" format (th suffix after month)
# ============================================================
print("=== QUESTIONS WITH 'March 10th' FORMAT ===")
for q in questions:
    quest = q['question']
    if re.search(r'(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:st|nd|rd|th)', quest, re.IGNORECASE):
        intent = query_engine.classify_question(quest, db)
        cert_date = intent.get('cert_issue_date')
        print(f"  {q['qid']}: cert_date={cert_date} shape={intent['shape']} Q: {quest[:120]}")

# ============================================================
# 2. Check the avg_work_size rounding behavior 
# ============================================================
print("\n=== AVG_WORK_SIZE: Rounding check ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'avg_work_size':
        client = query_engine._resolve_client_from_intent(db, intent)
        if client:
            vals = db.execute("SELECT contract_value FROM projects WHERE client_name = ?", (client,)).fetchall()
            vals = [v[0] for v in vals if v[0]]
            if vals:
                raw_avg = sum(vals) / len(vals)
                rounded = round(raw_avg)
                # Check if raw avg has decimal part
                if raw_avg != rounded:
                    print(f"  {q['qid']}: client='{client}' raw_avg={raw_avg} rounded={rounded} diff={abs(raw_avg - rounded)}")

# ============================================================
# 3. Check mean_minus_median rounding
# ============================================================
print("\n=== MEAN_MINUS_MEDIAN: Rounding check ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'mean_minus_median':
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        val = res.value
        # Check if it's a float with many decimals
        if isinstance(val, float) and val != int(val):
            print(f"  {q['qid']}: val={val}")

# ============================================================
# 4. Check gap_to_threshold questions more carefully
# ============================================================
print("\n=== GAP_TO_THRESHOLD: Full check ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'gap_to_threshold':
        client = intent.get('client')
        threshold = intent.get('threshold')
        if client and threshold:
            total = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ?", (client,)).fetchone()[0] or 0
            gap = max(0, threshold - total)
            print(f"  {q['qid']}: client='{client}' threshold={threshold:>12,} total={total:>12,} gap={gap:>12,}")
            print(f"    Q: {q['question'][:200]}")

# ============================================================
# 5. Check absence questions
# ============================================================
print("\n=== ABSENCE: Full check ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'absence':
        client = intent.get('client')
        if client:
            total = db.execute("SELECT COUNT(*) FROM projects WHERE client_name = ?", (client,)).fetchone()[0]
            no_ref = db.execute("SELECT COUNT(*) FROM projects WHERE client_name = ? AND has_reference_letter = 0", (client,)).fetchone()[0]
            has_ref = db.execute("SELECT COUNT(*) FROM projects WHERE client_name = ? AND has_reference_letter = 1", (client,)).fetchone()[0]
            print(f"  {q['qid']}: client='{client}' total={total} no_ref={no_ref} has_ref={has_ref}")
            print(f"    Q: {q['question'][:200]}")

# ============================================================
# 6. Check the hop_aggregate handler: does it sum ALL client projects
#    or just the engineer's projects?
# ============================================================
print("\n=== HOP_AGGREGATE: Check if questions ask for engineer-specific or client-wide ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'hop_aggregate':
        eng = intent.get('engineer')
        client = query_engine._resolve_client_from_intent(db, intent)
        quest = q['question'].lower()
        
        if eng and client:
            # Check if question says "every completed assignment HE has done" vs "for that client"
            # The question intent is usually about the CLIENT's total, not the engineer's total
            client_total = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ?", (client,)).fetchone()[0] or 0
            eng_total = db.execute("""
                SELECT SUM(p.contract_value) FROM projects p
                JOIN engineer_projects ep ON p.project_id = ep.project_id
                JOIN engineers e ON ep.engineer_id = e.engineer_id
                WHERE e.name = ? AND p.client_name = ?
            """, (eng, client)).fetchone()[0] or 0
            
            if client_total != eng_total:
                # These could be wrong if the question asks about the engineer's work specifically
                if 'every completed assignment' in quest and ('he has' in quest or 'she has' in quest or "he's" in quest or "she's" in quest or "delivered" in quest):
                    pass  # These say "for that client" so client total is right
                # But if it says "his" or "her" total value of works...
                elif 'his' in quest or 'her ' in quest or 'their ' in quest:
                    pass  # Still usually means for the client

db.close()
