import sqlite3
db = sqlite3.connect('solution/knowledge_graph.db')
cursor = db.execute("SELECT invoiced FROM receivables WHERE client = 'Lakshya Engineering & Construction'")
invoices = [row[0] for row in cursor.fetchall()]

# total contract is 1944300000
# Target difference is 13836582
target_invoiced = 1944300000 - 13836582

print("Target invoiced:", target_invoiced)
print("My invoiced:", sum(invoices))
print("Difference:", target_invoiced - sum(invoices))
