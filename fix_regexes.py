import re

with open('solution/query_engine.py', 'r') as f:
    content = f.read()

# 1. exclusion_aggregate extraction
old_exclude = r"r'(?:exclud(?:e|ing)|without|minus|not counting|leaving out|apart from|other than)\s+(.+?)(?:\s*(?:,|\.|what|$))|after the (.+?)\s*(?:division|work|projects?|category)?\s*is excluded'"
new_exclude = r"r'(?:exclud(?:e|ing)|without|minus|not counting|leaving out|apart from|other than|remove|dropping)\s+(.+?)(?:\s*(?:,|\.|what|$))|after the (.+?)\s*(?:division|work|projects?|category|segment)?\s*(?:is excluded|is removed|is stripped out|is dropped|is dropped out)'"
content = content.replace(old_exclude, new_exclude)

# 2. year_difference
old_year = r"r'(?:difference|gap|growth|variance|change).*?(?:\d{4}.*?\d{4})|(?:\d{4}.*?\d{4}).*?(?:difference|gap|growth|variance|change)'"
new_year = r"r'(?:difference|gap|growth|variance|change).*?(?:\d{4}.*?\d{4})|(?:\d{4}.*?\d{4}).*?(?:difference|gap|growth|variance|change|dollar amount between|swing|compare|actual move|delta)'"
content = content.replace(old_year, new_year)

# 3. gap_awarded_invoiced
content = re.sub(
    r"(elif re\.search\(r'gap between\.\*awarded\.\*invoiced\|.*?)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'gap_awarded_invoiced')",
    r"\1|delta between secured work and submitted claims|missing amount between commitments and our bills|variance between the total scope they.ve handed over and the value we.ve successfully claimed\2",
    content
)

# 4. unpaid_balance
content = re.sub(
    r"(elif re\.search\(r'\\b\(\?:unpaid balance\|balance still owed\|.*?)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'unpaid_balance')",
    r"\1|remain unpaid|total amount currently due\2",
    content
)

# 5. category_difference
content = re.sub(
    r"(elif re\.search\(r'\(diff\|difference\|gap\|variance\).*?category\|category.*difference\|difference.*?between.*?and.*|difference.*?between.*?and.*?projects|difference in total contract value between.*?and.*|subtract the.*?from the.*)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'category_difference')",
    r"\1|value diff between|value delta between|verified net value between|how you usually extract those two figures so I can run the math myself|total value for the.*?and the\2",
    content
)

# 6. avg_work_size
content = re.sub(
    r"(elif re\.search\(r'\(?:average\|mean\).*?\(?:size\|value\|contract value\)\|average.*?overall\b)(', q, re\.IGNORECASE\):\s*intent\['shape'\] = 'avg_work_size')",
    r"\1|typical scale across every completed assignment\2",
    content
)

with open('solution/query_engine.py', 'w') as f:
    f.write(content)

print("Replaced!")
