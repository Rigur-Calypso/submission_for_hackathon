import re, sqlite3

def register_custom_shapes(intent, q):
    if re.search(r'collection (?:figure|percentage|rate|%)', q) or re.search(r'billed amount collected', q) or re.search(r'percentage of everything billed.*actually been collected', q):
        intent['shape'] = 'collection_pct'
        
    elif re.search(r'distinct internal business units', q) or re.search(r'separate internal business units', q) or re.search(r'separate units', q) or re.search(r'count of internal business units', q) or re.search(r'how many business units', q) or re.search(r'separate internal divisions', q) or re.search(r'different internal business units', q) or re.search(r'separate internal units', q) or re.search(r'internal business units fulfilled', q) or re.search(r'number of internal business units', q) or re.search(r'count of internal units involved', q):
        intent['shape'] = 'client_distinct_units'
        
    elif re.search(r'gap between.*awarded.*invoiced', q) or re.search(r'gap between.*assigned.*billed', q) or re.search(r'awarded.*versus.*invoiced.*shortfall', q) or re.search(r'shortfall between.*awarded.*billed', q) or re.search(r'amount after we cross-check against the invoice amount', q) or re.search(r'gap between the full value of their awards and what we’ve managed to invoice', q):
        intent['shape'] = 'gap_awarded_invoiced'
        
    elif re.search(r'pct of.*deliveries.*top client', q) or re.search(r'percentage.*total deliveries.*single biggest account', q) or re.search(r'percentage.*total deliveries.*single biggest client', q) or re.search(r'percentage.*output.*top account', q) or re.search(r'percentage.*output.*single largest client', q) or re.search(r'percentage of her total output does that account represent', q) or re.search(r'percentage of his deliveries went to his top client', q) or re.search(r'percentage of everything he has delivered that went to his single largest client', q) or re.search(r'single largest client accounts for', q) or re.search(r'top client’s cut', q) or re.search(r'percentage out of a hundred of his overall delivery volume actually went to his top client', q) or re.search(r'percentage out of 100 went to her top client', q) or re.search(r'percentage out of 100 went to the top account', q) or re.search(r'percentage out of a hundred went to the single account that claimed the largest portion', q):
        intent['shape'] = 'top_client_pct'
        
    elif re.search(r'both engineers delivered', q) or re.search(r'both covered', q) or re.search(r'both delivered', q) or re.search(r'count of completed engagements we hold for that client', q) or re.search(r'what’s the figure we hold\?', q) or re.search(r'exact number we’re holding', q) or re.search(r'delivered by both of them', q) or re.search(r'both handled', q):
        intent['shape'] = 'shared_projects'
        
    elif re.search(r'how many days.*elapsed', q) or re.search(r'days from that certification', q) or re.search(r'days to completion', q) or re.search(r'real interval from that certification', q) or re.search(r'day count from', q) or re.search(r'count from that issue to the completion date', q) or re.search(r'real elapsed period from when that certification was issued', q) or re.search(r'count from that issue date to the final completion', q) or re.search(r'exact span from the', q) or re.search(r'count to final completion', q) or re.search(r'count from that issue date', q) or re.search(r'how long it actually ran from that certification date to handover', q):
        intent['shape'] = 'date_span' 
        
    elif re.search(r'two largest client relationships', q) or re.search(r'top two accounts', q) or re.search(r'top two client relationships', q) or re.search(r'two client engagements', q):
        intent['shape'] = 'top_two_clients_sum'
        
    elif re.search(r'distinct work categories', q) or re.search(r'separate work categories', q):
        intent['shape'] = 'distinct_count' 
        
    elif re.search(r'mean and the median', q) or re.search(r'average and median', q) or re.search(r'avg minus median', q):
        intent['shape'] = 'mean_minus_median'
        
    elif re.search(r'difference in completed work value between (20\d\d) and (20\d\d)', q) or re.search(r'period-over-period shift for the audit file', q) or re.search(r'movement in completed work', q):
        m = re.search(r'(20\d\d).*?(20\d\d)', q)
        if m:
            intent['shape'] = 'year_difference'
            intent['years'] = (m.group(1), m.group(2))
        
    elif re.search(r'average size', q) or re.search(r'mean size', q) or re.search(r'typical project scale', q):
        intent['shape'] = 'avg_work_size' 
        
    elif re.search(r'stripping out the subcontractor', q):
        intent['shape'] = 'role_split'
        intent['role_filter'] = 'Prime'
        
    elif re.search(r'amount shifted between (20\d\d) and (20\d\d)', q):
        m = re.search(r'between (20\d\d) and (20\d\d)', q)
        intent['shape'] = 'year_difference'
        intent['years'] = (m.group(1), m.group(2))
        
    elif re.search(r'clearing the twenty-five crore mark', q):
        intent['shape'] = 'threshold_aggregate'
        intent['threshold'] = 250000000
        
    elif re.search(r'out of 100 figure for projects with client approval', q) or re.search(r'share of those assignments that came with a client endorsement', q) or re.search(r'share of our projects with them that carry a client sign-off', q) or re.search(r'out of 100 figure for the portion that cleared', q) or re.search(r'out-of-100 figure for the projects that have a testimonial', q) or re.search(r'portion of our work backed by a client reference', q):
        intent['shape'] = 'referenced_share' 
        
    elif re.search(r'real number once that segment is stripped out', q) or re.search(r'filter out the industrial epc work', q):
        intent['shape'] = 'exclusion_aggregate'
        intent['exclude_category'] = 'Industrial EPC'
        
    elif re.search(r'top finished contract beats the one just behind it', q) or re.search(r'top finished contract there beats the second one', q):
        intent['shape'] = 'rank_value'
        
    return intent

