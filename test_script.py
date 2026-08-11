import json

with open('questions.json', 'r') as f:
    data = json.load(f)
    for row in data['questions']:
        if 'public works department account' in row['question'].lower():
            print(row['qid'], row['question'])
