#!/usr/bin/env python3
"""
query_engine.py — Answer questions against the knowledge graph.

Each question "shape" maps to a specific query pattern against the SQLite database.
The engine:
  1. Classifies the question into a shape
  2. Extracts parameters (client, engineer, threshold, etc.)
  3. Executes the appropriate SQL query
  4. Returns a numerical answer
"""
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from dateutil import parser as dateparser


class AnswerStatus(Enum):
    RESOLVED = "resolved"          # plan compiled & executed successfully
    UNSUPPORTED = "unsupported"    # question shape not recognized
    AMBIGUOUS = "ambiguous"        # multiple valid interpretations
    NO_MATCH = "no_match"          # entities not found in DB

@dataclass
class QueryPlan:
    entities: dict
    relations: list[str]
    predicates: list[dict]
    aggregation: str
    aggregate_field: str
    comparison: dict | None
    exclusions: list[dict]
    output_type: str
    ambiguities: list[str] = field(default_factory=list)

@dataclass
class AnswerResult:
    value: float
    status: AnswerStatus
    plan: QueryPlan | None = None
    evidence: list[dict] = field(default_factory=list)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from currency import parse_indian_money, parse_threshold_words
from evaluate_utils import score_one

SOLUTION_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SOLUTION_DIR, 'knowledge_graph.db')


# ═══════════════════════════════════════════════════════════════════
# ENTITY EXTRACTION HELPERS
# ═══════════════════════════════════════════════════════════════════

def find_best_entity_match(text: str, entities: list[str], threshold: int = 80) -> str | None:
    """Find the best matching entity from a list."""
    import re

    from rapidfuzz import fuzz
    
    # Try exact Pkg-NNN match first if applicable
    pkg_match = re.search(r'Pkg-(\d+)', text, re.IGNORECASE)
    if pkg_match:
        pkg_num = pkg_match.group(1)
        for entity in entities:
            if entity and f'Pkg-{pkg_num}' in entity:
                return entity
                
    aliases = {
        'phed': 'Public Health Engineering Dept, Odisha',
        'pwd': 'Public Works Department',
        'nhai': 'National Highways Authority of India',
        'bhel': 'Bharat Heavy Electricals Limited',
        'ntpc': 'National Thermal Power Corporation',
    }
    for alias, canonical in aliases.items():
        text = re.sub(rf'\b{alias}\b', canonical, text, flags=re.IGNORECASE)
        
    def normalize(s: str) -> str:
        s = s.lower()
        s = re.sub(r'\b(?:ltd|limited|corp|corporation|inc|govt|government|dept|department|of|pvt|private|the|m/s)\b', '', s)
        s = re.sub(r'[^\w\s]', '', s)
        return re.sub(r'\s+', ' ', s).strip()
    
    text_norm = normalize(text)
    if not text_norm:
        return None
        
    # Exact normalized match
    for entity in entities:
        if entity and normalize(entity) == text_norm:
            return entity
            
    # Fuzzy partial match on normalized strings
    scored_matches = []
    for entity in entities:
        if not entity:
            continue
        entity_norm = normalize(entity)
        if not entity_norm:
            continue
            
        score = fuzz.partial_ratio(entity_norm, text_norm)
        if score >= threshold:
            scored_matches.append((score, entity))
            
    if not scored_matches:
        return None
        
    scored_matches.sort(key=lambda x: x[0], reverse=True)
    if len(scored_matches) > 1 and scored_matches[0][0] - scored_matches[1][0] <= 5:
        return None # Ambiguous
            
    return scored_matches[0][1]


