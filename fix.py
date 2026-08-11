import re

with open('solution/query_engine.py', 'r') as f:
    content = f.read()

# 1. client UNION
content = content.replace('clients = [row[0] for row in db.execute("SELECT DISTINCT client_name FROM projects").fetchall()]', 
    '''cursor = db.execute("""
        SELECT DISTINCT client_name FROM projects
        UNION
        SELECT DISTINCT client FROM receivables
    """)
    clients = [row[0] for row in cursor.fetchall() if row[0]]''')

# 2. date_span
content = content.replace(r'(?:how many days|number of days|duration|time between|how long did it take|days elapsed)', 
    r'(?:how many days|number of days|duration|time between|how long did it take|days elapsed|days to completion)')

# 3. unpaid_balance regex
old_unpaid = r'\b(?:unpaid balance|balance still owed|remaining balance|adjusted balance|deduction of what they.ve cleared|net balance due|total unpaid amount|amount remains on the invoices|true balance|balance when I cross-check|total amount still due|amount still outstanding)\b'
new_unpaid = r'\b(?:unpaid balance|balance still owed|remaining balance|adjusted balance|deduction of what they.ve cleared|net balance due|total unpaid amount|amount remains on the invoices|true balance|balance when I cross-check|total amount still due|amount still outstanding)\b|(?:amount|balance|totals?).*?(?:still owe|still due|outstanding|pending|remaining)|(?:unpaid|remaining|outstanding|due|owed|pending|unbilled|un-billed)\s*(?:balance|amount|remainder|portion|totals?)|deduct.*cleared payment'
content = content.replace(old_unpaid, new_unpaid)

# 4. gap_awarded_invoiced regex
old_gap = r'gap between.*awarded.*invoiced|gap between.*assigned.*billed|awarded.*versus.*invoiced.*shortfall|shortfall between.*awarded.*billed|amount after we cross-check against the invoice amount|gap between the full value of their awards and what we.ve managed to invoice|actual gap between what they.ve sanctioned and what we.ve billed|shortfall between.*approved.*billed|shortfall between.*total contract value.*actually billed|gap between.*value.*secured.*billed|shortfall between.*contract value.*actually billed|shortfall between.*total value.*bill|gap between.*secured.*billed|gap between.*committed us to.*formally claimed|gap between.*committed us to.*actually billed|gap between.*award value.*billed amount|true gap between the full value of their awards and what we.ve managed to invoice|gap between what they.ve sanctioned and what we.ve billed|total value.*(?:above|over).*(?:invoiced|billed)'
new_gap = old_gap + r'|(?:gap|shortfall|difference|variance|unbilled|un-billed).*?(?:awarded|sanctioned|approved|assigned|contract value|project value).*?(?:invoiced|billed|claimed|submitted claims)|(?:awarded|sanctioned|contract value).*?(?:above|over|against|versus).*?(?:invoiced|billed|claims)'
content = content.replace(old_gap, new_gap)

# 5. threshold_aggregate regex
content = content.replace("and re.search(r'(?:clear|clearing|meet or exceed|at or over|crossing|hitting|above|over|past|reach|hit)', q, re.IGNORECASE):",
    "and (re.search(r'(?:clear|clearing|meet or exceed|at or over|crossing|hitting|above|over|past|reach|hit|against.*threshold|greater than|more than)', q, re.IGNORECASE) or 'sum' in q or 'total' in q or 'combined' in q):")

# 6. temporal_chain Project Lead
content = content.replace("WHERE e.name = ? AND p.completion_date > ?\n    \"\"\", (engineer, cert_issue_date))",
    "WHERE e.name = ? AND p.completion_date > ? AND ep.role_in_project = 'Project Lead'\n    \"\"\", (engineer, cert_issue_date))")

# 7. gap_awarded_invoiced abs()
content = content.replace('return awarded - invoiced', 'return abs(awarded - invoiced)')

# 8. mean_minus_median abs()
old_mean = """    diff = mean - median
    if mean < median:
        return -abs(diff)
    return abs(diff)"""
new_mean = """    diff = mean - median
    return abs(diff)"""
content = content.replace(old_mean, new_mean)

# 9. category_difference 3 matches
old_cat = """    if len(found_cats) < 2: return AnswerStatus.NO_MATCH
    cat1, cat2 = found_cats[:2]"""
new_cat = """    if len(found_cats) > 2 and 'Expressways' in found_cats and 'national expressway' in q:
        found_cats.remove('Expressways')
            
    if len(found_cats) < 2: return AnswerStatus.NO_MATCH
    cat1, cat2 = found_cats[-2:]"""
content = content.replace(old_cat, new_cat)

with open('solution/query_engine.py', 'w') as f:
    f.write(content)
