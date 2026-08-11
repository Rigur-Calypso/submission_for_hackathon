import re
import json

with open('questions.json') as f:
    qs = json.load(f)['questions']

zeros = ['HV-IC-0041', 'HV-IC-0044', 'HV-IC-0061', 'HV-IC-0085', 'HV-IC-0122', 'HV-IC-0178', 'HV-IC-0198', 'HV-IC-0244', 'HV-IC-0260', 'HV-IC-0276', 'HV-IC-0314', 'HV-IC-0316', 'HV-IC-0333', 'HV-IC-0357', 'HV-IC-0371', 'HV-IC-0386', 'HV-IC-0389', 'HV-IC-0392', 'HV-IC-0397', 'HV-IC-0400', 'HV-IC-0401', 'HV-IC-0405', 'HV-IC-0408', 'HV-IC-0410', 'HV-IC-0412', 'HV-IC-0420', 'HV-IC-0436', 'HV-IC-0438', 'HV-IC-0453', 'HV-IC-0463', 'HV-IC-0464', 'HV-IC-0468']

def get_intent(q):
    if re.search(r'gap between.*awarded.*invoiced|gap between.*assigned.*billed|awarded.*versus.*invoiced.*shortfall|shortfall between.*awarded.*billed|amount after we cross-check against the invoice amount|gap between the full value of their awards and what we.ve managed to invoice|actual gap between what they.ve sanctioned and what we.ve billed|shortfall between.*approved.*billed|shortfall between.*total contract value.*actually billed|gap between.*value.*secured.*billed|shortfall between.*contract value.*actually billed|shortfall between.*total value.*bill|gap between.*secured.*billed|gap between.*committed us to.*formally claimed|gap between.*committed us to.*actually billed|gap between.*award value.*billed amount|true gap between the full value of their awards and what we.ve managed to invoice|gap between what they.ve sanctioned and what we.ve billed', q, re.IGNORECASE):
        return 'gap_awarded_invoiced'
    elif re.search(r'difference|spread|subtract|compare', q, re.IGNORECASE) and len(re.findall(r'irrigation|epc|roads|highways|tunnels|bridges|water|sewerage|buildings|expressways', q, re.IGNORECASE)) >= 2 and not re.search(r'mean|median|between.*(?:largest|biggest)', q, re.IGNORECASE):
        return 'category_difference'
    elif re.search(r'unpaid balance|balance still owed|remaining balance|adjusted balance|deduction of what they.ve cleared|net balance due|total unpaid amount|amount remains on the invoices|true balance|balance when I cross-check|total amount still due|amount still outstanding|total unpaid value', q, re.IGNORECASE):
        return 'unpaid_balance'
    elif re.search(r'actual combined value of every completed assignment|outstanding contract value we still need to secure', q, re.IGNORECASE):
        return 'doc_filtered_aggregate' # just forcing it for now if needed, wait no.
    return 'unknown'

for qid in zeros:
    text = next((x['question'] for x in qs if x['qid'] == qid), '')
    print(f"{qid}: {get_intent(text)} -> {text}")