def extract_project_from_question(question: str) -> str | None:
    """Extract project name from question text."""
    # Pattern 1: "Pkg-NNN" with surrounding context
    pkg_match = re.search(
        r'(?:the\s+)?(\w[\w\s]+?(?:—|–|-)\s*[\w\s]+?Pkg-\d+)',
        question, re.IGNORECASE
    )
    if pkg_match:
        return pkg_match.group(1).strip()
    
    # Pattern 2: "Package NNN" or "Package-NNN" (verbose form)
    pkg_match = re.search(r'Package[\s-]+(\d+)', question, re.IGNORECASE)
    if pkg_match:
        return f"Pkg-{pkg_match.group(1)}"
    
    return None


def extract_date_from_question(question: str) -> str | None:
    """Extract a date from the question text."""
    # ISO format: 2021-03-10
    m = re.search(r'(\d{4}-\d{2}-\d{2})', question)
    if m:
        return m.group(1)
    
    # Verbose: "March 10, 2021" or "10 March 2021" or "10th March, 2021"
    m = re.search(
        r'((?:\d{1,2}(?:st|nd|rd|th)?\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}|\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|September|October|November|December),?\s+\d{4})',
        question, re.IGNORECASE
    )
    if m:
        try:
            dt = dateparser.parse(m.group(1))
            return dt.strftime('%Y-%m-%d')
        except Exception:
            pass
    return None


def extract_threshold_from_question(question: str) -> int | None:
    """Extract a monetary threshold from the question."""
    q = question.lower()
    
    # Pattern: "INR 20 Cr" or "Rs. 73 Cr"
    m = re.search(r'((?:INR|Rs\.?|₹)\s*[\d,.]+\s*(?:Cr(?:ore)?|Lakh?))', question, re.IGNORECASE)
    if m:
        val = parse_indian_money(m.group(1))
        if val:
            return val
    
    # Pattern: "crossing the seventy-three crore mark"
    m = re.search(
        r'(?:crossing|hitting|reaching|above|over|past|exceeding|beyond)\s+(?:the\s+)?(.+?)\s+(?:mark|line|threshold|bar|level|figure)',
        q, re.IGNORECASE
    )
    if m:
        val = parse_threshold_words(m.group(1))
        if val:
            return val
    
    # Pattern: "target of INR 20 Cr" or "credential target of INR 20 Cr"
    m = re.search(r'target\s+of\s+((?:INR|Rs\.?|₹)\s*[\d,.]+\s*(?:Cr(?:ore)?|Lakh?))', question, re.IGNORECASE)
    if m:
        val = parse_indian_money(m.group(1))
        if val:
            return val
    
    # Pattern: "reach ... INR 20 Cr"
    m = re.search(r'reach\s+.*?((?:INR|Rs\.?|₹)\s*[\d,.]+\s*(?:Cr(?:ore)?|Lakh?))', question, re.IGNORECASE)
    if m:
        val = parse_indian_money(m.group(1))
        if val:
            return val
    
    # Word-based: "seventy-three crore" anywhere
    m = re.search(r'([\w][\w\s-]+?)\s+(crore|cr)\b', q)
    if m:
        word_part = m.group(1).strip()
        # Clean up leading context words
        word_part = re.sub(r'^.*?(?:the|of|our)\s+', '', word_part)
        val = parse_threshold_words(word_part + ' crore')
        if val and val > 0:
            return val
    
    return None


# ═══════════════════════════════════════════════════════════════════
# QUESTION CLASSIFIER
# ═══════════════════════════════════════════════════════════════════

