import json, sqlite3, sys
sys.path.insert(0, './solution')
import query_engine

db = sqlite3.connect('./solution/knowledge_graph.db')
data = json.load(open('questions.json'))['questions']

for q in data:
    intent = query_engine.classify_question(q['question'], db)
    res = query_engine.answer_question_with_intent(q['question'], intent, db)
    if res.value == 0:
        print(f"[{q['qid']}] {q['question']}")
        print(f"  Shape: {intent['shape']}, Client: {intent.get('client')}, Eng: {intent.get('engineer')}, Proj: {intent.get('project')}")
        print(f"  Status: {res.status}")
        print(f"  Ans: {res.value}\n")
