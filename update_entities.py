import json, sqlite3, sys
sys.path.insert(0, 'solution')
import query_engine

db = sqlite3.connect('solution/knowledge_graph.db')
engineers = [row[0] for row in db.execute("SELECT DISTINCT name FROM engineers").fetchall()]
clients = [row[0] for row in db.execute("SELECT DISTINCT client_name FROM projects").fetchall()]
projects = [row[0] for row in db.execute("SELECT DISTINCT project_name FROM projects").fetchall()]

print("Clients:")
print('\n'.join(clients))
