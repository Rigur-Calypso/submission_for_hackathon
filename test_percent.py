import sqlite3
from query_engine import classify_question, handle_grading_absence

db = sqlite3.connect('solution/knowledge_graph.db')
q = "what share of their completed works have no formal grading on file, as a percentage?"
intent = classify_question(q)
intent['client'] = "Trishakti Power Generation Corporation"
print("Intent:", intent)
ans = handle_grading_absence(db, intent)
print("Answer:", ans)
