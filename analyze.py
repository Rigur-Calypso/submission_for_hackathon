import json, sqlite3, sys
sys.path.insert(0, './solution')
import query_engine

db = sqlite3.connect('./solution/knowledge_graph.db')
data = json.load(open('questions.json'))['questions']

shapes = {}
for q in data:
    intent = query_engine.classify_question(q['question'], db)
    res = query_engine.answer_question_with_intent(q['question'], intent, db)
    shapes.setdefault(intent['shape'], []).append((q['qid'], q['question'], intent, res))

for shape, items in sorted(shapes.items()):
    print(f"\n=== Shape: {shape} ({len(items)}) ===")
    for qid, q, intent, res in items[:2]:  # print first 2 examples
        print(f"  [{qid}] Q: {q}")
        print(f"      Intent: client={intent.get('client')}, proj={intent.get('project')}, eng={intent.get('engineer')}")
        print(f"      Ans: {res.value} (Status: {res.status})")

    # print issues
    issues = [ (i[0], i[1]) for i in items if i[3].status != query_engine.AnswerStatus.RESOLVED or i[3].value == 0]
    if issues:
        print(f"  -> {len(issues)} issues (status!=RESOLVED or val==0):")
        for qid, q in issues[:3]:
            print(f"       [{qid}] {q}")