def classify_question(question: str, db: sqlite3.Connection) -> dict:
    """Classify a question into a shape and extract parameters."""
    q = question.lower()
    
    intent = {
        'shape': 'unknown',
        'table_focus': 'projects', # defaults to projects
        'client': None,
        'engineer': None,
        'cert_type': None,
        'cert_id': None,
        'project': None,
        'threshold': None,
        'grading': None,
        'exclude_category': None,
        'role_filter': None,
        'cert_issue_date': None,
        'answer_type': 'count',
    }
    
    # ── Extract table focus ─────────────────────────────────────
    if re.search(r'\b(?:receivable|receivables|invoice|invoices|ageing)\b', q):
        intent['table_focus'] = 'receivables'
    elif re.search(r'\b(?:plant|machinery|equipment|asset|assets)\b', q):
        intent['table_focus'] = 'plant_register'
    elif re.search(r'\b(?:boq|bill of quantities|ra bill)\b', q):
        intent['table_focus'] = 'boq_items' 
    elif re.search(r'\b(?:trial balance|debit|credit)\b', q):
        intent['table_focus'] = 'trial_balance'
    
    # ── Extract named entities ──────────────────────────────────
    
    # Client name
    clients = [row[0] for row in db.execute("SELECT DISTINCT client_name FROM projects").fetchall()]
    intent['client'] = find_best_entity_match(q, clients)
    
    # Engineer name
    engineers = [row[0] for row in db.execute("SELECT DISTINCT name FROM engineers").fetchall()]
    intent['engineer'] = find_best_entity_match(q, engineers)
    
    # Project name
    intent['project'] = extract_project_from_question(question)
    
    # Cert type
    if 'pmp' in q:
        intent['cert_type'] = 'PMP'
    elif 'six sigma black belt' in q:
        intent['cert_type'] = 'Six Sigma Black Belt'
    elif 'six sigma green belt' in q:
        intent['cert_type'] = 'Six Sigma Green Belt'
    elif 'six sigma' in q:
        intent['cert_type'] = 'Six Sigma Black Belt'
    
    # Cert ID
    cert_id_match = re.search(r'(PMI-\d+|6S-\d+)', question)
    if cert_id_match:
        intent['cert_id'] = cert_id_match.group(1)
        # Resolve cert ID to engineer and cert_type
        row = db.execute('''
            SELECT e.name, c.cert_type 
            FROM certifications c 
            JOIN engineers e ON c.engineer_id = e.engineer_id 
            WHERE c.cert_id = ?
        ''', (intent['cert_id'],)).fetchone()
        if row:
            intent['engineer'] = row[0]
            intent['cert_type'] = row[1]
    
    # Cert issue date
    intent['cert_issue_date'] = extract_date_from_question(question)
    
    # Grading
    for grade in ['Excellent', 'Very Good', 'Good', 'Satisfactory', 'Fair']:
        if grade.lower() in q:
            intent['grading'] = grade
            break
    
    # Role filter — "as Prime" pattern
    if re.search(r'\bas\s+prime\b', q, re.IGNORECASE) or re.search(r'\bprime\s+contractor\b', q, re.IGNORECASE):
        intent['role_filter'] = 'Prime'
    elif re.search(r'\bsubcontractor\b|\bsub-contractor\b', q, re.IGNORECASE):
        intent['role_filter'] = 'Subcontractor'
    elif re.search(r'\bjv partner\b|\bjoint venture\b', q, re.IGNORECASE):
        intent['role_filter'] = 'JV Partner'
    
    # Threshold
    intent['threshold'] = extract_threshold_from_question(question)
    intent['threshold_op'] = '>='
    if intent['threshold']:
        if re.search(r'\b(?:crossing|exceeding|above|over|past|beyond|more than|greater than)\b', q):
            intent['threshold_op'] = '>'
        elif re.search(r'\b(?:at least|hitting|reaching|meeting|minimum)\b', q):
            intent['threshold_op'] = '>='
    
    # Exclude category
    exclude_match = re.search(
        r'(?:exclud(?:e|ing)|without|minus|not counting|leaving out|apart from|other than)\s+(.+?)(?:\s*(?:,|\.|what|$))',
        q, re.IGNORECASE
    )
    if exclude_match:
        exclude_text = exclude_match.group(1).strip()
        categories = [row[0] for row in db.execute("SELECT DISTINCT category FROM projects").fetchall()]
        intent['exclude_category'] = find_best_entity_match(exclude_text, categories, threshold=60)
    
    # ── Classify shape ──────────────────────────────────────────
    
    # 1. absence: "no client reference letter" / "lack a reference"
    if re.search(r'(?:no|lack|without|missing)\s+.*?reference\s+letter', q, re.IGNORECASE):
        intent['shape'] = 'absence'
        intent['answer_type'] = 'count'
    
    # 1.5. grading_absence: "no grading" / "lack of grading" / "missing grading"
    elif re.search(r'(?:no|lack|without|missing)\s+.*?(?:formal\s+)?(?:quality\s+)?grading', q, re.IGNORECASE) or \
         re.search(r'what share.*?no grading', q, re.IGNORECASE):
        intent['shape'] = 'grading_absence'
        if re.search(r'(?:share|percentage|percent|%|number out of one hundred|out of one hundred)', q, re.IGNORECASE):
            intent['answer_type'] = 'percent'
        else:
            intent['answer_type'] = 'count'
    
    # 2. date_span: "days" / "interval" / "duration"
    elif re.search(r'\bdays\b|\binterval\b|\bduration\b', q, re.IGNORECASE):
        intent['shape'] = 'date_span'
        intent['answer_type'] = 'days'
    
    # 3. referenced_share: "percentage" or "number out of one hundred" + reference
    elif re.search(r'(?:percentage|percent|%|number out of one hundred|out of one hundred)', q, re.IGNORECASE) and \
         re.search(r'(?:reference|verification|referenced)', q, re.IGNORECASE):
        intent['shape'] = 'referenced_share'
        intent['answer_type'] = 'percent'
    
    # 4. distinct_count: "different categories" / "distinct work classifications"
    elif re.search(r'(?:different|distinct|unique)\s+(?:categories|work\s+classifications|types)', q, re.IGNORECASE) or \
         re.search(r'how many.*?(?:categories|classifications)', q, re.IGNORECASE):
        intent['shape'] = 'distinct_count'
        intent['answer_type'] = 'count'
    
    # 5. gap_to_threshold: "how much more" / "additional work" / "reach our target"
    elif re.search(r'(?:how much (?:more|additional)|additional.*?(?:work|must)|reach\s+(?:our|the)\s+(?:credential\s+)?target|shortfall|fall short|gap)', q, re.IGNORECASE):
        intent['shape'] = 'gap_to_threshold'
        intent['answer_type'] = 'money'
    
    # 6. rank_value: "largest ... exceed ... second" / "difference between"
    elif re.search(r'(?:largest|biggest).*?(?:exceed|second)|difference\s+between.*?(?:largest|biggest)', q, re.IGNORECASE):
        intent['shape'] = 'rank_value'
        intent['answer_type'] = 'money'
    
    # 7. role_split: "as Prime" with total/value
    elif intent.get('role_filter'):
        intent['shape'] = 'role_split'
        intent['answer_type'] = 'money'
    
    # 8. exclusion_aggregate: "excluding X"
    elif intent.get('exclude_category'):
        intent['shape'] = 'exclusion_aggregate'
        intent['answer_type'] = 'money'
    
    # 9. threshold_aggregate: "crossing X crore" / "hitting X line"
    elif intent.get('threshold') and re.search(r'(?:crossing|hitting|above|over|past)', q, re.IGNORECASE):
        intent['shape'] = 'threshold_aggregate'
        intent['answer_type'] = 'money'
    
    # 10. doc_filtered_aggregate: grading + total/value
    elif intent.get('grading') and re.search(r'(?:total|sum|aggregate|combined|amount)', q, re.IGNORECASE):
        intent['shape'] = 'doc_filtered_aggregate'
        intent['answer_type'] = 'money'
    
    # 11. temporal_chain: "after" + cert date + value
    elif re.search(r'(?:after|since|following|subsequent)', q, re.IGNORECASE) and \
         (intent.get('cert_issue_date') or intent.get('cert_type')) and \
         re.search(r'(?:combined|total|sum|value)', q, re.IGNORECASE):
        intent['shape'] = 'temporal_chain'
        intent['answer_type'] = 'money'
    
    # 12. avg_work_size: "average" / "mean"
    elif re.search(r'\baverage\b|\bmean\b', q, re.IGNORECASE):
        intent['shape'] = 'avg_work_size'
        intent['answer_type'] = 'money'
    
    # 13. hop_aggregate: general sum/total with engineer or client
    elif re.search(r'(?:total|sum|aggregate|combined|value|portfolio)', q, re.IGNORECASE):
        intent['shape'] = 'hop_aggregate'
        intent['answer_type'] = 'money'
    
    return intent


