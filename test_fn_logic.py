#!/usr/bin/env python3
import json, sqlite3, sys, os, re
db = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solution', 'knowledge_graph.db'))

with open('questions.json') as f:
    questions = json.load(f)['questions']

engineers_all = [row[0] for row in db.execute("SELECT DISTINCT name FROM engineers").fetchall()]

def extract_project_from_question(question, db, engineer=None):
    # Simplified just for testing
    from rapidfuzz import fuzz
    def normalize(s: str) -> str:
        s = s.lower()
        s = re.sub(r'\b(?:ltd|limited|corp|corporation|inc|govt|government|dept|department|of|pvt|private|the|m/s)\b', '', s)
        s = re.sub(r'[^\w\s]', '', s)
        return re.sub(r'\s+', ' ', s).strip()

    pkg_match = re.search(r'(?:Package|Pkg)[\s-]*(\d+)', question, re.IGNORECASE)
    if pkg_match:
        pkg_num = pkg_match.group(1)
        row = db.execute("SELECT project_name FROM projects WHERE pkg_number = ?", (int(pkg_num),)).fetchone()
        if row: return row[0]
            
    cursor = db.execute("SELECT project_name FROM projects")
    all_projects = [row[0] for row in cursor.fetchall()]
    
    eng_projects = set()
    if engineer:
        cursor = db.execute("""
            SELECT p.project_name FROM projects p
            JOIN engineer_projects ep ON p.project_id = ep.project_id
            JOIN engineers e ON ep.engineer_id = e.engineer_id
            WHERE e.name = ?
        """, (engineer,))
        eng_projects = set(row[0] for row in cursor.fetchall())
    
    q_norm = normalize(question)
    best_matches = []
    
    for project in all_projects:
        proj_norm = normalize(project)
        if not proj_norm: continue
        score = fuzz.token_set_ratio(proj_norm, q_norm)
        if score >= 60:
            best_matches.append((score, project))
            
    if best_matches:
        best_matches.sort(key=lambda x: (x[0], x[1] in eng_projects), reverse=True)
        top_match = best_matches[0][1]
        
        if engineer and top_match not in eng_projects:
            top_base = re.sub(r'\s*(?:—|-)?\s*Pkg-\d+', '', top_match, flags=re.IGNORECASE).strip()
            for ep in eng_projects:
                ep_base = re.sub(r'\s*(?:—|-)?\s*Pkg-\d+', '', ep, flags=re.IGNORECASE).strip()
                if top_base.lower() == ep_base.lower():
                    return ep
        return top_match
    return None

for q in questions:
    quest = q['question']
    q_lower = quest.lower()
    # Check if a full name is in there
    eng = None
    for e in engineers_all:
        if e.lower() in q_lower:
            eng = e
            break
            
    if not eng:
        first_name_matches = []
        for e in engineers_all:
            fn = e.split()[0].lower()
            if re.search(rf'\b{fn}(?:\'?s)?\b', q_lower):
                first_name_matches.append(e)
                
        if len(first_name_matches) == 1:
            eng = first_name_matches[0]
        elif len(first_name_matches) > 1:
            temp_project = extract_project_from_question(quest, db)
            if temp_project:
                pkg_match = re.search(r'Pkg-(\d+)', temp_project, re.IGNORECASE)
                if pkg_match:
                    pkg_num = int(pkg_match.group(1))
                    assigned = [row[0] for row in db.execute("""
                        SELECT e.name FROM engineers e
                        JOIN engineer_projects ep ON e.engineer_id = ep.engineer_id
                        JOIN projects p ON ep.project_id = p.project_id
                        WHERE p.pkg_number = ?
                    """, (pkg_num,)).fetchall()]
                    
                    found = False
                    for candidate in first_name_matches:
                        if candidate in assigned:
                            eng = candidate
                            found = True
                            break
                    if not found:
                        eng = first_name_matches[0]
                else:
                    eng = first_name_matches[0]
            else:
                eng = first_name_matches[0]
                
    if eng:
        # Just to check the interesting ones
        if q['qid'] in ('HV-IC-0244', 'HV-IC-0318', 'HV-IC-0118'):
            print(f"{q['qid']}: eng={eng} | Q={quest[:60]}")

