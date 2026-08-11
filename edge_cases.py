#!/usr/bin/env python3
"""Check edge cases and potential misclassification patterns."""
import json, sqlite3, sys, os, re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution'))
import query_engine

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db')
db = sqlite3.connect(DB_PATH)

with open('questions.json') as f:
    data = json.load(f)
questions = data['questions']

# ============================================================
# 1. Check for questions where the QUESTION says "percentage" or "percent" 
#    but we don't classify as a percentage-returning shape
# ============================================================
print("=== QUESTIONS WITH PERCENT KEYWORDS BUT NON-PERCENT SHAPE ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    quest_lower = q['question'].lower()
    if q.get('answer_type') == 'percent' and intent['answer_type'] != 'percent':
        print(f"  {q['qid']}: answer_type=percent but shape={intent['shape']} answer_type={intent['answer_type']}")
        print(f"    Q: {q['question'][:180]}")

# ============================================================
# 2. Check for collection_pct questions — are they correctly using
#    the hop path (engineer → project → client → receivables)?
# ============================================================
print("\n=== COLLECTION_PCT: Verify engineer→project→client hop ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'collection_pct':
        quest = q['question']
        # Check if the question mentions an engineer
        eng = intent.get('engineer')
        proj = intent.get('project')
        client = intent.get('client')
        
        # If engineer is mentioned, the client should be resolved from the engineer's project
        if eng and not client and proj:
            m = re.search(r'Pkg-(\d+)', proj, re.IGNORECASE)
            if m:
                pkg = int(m.group(1))
                c = db.execute("SELECT client_name FROM projects WHERE pkg_number = ?", (pkg,)).fetchone()
                if c:
                    resolved_client = c[0]
                    # Verify this engineer actually works on this project
                    e = db.execute("""
                        SELECT 1 FROM engineer_projects ep
                        JOIN engineers e ON ep.engineer_id = e.engineer_id
                        JOIN projects p ON ep.project_id = p.project_id
                        WHERE e.name = ? AND p.pkg_number = ?
                    """, (eng, pkg)).fetchone()
                    if not e:
                        print(f"  WARNING {q['qid']}: Engineer '{eng}' not assigned to Pkg-{pkg}!")
                        print(f"    Q: {quest[:150]}")

# ============================================================
# 3. Check hop_aggregate for potential overcounting
# ============================================================
print("\n=== HOP_AGGREGATE: Check for different questions getting same answer ===")
answers = {}
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'hop_aggregate':
        res = query_engine.answer_question_with_intent(q['question'], intent, db)
        client = query_engine._resolve_client_from_intent(db, intent)
        key = (client, res.value)
        if key not in answers:
            answers[key] = []
        answers[key].append(q['qid'])

for (client, val), qids in sorted(answers.items()):
    if len(qids) > 1:
        pass  # Multiple questions about the same client = same answer, expected
    # Print unique answers
    print(f"  {client}: {val:>15,} ({len(qids)} questions)")

# ============================================================
# 4. Check referenced_share — questions about reference letters
# ============================================================
print("\n=== REFERENCED_SHARE: Audit ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'referenced_share':
        client = intent.get('client')
        if client:
            total = db.execute("SELECT COUNT(*) FROM projects WHERE client_name = ?", (client,)).fetchone()[0]
            with_ref = db.execute("SELECT COUNT(*) FROM projects WHERE client_name = ? AND has_reference_letter = 1", (client,)).fetchone()[0]
            pct = round(with_ref / total * 100, 2) if total else 0
            print(f"  {q['qid']}: client='{client}' total={total} with_ref={with_ref} pct={pct}%")

# ============================================================
# 5. year_difference: check which years and if completion_date has those years
# ============================================================
print("\n=== YEAR_DIFFERENCE: Audit ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'year_difference':
        client = intent.get('client')
        years = intent.get('years')
        if client and years:
            y1, y2 = years
            c1 = db.execute("SELECT SUM(contract_value), COUNT(*) FROM projects WHERE client_name = ? AND completion_date LIKE ?", (client, f"{y1}%")).fetchone()
            c2 = db.execute("SELECT SUM(contract_value), COUNT(*) FROM projects WHERE client_name = ? AND completion_date LIKE ?", (client, f"{y2}%")).fetchone()
            val1 = c1[0] or 0
            val2 = c2[0] or 0
            n1 = c1[1]
            n2 = c2[1]
            diff = abs(val1 - val2)
            warning = "⚠️" if n1 == 0 or n2 == 0 else "✅"
            print(f"  {warning} {q['qid']}: client='{client}' {y1}(n={n1})={val1:>12,} {y2}(n={n2})={val2:>12,} diff={diff:>12,}")
            if n1 == 0 or n2 == 0:
                # Check which years this client has
                all_years = db.execute("SELECT DISTINCT substr(completion_date, 1, 4) FROM projects WHERE client_name = ? ORDER BY 1", (client,)).fetchall()
                print(f"    Available years: {[y[0] for y in all_years]}")
                print(f"    Q: {q['question'][:200]}")

# ============================================================
# 6. temporal_chain: Check cert_issue_date resolution
# ============================================================
print("\n=== TEMPORAL_CHAIN: Audit ===")
for q in questions:
    intent = query_engine.classify_question(q['question'], db)
    if intent['shape'] == 'temporal_chain':
        eng = intent.get('engineer')
        cert_date = intent.get('cert_issue_date')
        cert_type = intent.get('cert_type')
        
        # If no cert_date, try to resolve from engineer+cert_type
        if not cert_date and eng and cert_type:
            c = db.execute("""
                SELECT c.issue_date FROM certifications c
                JOIN engineers e ON c.engineer_id = e.engineer_id
                WHERE e.name = ? AND c.cert_type = ?
            """, (eng, cert_type)).fetchone()
            if c:
                cert_date = c[0]
        
        if eng and cert_date:
            projects = db.execute("""
                SELECT p.project_name, p.contract_value, p.completion_date
                FROM projects p
                JOIN engineer_projects ep ON p.project_id = ep.project_id
                JOIN engineers e ON ep.engineer_id = e.engineer_id
                WHERE e.name = ? AND p.completion_date > ?
                ORDER BY p.completion_date
            """, (eng, cert_date)).fetchall()
            total = sum(p[1] for p in projects if p[1])
            print(f"  {q['qid']}: eng='{eng}' cert_date={cert_date} projects_after={len(projects)} total={total:>12,}")
        else:
            print(f"  PROBLEM {q['qid']}: eng='{eng}' cert_date={cert_date} cert_type={cert_type}")

# ============================================================  
# 7. Check for questions about "completed" status filter
# ============================================================
print("\n=== COMPLETION STATUS: Are we filtering on project status? ===")
has_status_col = db.execute("PRAGMA table_info(projects)").fetchall()
col_names = [c[1] for c in has_status_col]
print(f"  Projects columns: {col_names}")
if 'status' in col_names:
    statuses = db.execute("SELECT DISTINCT status, COUNT(*) FROM projects GROUP BY status").fetchall()
    print(f"  Distinct statuses: {statuses}")
    print("  WARNING: We may need to filter on status='Completed' in many queries!")
else:
    print("  No 'status' column — all projects assumed completed")

db.close()
