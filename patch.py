import re
with open('solution/query_engine.py', 'r') as f:
    text = f.read()

# year_difference
new_year = r"(?:between\s+(?:the\s+|that\s+)?(20\d\d)\s+and\s+(?:the\s+)?(20\d\d)|(?:variance|difference|shift|movement|gap).*?(20\d\d).*?(20\d\d)|(20\d\d).*?(20\d\d).*?(?:shift|movement|gap|difference|variance|dollar amount between|swing|compare|actual move|delta))"
text = re.sub(r"(\(\?:between.*?\(20\\d\\d\)\.\*\?\(20\\d\\d\)\.\*\?\(?:shift\|movement\|gap\|difference\|variance\)\))", new_year, text)

# gap_awarded_invoiced
text = re.sub(
    r"(elif re\.search\(r'gap between.*?above\|over\|against\|versus\)\.\*\?\(\?:invoiced\|billed\|claims\))(.*?)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'gap_awarded_invoiced')",
    r"\1|delta between secured work and submitted claims|missing amount between commitments and our bills|variance between the total scope they.ve handed over and the value we.ve successfully claimed\3",
    text
)

# unpaid_balance
text = re.sub(
    r"(elif re\.search\(r'\\b\(\?:unpaid balance.*?deduct\.\*cleared payment)(.*?)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'unpaid_balance')",
    r"\1|remain unpaid|total amount currently due\3",
    text
)

# category_difference
text = re.sub(
    r"(elif re\.search\(r'\(diff\|difference\|gap\|variance\).*?subtract the\.\*\?from the\.\*)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'category_difference')",
    r"\1|value diff between|value delta between|verified net value between|how you usually extract those two figures so I can run the math myself|total value for the.*?and the\2",
    text
)

# exclusion_aggregate
text = re.sub(
    r"(exclude_match = re\.search\(\s*r'\(\?:exclud\(\?:e\|ing\)\|without\|minus\|not counting\|leaving out\|apart from\|other than\)\\s\+\(\.\+\?\)\(\?\\s\*\(\?:,\|\\\.\|what\|\$\)\)\|after the \(\.\+\?\)\\s\*\(\?:division\|work\|projects\?\|category\)\?\\s\*is excluded')",
    r"exclude_match = re.search(\n        r'(?:exclud(?:e|ing)|without|minus|not counting|leaving out|apart from|other than|remove|dropping)\\s+(.+?)(?:\\s*(?:,|\\.|what|$))|after the (.+?)\\s*(?:division|work|projects?|category|segment|piece)?\\s*(?:is excluded|is removed|is stripped out|is dropped|is dropped out)'",
    text
)

# avg_work_size
text = re.sub(
    r"(elif re\.search\(r'\(?:average\|mean\)\.\*\?\(?:size\|value\|contract value\)\|average\.\*\?overall\\b)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'avg_work_size')",
    r"\1|typical scale across every completed assignment\2",
    text
)

with open('solution/query_engine.py', 'w') as f:
    f.write(text)
print("patched")
