import json, sqlite3, sys
sys.path.insert(0, 'solution')
import query_engine

db = sqlite3.connect('solution/knowledge_graph.db')
clients = [row[0] for row in db.execute("SELECT DISTINCT client_name FROM projects").fetchall()]
engineers = [row[0] for row in db.execute("SELECT DISTINCT name FROM engineers").fetchall()]
projects = [row[0] for row in db.execute("SELECT DISTINCT project_name FROM projects").fetchall()]

with open('questions.json') as f:
    questions = json.load(f)['questions']

failed = [q['question'] for q in questions if query_engine.answer_question(q['question'], db).value == 0]

templates = {}
for q in failed:
    t = q
    for c in clients:
        if c.lower() in t.lower():
            t = t.replace(c, '[CLIENT]')
            t = t.replace(c.upper(), '[CLIENT]')
            t = t.replace(c.lower(), '[CLIENT]')
            t = t.replace(c.title(), '[CLIENT]')
    for e in engineers:
        if e.lower() in t.lower():
            t = t.replace(e, '[ENGINEER]')
            t = t.replace(e.upper(), '[ENGINEER]')
            t = t.replace(e.lower(), '[ENGINEER]')
            t = t.replace(e.title(), '[ENGINEER]')
    t_key = t[:50]
    templates[t_key] = t

print(f"Found {len(templates)} templates")
for t in templates.values():
    print("-", t)
