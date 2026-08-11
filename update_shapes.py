import re

with open('solution/query_engine.py', 'r') as f:
    content = f.read()

# collection_pct
content = re.sub(
    r"if re\.search\(r'collection \(\?:figure\|percentage\|rate\|%\)\|billed amount collected\|percentage of everything billed\.\*actually been collected', q, re\.IGNORECASE\):",
    r"if re.search(r'collection (?:figure|percentage|rate|%)|billed amount collected|percentage of everything billed.*actually been collected|percentage out of 100 has actually cleared|percentage out of 100 collected aligns|percentage out of 100 of the total billed amount has actually been collected', q, re.IGNORECASE):",
    content
)

# unpaid_balance
new_gap = r"""
    # unpaid_balance
    elif re.search(r'\b(?:unpaid balance|balance still owed|remaining balance|adjusted balance|deduction of what they.ve cleared|net balance due|total unpaid amount|amount remains on the invoices|true balance|balance when I cross-check|total amount still due|amount still outstanding)\b', q, re.IGNORECASE):
        intent['shape'] = 'unpaid_balance'
        intent['answer_type'] = 'money'

    # gap_awarded_invoiced
    elif re.search(r'gap between.*awarded.*invoiced|gap between.*assigned.*billed|awarded.*versus.*invoiced.*shortfall|shortfall between.*awarded.*billed|amount after we cross-check against the invoice amount|gap between the full value of their awards and what we’ve managed to invoice|actual gap between what they\'ve sanctioned and what we\'ve billed|shortfall between.*approved.*billed|shortfall between.*total contract value.*actually billed|gap between.*value.*secured.*billed|shortfall between.*contract value.*actually billed|shortfall between.*total value.*bill|gap between.*secured.*billed|gap between.*committed us to.*formally claimed|gap between.*committed us to.*actually billed|gap between.*award value.*billed amount|true gap between the full value of their awards and what we’ve managed to invoice|gap between what they\'ve sanctioned and what we\'ve billed', q, re.IGNORECASE):"""

content = re.sub(
    r"""    # gap_awarded_invoiced\n    elif re\.search\(r'gap between\.\*awarded\.\*invoiced.*?', q, re\.IGNORECASE\):""",
    new_gap,
    content,
    flags=re.DOTALL
)

# category_difference and year_difference
new_year = r"""
    # category_difference
    elif re.search(r'difference.*(?:scopes|categories|workstreams|value)|spread across both scopes|subtract the .* figure from the .* one', q, re.IGNORECASE) and not re.search(r'between\s+(?:the\s+|that\s+)?(20\d\d)', q, re.IGNORECASE):
        intent['shape'] = 'category_difference'
        intent['answer_type'] = 'money'
        
    # year_difference
    elif re.search(r'(?:between\s+(?:the\s+|that\s+)?(20\d\d)\s+and\s+(?:the\s+)?(20\d\d)|(?:variance|difference|shift|movement).*?(20\d\d).*?(20\d\d)|(20\d\d).*?(20\d\d).*?(?:shift|movement|gap|difference|variance))', q, re.IGNORECASE) and not re.search(r'mean|median', q, re.IGNORECASE):
        years = re.findall(r'(20\d\d)', q)
        if len(years) >= 2:
            intent['shape'] = 'year_difference'
            intent['years'] = (years[0], years[1])
            intent['answer_type'] = 'money'"""

content = re.sub(
    r"""    # year_difference\n    elif re\.search\(r'between\\s\+\(\?:the\\s\+\|that\\s\+\)\?\(20\\d\\d\).*?intent\['answer_type'\] = 'money'""",
    new_year,
    content,
    flags=re.DOTALL
)

# referenced_share
new_ref = r"""    # referenced_share (includes custom)
    elif re.search(r'(?:percentage|percent|%|number out of one hundred|out of one hundred|out-of-100|share of those assignments|portion of our work)', q, re.IGNORECASE) and \
         re.search(r'(?:reference|verification|referenced|client approval|client endorsement|client sign-off|testimonial|cleared|backed by a client reference)', q, re.IGNORECASE):"""

content = re.sub(
    r"""    # referenced_share \(includes custom\)\n    elif re\.search\(r'\(\?:percentage\|percent\|%\|number out of one hundred\|out of one hundred\)', q, re\.IGNORECASE\) and \\\n         re\.search\(r'\(\?:reference\|verification\|referenced\|client approval\|client endorsement\|client sign-off\|testimonial\)', q, re\.IGNORECASE\):""",
    new_ref,
    content,
    flags=re.DOTALL
)

# date_span
new_date = r"""    # date_span: "days" / "interval" / "duration" (including custom)
    elif re.search(r'\bdays\b|\binterval\b|\bduration\b|how long it|elapsed period|elapsed time|exact span from|count from|count to|actual count from that certification date', q, re.IGNORECASE):"""

content = re.sub(
    r"""    # date_span: "days" / "interval" / "duration" \(including custom\)\n    elif re\.search\(r'\\bdays\\b\|\\binterval\\b\|\\bduration\\b\|how long it\|elapsed period\|elapsed time\|exact span from\|count from\|count to', q, re\.IGNORECASE\):""",
    new_date,
    content,
    flags=re.DOTALL
)

with open('solution/query_engine.py', 'w') as f:
    f.write(content)

print("Updated query_engine.py shapes!")