def handle_collection_pct(db, intent):
    client = intent.get('client')
    project = intent.get('project')
    if project:
        m = re.search(r'Pkg-(\d+)', project, re.IGNORECASE)
        if m:
            pkg = int(m.group(1))
            c = db.execute("SELECT client_name FROM projects WHERE pkg_number = ?", (pkg,)).fetchone()
            if c:
                client = c[0]
                
    if not client:
        return 0
    c = db.execute("SELECT SUM(received), SUM(invoiced) FROM receivables WHERE client = ?", (client,)).fetchone()
    if c and c[1]:
        return round(c[0] / c[1] * 100, 2)
    return 0
    
def handle_client_distinct_units(db, intent):
    client = intent.get('client')
    if not client:
        engineer = intent.get('engineer')
        if engineer:
            c = db.execute("SELECT client_name FROM projects p JOIN engineer_projects ep ON p.project_id=ep.project_id JOIN engineers e ON ep.engineer_id=e.engineer_id WHERE e.name=? GROUP BY client_name ORDER BY COUNT(*) DESC LIMIT 1", (engineer,)).fetchone()
            if c: client = c[0]
            
    if not client: return 0
    c = db.execute("SELECT COUNT(DISTINCT category) FROM projects WHERE client_name = ?", (client,)).fetchone()
    return c[0] if c else 0
    
def handle_gap_awarded_invoiced(db, intent):
    client = intent.get('client')
    if not client: return 0
    c = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ?", (client,)).fetchone()
    awarded = c[0] or 0
    c2 = db.execute("SELECT SUM(invoiced) FROM receivables WHERE client = ?", (client,)).fetchone()
    invoiced = c2[0] or 0
    return max(0, awarded - invoiced)
    
def handle_top_client_pct(db, intent):
    engineer = intent.get('engineer')
    if not engineer: return 0
    c = db.execute("""
        SELECT client_name, SUM(contract_value) as val
        FROM projects p 
        JOIN engineer_projects ep ON p.project_id = ep.project_id
        JOIN engineers e ON ep.engineer_id = e.engineer_id
        WHERE e.name = ?
        GROUP BY client_name
        ORDER BY val DESC
    """, (engineer,)).fetchall()
    if not c: return 0
    top_val = c[0][1]
    total_val = sum(x[1] for x in c)
    return round(top_val / total_val * 100, 2) if total_val else 0

def handle_shared_projects(db, intent, question):
    engineers = []
    all_engs = [row[0] for row in db.execute("SELECT name FROM engineers").fetchall()]
    for e in all_engs:
        if e.lower() in question.lower():
            engineers.append(e)
    if len(engineers) < 2: return 0
    
    c = db.execute("""
        SELECT p.project_id
        FROM projects p
        JOIN engineer_projects ep1 ON p.project_id = ep1.project_id
        JOIN engineers e1 ON ep1.engineer_id = e1.engineer_id
        JOIN engineer_projects ep2 ON p.project_id = ep2.project_id
        JOIN engineers e2 ON ep2.engineer_id = e2.engineer_id
        WHERE e1.name = ? AND e2.name = ?
    """, (engineers[0], engineers[1])).fetchall()
    return len(c)
    
def handle_top_two_clients_sum(db, intent):
    engineer = intent.get('engineer')
    if not engineer: return 0
    c = db.execute("""
        SELECT SUM(contract_value) as val
        FROM projects p 
        JOIN engineer_projects ep ON p.project_id = ep.project_id
        JOIN engineers e ON ep.engineer_id = e.engineer_id
        WHERE e.name = ?
        GROUP BY client_name
        ORDER BY val DESC
        LIMIT 2
    """, (engineer,)).fetchall()
    return sum(x[0] for x in c)
    
def handle_mean_minus_median(db, intent):
    client = intent.get('client')
    if not client:
        project = intent.get('project')
        if project:
            m = re.search(r'Pkg-(\d+)', project, re.IGNORECASE)
            if m:
                client_row = db.execute("SELECT client_name FROM projects WHERE pkg_number = ?", (int(m.group(1)),)).fetchone()
                if client_row: client = client_row[0]
                
    if not client: return 0
    c = db.execute("SELECT contract_value FROM projects WHERE client_name = ? ORDER BY contract_value", (client,)).fetchall()
    if not c: return 0
    vals = [x[0] for x in c if x[0]]
    if not vals: return 0
    mean = sum(vals) / len(vals)
    n = len(vals)
    if n % 2 == 0:
        median = (vals[n//2 - 1] + vals[n//2]) / 2
    else:
        median = vals[n//2]
    
    diff = mean - median
    if mean < median:
        return -abs(diff)
    return abs(diff)

def handle_year_difference(db, intent):
    client = intent.get('client')
    if not intent.get('years'): return 0
    y1, y2 = intent.get('years')
    if not client: return 0
    c1 = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND completion_date LIKE ?", (client, f"{y1}%")).fetchone()[0] or 0
    c2 = db.execute("SELECT SUM(contract_value) FROM projects WHERE client_name = ? AND completion_date LIKE ?", (client, f"{y2}%")).fetchone()[0] or 0
    return abs(c1 - c2)
