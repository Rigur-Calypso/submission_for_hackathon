import re
with open('solution/query_engine.py') as f: content = f.read()

# category_difference
old_cat = r"""    # category_difference
    elif re.search(r'(?:difference|spread).*?(?:scopes|categories|workstreams|irrigation|epc|roads|highways|tunnels|bridges|water|sewerage|buildings|expressways)|subtract the .* figure from the .* one', q, re.IGNORECASE) and not re.search(r'mean|median|between.*(?:largest|biggest)', q, re.IGNORECASE):
        intent['shape'] = 'category_difference'
        intent['answer_type'] = 'money'"""

new_cat = r"""    # category_difference
    elif re.search(r'difference|spread|subtract|compare', q, re.IGNORECASE) and len(re.findall(r'irrigation|epc|roads|highways|tunnels|bridges|water|sewerage|buildings|expressways', q, re.IGNORECASE)) >= 2 and not re.search(r'mean|median|between.*(?:largest|biggest)', q, re.IGNORECASE):
        intent['shape'] = 'category_difference'
        intent['answer_type'] = 'money'"""
content = content.replace(old_cat, new_cat)

# gap_awarded_invoiced
old_gap = r"""    # gap_awarded_invoiced
    elif re.search(r'gap between.*awarded.*invoiced|gap between.*assigned.*billed|awarded.*versus.*invoiced.*shortfall|shortfall between.*awarded.*billed|amount after we cross-check against the invoice amount|gap between the full value of their awards and what we’ve managed to invoice|actual gap between what they\'ve sanctioned and what we\'ve billed|shortfall between.*approved.*billed|shortfall between.*total contract value.*actually billed|gap between.*value.*secured.*billed|shortfall between.*contract value.*actually billed|shortfall between.*total value.*bill|gap between.*secured.*billed|gap between.*committed us to.*formally claimed|gap between.*committed us to.*actually billed|gap between.*award value.*billed amount|true gap between the full value of their awards and what we’ve managed to invoice|gap between what they\'ve sanctioned and what we\'ve billed', q, re.IGNORECASE):
        intent['shape'] = 'gap_awarded_invoiced'
        intent['answer_type'] = 'money'"""

new_gap = r"""    # gap_awarded_invoiced
    elif re.search(r'gap between.*awarded.*invoiced|gap between.*assigned.*billed|awarded.*versus.*invoiced.*shortfall|shortfall between.*awarded.*billed|amount after we cross-check against the invoice amount|gap between the full value of their awards and what we.ve managed to invoice|actual gap between what they.ve sanctioned and what we.ve billed|shortfall between.*approved.*billed|shortfall between.*total contract value.*actually billed|gap between.*value.*secured.*billed|shortfall between.*contract value.*actually billed|shortfall between.*total value.*bill|gap between.*secured.*billed|gap between.*committed us to.*formally claimed|gap between.*committed us to.*actually billed|gap between.*award value.*billed amount|true gap between the full value of their awards and what we.ve managed to invoice|gap between what they.ve sanctioned and what we.ve billed', q, re.IGNORECASE):
        intent['shape'] = 'gap_awarded_invoiced'
        intent['answer_type'] = 'money'"""
content = content.replace(old_gap, new_gap)

with open('solution/query_engine.py', 'w') as f: f.write(content)
print("Updated regexes")