# ═══════════════════════════════════════════════════════════════════
# SHAPE HANDLERS
# ═══════════════════════════════════════════════════════════════════

def handle_absence(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Count projects for a client that have no reference letter."""
    client = intent['client']
    if not client:
        return AnswerStatus.NO_MATCH
    cursor = db.execute(
        "SELECT COUNT(*) FROM projects WHERE client_name = ? AND has_reference_letter = 0",
        (client,)
    )
    return cursor.fetchone()[0]


def handle_grading_absence(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Calculate count or percentage of projects for a client that have no formal quality grading."""
    client = intent['client']
    if not client:
        return AnswerStatus.NO_MATCH
    
    if intent.get('answer_type') == 'percent':
        cursor = db.execute("""
            SELECT 
                CAST(SUM(CASE WHEN grading IS NULL OR grading = '' THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) * 100
            FROM projects WHERE client_name = ?
        """, (client,))
        result = cursor.fetchone()[0]
        return round(result, 2) if result is not None else 0
    else:
        cursor = db.execute(
            "SELECT COUNT(*) FROM projects WHERE client_name = ? AND (grading IS NULL OR grading = '')",
            (client,)
        )
        return cursor.fetchone()[0]


def handle_date_span(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Calculate days between a cert issue date and a project completion date."""
    engineer = intent.get('engineer')
    project = intent.get('project')
    cert_issue_date_str = intent.get('cert_issue_date')
    cert_type = intent.get('cert_type')
    
    # Get cert issue date
    cert_date = None
    if cert_issue_date_str:
        cert_date = dateparser.parse(cert_issue_date_str)
    elif engineer and cert_type:
        cursor = db.execute("""
            SELECT c.issue_date FROM certifications c
            JOIN engineers e ON c.engineer_id = e.engineer_id
            WHERE e.name = ? AND c.cert_type = ?
        """, (engineer, cert_type))
        row = cursor.fetchone()
        if row and row[0]:
            cert_date = dateparser.parse(row[0])
    
    if not cert_date:
        return AnswerStatus.NO_MATCH
    
    # Get project completion date
    completion_date = None
    if project:
        pkg_match = re.search(r'Pkg-(\d+)', project, re.IGNORECASE)
        if pkg_match:
            pkg_num = int(pkg_match.group(1))
            cursor = db.execute(
                "SELECT completion_date FROM projects WHERE pkg_number = ?", (pkg_num,)
            )
            row = cursor.fetchone()
            if row and row[0]:
                completion_date = dateparser.parse(row[0])
    
    if cert_date and completion_date:
        return abs((completion_date - cert_date).days)
    return AnswerStatus.NO_MATCH


def handle_distinct_count(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Count distinct categories for an engineer's projects."""
    engineer = intent.get('engineer')
    if not engineer:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute("""
        SELECT COUNT(DISTINCT p.category) 
        FROM projects p
        JOIN engineer_projects ep ON p.project_id = ep.project_id
        JOIN engineers e ON ep.engineer_id = e.engineer_id
        WHERE e.name = ?
    """, (engineer,))
    return cursor.fetchone()[0]


def _resolve_client_from_intent(db: sqlite3.Connection, intent: dict) -> str | None:
    """Resolve the client name — either directly or via engineer+project hop."""
    client = intent.get('client')
    if client:
        return client
    
    # Hop: engineer → project → client
    engineer = intent.get('engineer')
    project = intent.get('project')
    
    if project:
        pkg_match = re.search(r'Pkg-(\d+)', project, re.IGNORECASE)
        if pkg_match:
            pkg_num = int(pkg_match.group(1))
            cursor = db.execute(
                "SELECT client_name FROM projects WHERE pkg_number = ?", (pkg_num,)
            )
            row = cursor.fetchone()
            if row:
                return row[0]
    
    # If only engineer, get their client(s) — if only one, use it
    if engineer:
        cursor = db.execute("""
            SELECT DISTINCT p.client_name
            FROM projects p
            JOIN engineer_projects ep ON p.project_id = ep.project_id
            JOIN engineers e ON ep.engineer_id = e.engineer_id
            WHERE e.name = ?
        """, (engineer,))
        clients = [row[0] for row in cursor.fetchall()]
        if len(clients) == 1:
            return clients[0]
    
    return None


def handle_hop_aggregate(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Sum contract values across a client's portfolio."""
    client = _resolve_client_from_intent(db, intent)
    if not client:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT SUM(contract_value) FROM projects WHERE client_name = ?", (client,)
    )
    return cursor.fetchone()[0] or 0


def handle_temporal_chain(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Sum contract values for projects an engineer led that completed after their cert date."""
    engineer = intent.get('engineer')
    cert_issue_date = intent.get('cert_issue_date')
    cert_type = intent.get('cert_type')
    
    if not cert_issue_date and engineer and cert_type:
        cursor = db.execute("""
            SELECT c.issue_date FROM certifications c
            JOIN engineers e ON c.engineer_id = e.engineer_id
            WHERE e.name = ? AND c.cert_type = ?
        """, (engineer, cert_type))
        row = cursor.fetchone()
        if row:
            cert_issue_date = row[0]
    
    if not cert_issue_date or not engineer:
        return AnswerStatus.NO_MATCH
    
    # Sum projects this engineer LED that completed AFTER cert date
    cursor = db.execute("""
        SELECT SUM(p.contract_value)
        FROM projects p
        JOIN engineer_projects ep ON p.project_id = ep.project_id
        JOIN engineers e ON ep.engineer_id = e.engineer_id
        WHERE e.name = ? AND p.completion_date > ?
    """, (engineer, cert_issue_date))
    
    return cursor.fetchone()[0] or 0


def handle_avg_work_size(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Calculate average contract value for a client's portfolio."""
    # Need to resolve client via project hop
    client = _resolve_client_from_intent(db, intent)
    if not client:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT AVG(contract_value) FROM projects WHERE client_name = ?", (client,)
    )
    result = cursor.fetchone()[0]
    return round(result) if result is not None else 0


def handle_doc_filtered_aggregate(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Sum contract values filtered by grading for a client."""
    client = intent.get('client')
    grading = intent.get('grading')
    
    if not client or not grading:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND grading = ?",
        (client, grading)
    )
    return cursor.fetchone()[0] or 0


def handle_exclusion_aggregate(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Sum contract values excluding a category for a client."""
    client = intent.get('client')
    exclude_cat = intent.get('exclude_category')
    
    if not client or not exclude_cat:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND category != ?",
        (client, exclude_cat)
    )
    return cursor.fetchone()[0] or 0


def handle_gap_to_threshold(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Calculate gap between current portfolio total and a threshold."""
    client = intent.get('client')
    threshold = intent.get('threshold')
    
    if not client or not threshold:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT SUM(contract_value) FROM projects WHERE client_name = ?", (client,)
    )
    current_total = cursor.fetchone()[0] or 0
    return max(0, threshold - current_total)


def handle_rank_value(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Find difference between largest and second-largest contract values for a client."""
    client = intent.get('client')
    if not client:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT contract_value FROM projects WHERE client_name = ? ORDER BY contract_value DESC LIMIT 2",
        (client,)
    )
    values = [row[0] for row in cursor.fetchall() if row[0]]
    if len(values) >= 2:
        return values[0] - values[1]
    return AnswerStatus.NO_MATCH


def handle_referenced_share(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Calculate percentage of projects with reference letters for a client."""
    client = intent.get('client')
    if not client:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute("""
        SELECT 
            CAST(SUM(has_reference_letter) AS FLOAT) / COUNT(*) * 100
        FROM projects WHERE client_name = ?
    """, (client,))
    result = cursor.fetchone()[0]
    return round(result, 2) if result is not None else 0


def handle_role_split(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Sum contract values filtered by role (Prime/Sub/JV) for a client."""
    client = intent.get('client')
    role = intent.get('role_filter')
    
    if not client or not role:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        "SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND role = ?",
        (client, role)
    )
    return cursor.fetchone()[0] or 0


def handle_threshold_aggregate(db: sqlite3.Connection, intent: dict) -> float | AnswerStatus:
    """Sum contract values for projects above a threshold for a client."""
    client = intent.get('client')
    threshold = intent.get('threshold')
    op = intent.get('threshold_op', '>=')
    
    if not client or not threshold:
        return AnswerStatus.NO_MATCH
    
    cursor = db.execute(
        f"SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND contract_value {op} ?",
        (client, threshold)
    )
    return cursor.fetchone()[0] or 0


# ═══════════════════════════════════════════════════════════════════
# DISPATCHER
# ═══════════════════════════════════════════════════════════════════

SHAPE_HANDLERS = {
    'absence': handle_absence,
    'date_span': handle_date_span,
    'distinct_count': handle_distinct_count,
    'hop_aggregate': handle_hop_aggregate,
    'temporal_chain': handle_temporal_chain,
    'avg_work_size': handle_avg_work_size,
    'doc_filtered_aggregate': handle_doc_filtered_aggregate,
    'exclusion_aggregate': handle_exclusion_aggregate,
    'gap_to_threshold': handle_gap_to_threshold,
    'grading_absence': handle_grading_absence,
    'rank_value': handle_rank_value,
    'referenced_share': handle_referenced_share,
    'role_split': handle_role_split,
    'threshold_aggregate': handle_threshold_aggregate,
}


def handle_financial_query(db: sqlite3.Connection, intent: dict, question: str) -> float | AnswerStatus:
    """Handle queries targeting the financial data tables."""
    table = intent['table_focus']
    q = question.lower()
    
    # If the question contains filters we don't handle well in deterministic engine
    if intent.get('client') or intent.get('engineer') or intent.get('project') or intent.get('exclude_category') or intent.get('role_filter'):
        return AnswerStatus.UNSUPPORTED
    
    # Also check for date, year, ageing, condition, contract
    if re.search(r'\b(20\d{2})\b', q) or re.search(r'\b(ageing|bucket|>|<|days|condition|good|fair|contract)\b', q):
        return AnswerStatus.UNSUPPORTED
        
    is_count = re.search(r'\b(?:how many|count|number of)\b', q)
    
    if table == 'receivables':
        if is_count:
            return db.execute("SELECT COUNT(*) FROM receivables").fetchone()[0]
        # Aggregate logic
        if 'outstanding' in q or 'due' in q:
            return db.execute("SELECT SUM(outstanding) FROM receivables").fetchone()[0]
        if 'received' in q or 'paid' in q:
            return db.execute("SELECT SUM(received) FROM receivables").fetchone()[0]
        return db.execute("SELECT SUM(invoiced) FROM receivables").fetchone()[0]
        
    elif table == 'plant_register':
        if is_count:
            return db.execute("SELECT COUNT(*) FROM plant_register").fetchone()[0]
        return db.execute("SELECT SUM(cost) FROM plant_register").fetchone()[0]
        
    elif table == 'boq_items':
        if is_count:
            return db.execute("SELECT COUNT(*) FROM boq_items").fetchone()[0]
        return db.execute("SELECT SUM(amount) FROM boq_items").fetchone()[0]
        
    elif table == 'trial_balance':
        if 'debit' in q:
            return db.execute("SELECT SUM(debit) FROM trial_balance").fetchone()[0]
        if 'credit' in q:
            return db.execute("SELECT SUM(credit) FROM trial_balance").fetchone()[0]
        return db.execute("SELECT SUM(balance) FROM trial_balance").fetchone()[0]
        
    return AnswerStatus.UNSUPPORTED


def answer_question_with_intent(question: str, intent: dict, db: sqlite3.Connection) -> AnswerResult:
    """Answer a question using a pre-computed intent dictionary."""
    plan = QueryPlan(
        entities={
            'client': intent.get('client'), 
            'engineer': intent.get('engineer'), 
            'project': intent.get('project'),
            'cert_type': intent.get('cert_type'),
            'cert_id': intent.get('cert_id')
        },
        relations=[],
        predicates=[],
        aggregation=intent.get('answer_type', 'count'),
        aggregate_field='*',
        comparison=intent.get('threshold'),
        exclusions=[],
        output_type='numeric'
    )
    
    if intent.get('table_focus', 'projects') != 'projects':
        answer = handle_financial_query(db, intent, question)
        if isinstance(answer, AnswerStatus):
            return AnswerResult(value=0, status=answer, plan=plan)
        return AnswerResult(value=answer, status=AnswerStatus.RESOLVED, plan=plan)
        
    handler = SHAPE_HANDLERS.get(intent.get('shape'))
    if handler:
        answer = handler(db, intent)
        if isinstance(answer, AnswerStatus):
            return AnswerResult(value=0, status=answer, plan=plan)
        return AnswerResult(value=answer, status=AnswerStatus.RESOLVED, plan=plan)
        
    return AnswerResult(value=0, status=AnswerStatus.UNSUPPORTED, plan=plan)


def answer_question(question: str, db: sqlite3.Connection) -> AnswerResult:
    """Answer a single question. Returns AnswerResult."""
    intent = classify_question(question, db)
    return answer_question_with_intent(question, intent, db)


# ═══════════════════════════════════════════════════════════════════
# MAIN — Test against sample questions
# ═══════════════════════════════════════════════════════════════════

if __name__ == '__main__':
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        print("Run build_kg.py first!")
        sys.exit(1)
    
    db = sqlite3.connect(DB_PATH)
    
    sample_path = os.path.join(SOLUTION_DIR, '..', 'sample_questions.json')
    with open(sample_path) as f:
        sample = json.load(f)
    
    print("Testing Query Engine against Sample Questions")
    print("=" * 80)
    
    correct = 0
    partial = 0
    total = len(sample['questions'])
    
    for q in sample['questions']:
        res = answer_question(q['question'], db)
        answer = res.value
        gold = q['answer']
        s = score_one(gold, answer)
        
        status = "✅" if s == 1.0 else ("🟡" if s > 0 else "❌")
        if s == 1.0:
            correct += 1
        elif s > 0:
            partial += 1
        
        print(f"  {status} {q['qid']:12s} status={res.status.value:15s} gold={gold!s:>15} got={answer!s:>15} score={s:.1f}")
        if s < 1.0:
            print(f"       Q: {q['question'][:120]}")
    
    print(f"\n{'='*80}")
    total_score = sum(score_one(q['answer'], answer_question(q['question'], db).value) for q in sample['questions'])
    print(f"SCORE: {correct}/{total} perfect, {partial} partial")
    print(f"TOTAL POINTS: {total_score:.1f} / {total}")
    
    db.close()
