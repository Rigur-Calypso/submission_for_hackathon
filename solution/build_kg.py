#!/usr/bin/env python3
"""
build_kg.py — Build the SQLite Knowledge Graph from extracted data.

Takes the extracted_data.json and creates a normalized SQLite database
with entities, relationships, and cross-references.

Build is atomic: writes to a temporary file and replaces the target
only after all quality gates pass.
"""
import hashlib
import json
import os
import re
import sqlite3
import sys

from rapidfuzz import fuzz

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SOLUTION_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SOLUTION_DIR, 'knowledge_graph.db')
DATA_PATH = os.path.join(SOLUTION_DIR, 'extracted_data.json')

EXTRACTOR_VERSION = '2.0.0'


class BuildValidationError(Exception):
    """Raised when the built DB fails quality gates."""


def _log_error(db: sqlite3.Connection, source_file: str, step: str,
               error_message: str, error_type: str = 'parse_failure'):
    """Log an extraction error to the extraction_errors table."""
    db.execute(
        "INSERT INTO extraction_errors (source_file, step, error_message, error_type) "
        "VALUES (?, ?, ?, ?)",
        (source_file, step, str(error_message)[:2000], error_type)
    )


def create_schema(db: sqlite3.Connection):
    """Create the knowledge graph schema."""
    db.executescript('''
        DROP TABLE IF EXISTS projects;
        DROP TABLE IF EXISTS engineers;
        DROP TABLE IF EXISTS certifications;
        DROP TABLE IF EXISTS engineer_projects;
        DROP TABLE IF EXISTS reference_letters;
        DROP TABLE IF EXISTS documents;
        DROP TABLE IF EXISTS financial_data;
        DROP TABLE IF EXISTS boq_items;
        DROP TABLE IF EXISTS measurements;
        DROP TABLE IF EXISTS receivables;
        DROP TABLE IF EXISTS plant_register;
        DROP TABLE IF EXISTS trial_balance;
        DROP TABLE IF EXISTS documents_text;
        DROP TABLE IF EXISTS extraction_errors;
        DROP TABLE IF EXISTS source_documents;
        DROP TABLE IF EXISTS fact_provenance;
        DROP TABLE IF EXISTS cvs;
        DROP TABLE IF EXISTS financial_statements;
        DROP TABLE IF EXISTS final_ra_bills;
        DROP TABLE IF EXISTS ra_bills;
        DROP TABLE IF EXISTS bank_statements;
        DROP TABLE IF EXISTS ledger_entries;
        DROP TABLE IF EXISTS performance_bonds;
        DROP TABLE IF EXISTS compliance_matrix;
        DROP TABLE IF EXISTS tender_dossiers;
        DROP TABLE IF EXISTS iso_certificates;
        DROP TABLE IF EXISTS annual_reports;
        
        CREATE TABLE projects (
            project_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT NOT NULL,
            pkg_number INTEGER,               -- extracted from "Pkg-NNN"
            client_name TEXT,                  -- clean client name
            client_type TEXT,                  -- government, psu, private
            category TEXT,                     -- Bridges Flyovers, Buildings, etc.
            contract_value INTEGER,            -- in rupees
            completion_date TEXT,              -- ISO format YYYY-MM-DD
            grading TEXT,                      -- Excellent, Very Good, Good, Satisfactory
            role TEXT,                         -- Prime, Subcontractor, JV Partner
            project_lead TEXT,                 -- engineer who led
            project_lead_role TEXT,            -- Project Lead or Project Manager
            cc_ref TEXT,                       -- Certificate ref: CC/34/2011/001
            has_reference_letter INTEGER DEFAULT 0,  -- boolean
            source_ccc TEXT,                   -- source CCC filename
            source_cc TEXT                     -- source CC filename
        );
        
        CREATE TABLE engineers (
            engineer_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            employee_id TEXT                    -- EMP-001, EMP-004, etc.
        );
        
        CREATE TABLE certifications (
            cert_id TEXT PRIMARY KEY,           -- PMI-200006, 6S-500156
            engineer_id INTEGER,
            cert_type TEXT,                    -- PMP, Six Sigma Black Belt, Six Sigma Green Belt
            issuing_authority TEXT,            -- PMI, ASQ
            issue_date TEXT,                   -- ISO date
            valid_through TEXT,                -- ISO date
            source_file TEXT,
            FOREIGN KEY (engineer_id) REFERENCES engineers(engineer_id)
        );
        
        CREATE TABLE engineer_projects (
            engineer_id INTEGER,
            project_id INTEGER,
            role_in_project TEXT,              -- Project Lead, Project Manager
            PRIMARY KEY (engineer_id, project_id),
            FOREIGN KEY (engineer_id) REFERENCES engineers(engineer_id),
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        
        CREATE TABLE reference_letters (
            ref_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT,
            project_name TEXT,
            project_id INTEGER,
            contract_value INTEGER,
            issuing_authority TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(project_id)
        );
        
        -- Excel tables --
        
        CREATE TABLE boq_items (
            boq_id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_number INTEGER,
            item_no INTEGER,
            description TEXT,
            unit TEXT,
            quantity REAL,
            rate REAL,
            amount REAL
        );
        
        CREATE TABLE measurements (
            meas_id INTEGER PRIMARY KEY AUTOINCREMENT,
            contract_number INTEGER,
            ra_no INTEGER,
            measured_on TEXT,
            item_no INTEGER,
            description TEXT,
            qty_measured REAL,
            amount REAL
        );
        
        CREATE TABLE receivables (
            recv_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_no TEXT,
            client TEXT,
            invoice_date TEXT,
            invoiced REAL,
            status TEXT,
            received REAL,
            outstanding REAL
        );
        
        CREATE TABLE plant_register (
            asset_id INTEGER PRIMARY KEY,
            type TEXT,
            make TEXT,
            acquired INTEGER,
            cost REAL,
            condition TEXT,
            location TEXT,
            ownership TEXT,
            safety_certified INTEGER
        );
        
        CREATE TABLE trial_balance (
            tb_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fiscal_year TEXT,
            account TEXT,
            debit REAL,
            credit REAL,
            balance REAL
        );
        
        CREATE TABLE documents_text (
            doc_id TEXT PRIMARY KEY,
            doc_type TEXT,
            filename TEXT,
            full_text TEXT
        );
        
        -- Phase 4 Batch 1 Tables --
        CREATE TABLE cvs (
            cv_id INTEGER PRIMARY KEY AUTOINCREMENT,
            engineer_name TEXT,
            qualifications TEXT,
            experience_years INTEGER,
            specializations TEXT,
            projects_listed TEXT,
            source_file TEXT
        );
        
        CREATE TABLE financial_statements (
            fs_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fiscal_year TEXT,
            revenue REAL,
            expenses REAL,
            net_profit REAL,
            total_assets REAL,
            total_liabilities REAL,
            source_file TEXT
        );
        
        CREATE TABLE final_ra_bills (
            frb_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_ref TEXT,
            bill_amount REAL,
            deductions REAL,
            net_payable REAL,
            bill_date TEXT,
            source_file TEXT
        );
        
        CREATE TABLE ra_bills (
            rab_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_ref TEXT,
            ra_number INTEGER,
            measured_qty REAL,
            certified_amount REAL,
            source_file TEXT
        );
        
        CREATE TABLE bank_statements (
            bs_id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT,
            account_no TEXT,
            period_start TEXT,
            period_end TEXT,
            opening_bal REAL,
            closing_bal REAL,
            source_file TEXT
        );
        
        CREATE TABLE ledger_entries (
            le_id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            date TEXT,
            description TEXT,
            debit REAL,
            credit REAL,
            running_balance REAL,
            source_file TEXT
        );
        
        -- Phase 4 Batch 2 Tables --
        CREATE TABLE performance_bonds (
            pb_id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_name TEXT,
            bond_value REAL,
            issuing_bank TEXT,
            expiry_date TEXT,
            beneficiary TEXT,
            source_file TEXT
        );
        
        CREATE TABLE compliance_matrix (
            cm_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_ref TEXT,
            requirement TEXT,
            clause TEXT,
            compliance_status TEXT,
            evidence_ref TEXT,
            source_file TEXT
        );
        
        CREATE TABLE tender_dossiers (
            td_id INTEGER PRIMARY KEY AUTOINCREMENT,
            tender_ref TEXT,
            project_name TEXT,
            estimated_value REAL,
            submission_date TEXT,
            source_file TEXT
        );
        
        CREATE TABLE iso_certificates (
            iso_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cert_standard TEXT,
            cert_number TEXT,
            valid_from TEXT,
            valid_to TEXT,
            scope TEXT,
            source_file TEXT
        );
        
        CREATE TABLE annual_reports (
            ar_id INTEGER PRIMARY KEY AUTOINCREMENT,
            fiscal_year TEXT,
            revenue REAL,
            project_count INTEGER,
            employee_count INTEGER,
            highlights TEXT,
            source_file TEXT
        );
        
        -- Observability tables --
        
        CREATE TABLE extraction_errors (
            error_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            step TEXT NOT NULL,
            error_message TEXT,
            error_type TEXT DEFAULT 'parse_failure',
            timestamp TEXT DEFAULT (datetime('now'))
        );
        
        CREATE TABLE source_documents (
            doc_id TEXT PRIMARY KEY,
            doc_type TEXT NOT NULL,
            file_path TEXT,
            checksum_sha256 TEXT,
            page_count INTEGER,
            char_count_primary INTEGER,
            extractor_used TEXT DEFAULT 'pdfplumber',
            extraction_version TEXT
        );
        
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            doc_id,
            full_text,
            tokenize="unicode61"
        );
        
        CREATE TABLE fact_provenance (
            provenance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_type TEXT NOT NULL,
            entity_id INTEGER NOT NULL,
            field_name TEXT NOT NULL,
            source_document_id TEXT,
            page_number INTEGER,
            bounding_box TEXT,
            raw_text TEXT,
            normalized_value TEXT,
            extractor_version TEXT,
            confidence REAL DEFAULT 1.0,
            validation_status TEXT DEFAULT 'unverified',
            FOREIGN KEY (source_document_id) REFERENCES source_documents(doc_id)
        );
        
        CREATE INDEX idx_projects_client ON projects(client_name);
        CREATE INDEX idx_projects_category ON projects(category);
        CREATE INDEX idx_projects_lead ON projects(project_lead);
        CREATE INDEX idx_projects_grading ON projects(grading);
        CREATE INDEX idx_projects_role ON projects(role);
        CREATE INDEX idx_projects_pkg ON projects(pkg_number);
        CREATE INDEX idx_engineer_projects_eid ON engineer_projects(engineer_id);
        CREATE INDEX idx_engineer_projects_pid ON engineer_projects(project_id);
        CREATE INDEX idx_certifications_eid ON certifications(engineer_id);
        CREATE INDEX idx_boq_contract ON boq_items(contract_number);
        CREATE INDEX idx_meas_contract ON measurements(contract_number);
        CREATE INDEX idx_recv_client ON receivables(client);
        CREATE INDEX idx_recv_status ON receivables(status);
        CREATE INDEX idx_plant_type ON plant_register(type);
        CREATE INDEX idx_tb_year ON trial_balance(fiscal_year);
        CREATE INDEX idx_tb_account ON trial_balance(account);
        CREATE INDEX idx_prov_entity ON fact_provenance(entity_type, entity_id);
        CREATE INDEX idx_prov_source ON fact_provenance(source_document_id);
        CREATE INDEX idx_prov_status ON fact_provenance(validation_status);
        CREATE INDEX idx_errors_file ON extraction_errors(source_file);
        CREATE INDEX idx_errors_step ON extraction_errors(step);
    ''')


def extract_pkg_number(name: str) -> int | None:
    """Extract package number from project name like 'RCC Bridge — Gujarat Pkg-1'."""
    m = re.search(r'Pkg-(\d+)', name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def normalize_client_name(name: str) -> str:
    """Normalize a client name for consistent matching."""
    if not name:
        return ''
    # Remove type suffixes like (government), (psu), (Private)
    name = re.sub(r'\s*\([^)]*\)\s*$', '', name)
    # Normalize whitespace
    name = ' '.join(name.split())
    return name.strip()


def normalize_category(category: str) -> str:
    """Normalize category names for consistent matching."""
    if not category:
        return ''
    cat = category.strip().lower()
    
    # Common normalizations based on what we've seen in the data
    category_map = {
        'bridges flyovers': 'Bridges Flyovers',
        'bridges  flyovers': 'Bridges Flyovers',
        'buildings': 'Buildings',
        'small buildings': 'Small Buildings',
        'irrigation': 'Irrigation',
        'water treatment': 'Water Treatment',
        'water supply': 'Water Supply',
        'sewerage drainage': 'Sewerage Drainage',
        'expressways': 'Expressways',
        'roads highways': 'Roads Highways',
        'roads maintenance': 'Roads Maintenance',
        'tunnels': 'Tunnels',
        'large bridges': 'Large Bridges',
        'industrial epc': 'Industrial EPC',
    }
    
    return category_map.get(cat, category.strip().title())


def _file_sha256(filepath: str) -> str:
    """Compute SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def _populate_source_documents(db: sqlite3.Connection, base_dir: str):
    """Scan all document directories and register each file in source_documents."""
    base = os.path.abspath(base_dir)
    count = 0
    for doc_type in sorted(os.listdir(base)):
        type_dir = os.path.join(base, doc_type)
        if not os.path.isdir(type_dir):
            continue
        for fname in sorted(os.listdir(type_dir)):
            fpath = os.path.join(type_dir, fname)
            if not os.path.isfile(fpath):
                continue
            checksum = _file_sha256(fpath)
            page_count = None
            char_count = None
            extractor = 'none'
            if fname.endswith('.pdf'):
                extractor = 'pdfplumber'
                try:
                    import pdfplumber
                    with pdfplumber.open(fpath) as pdf:
                        page_count = len(pdf.pages)
                        text = ''
                        for page in pdf.pages:
                            text += (page.extract_text() or '')
                        char_count = len(text)
                except Exception:
                    pass
            elif fname.endswith('.xlsx'):
                extractor = 'openpyxl'
            db.execute(
                "INSERT OR REPLACE INTO source_documents "
                "(doc_id, doc_type, file_path, checksum_sha256, page_count, "
                "char_count_primary, extractor_used, extraction_version) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (fname, doc_type, fpath, checksum, page_count, char_count,
                 extractor, EXTRACTOR_VERSION)
            )
            count += 1
    db.commit()
    return count


def _paired_cc_filename(ccc_filename: str) -> str | None:
    """Return the client-certificate filename paired with a CCC filename.

    The corpus uses a shared, zero-padded document sequence for the two
    completion-certificate sets (``DOC-CCC-001.pdf`` ↔ ``DOC-CC-001.pdf``).
    This is a stronger join key than a fuzzy project-name comparison and also
    works when an extractor cannot read a certificate reference or project
    title from a layout-heavy PDF.
    """
    match = re.fullmatch(r'DOC-CCC-(\d{3})\.pdf', ccc_filename or '')
    return f"DOC-CC-{match.group(1)}.pdf" if match else None


def _record_fact_provenance(
    db: sqlite3.Connection,
    project_id: int,
    field_name: str,
    raw_value,
    source_document_id: str | None,
    *,
    page_number: int | None = None,
    confidence: float = 1.0,
    validation_status: str = 'parsed',
):
    """Record the source and normalized value of one project-level fact."""
    if raw_value is None or raw_value == '':
        return
    db.execute(
        """
        INSERT INTO fact_provenance (
            entity_type, entity_id, field_name, source_document_id, page_number, raw_text,
            normalized_value, extractor_version, confidence, validation_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            'project', project_id, field_name, source_document_id, page_number,
            str(raw_value), str(raw_value), EXTRACTOR_VERSION, confidence,
            validation_status,
        ),
    )


def _populate_project_provenance(db: sqlite3.Connection):
    """Create an auditable provenance record for every core project fact.

    Page coordinates are not yet retained by the extractors, but the source
    document, raw parsed value, version, and confidence are sufficient to
    trace an answer back to the corpus and to target manual verification.
    """
    db.execute("DELETE FROM fact_provenance WHERE entity_type = 'project'")
    project_rows = db.execute(
        """
        SELECT project_id, project_name, client_name, client_type, category,
               contract_value, completion_date, grading, role, project_lead,
               project_lead_role, cc_ref, has_reference_letter, source_ccc, source_cc
        FROM projects
        """
    ).fetchall()

    for row in project_rows:
        (
            project_id, project_name, client_name, client_type, category,
            contract_value, completion_date, grading, role, project_lead,
            project_lead_role, cc_ref, has_reference_letter, source_ccc, source_cc,
        ) = row

        for field_name, value in (
            ('project_name', project_name),
            ('client_name', client_name),
            ('client_type', client_type),
            ('category', category),
            ('contract_value', contract_value),
            ('completion_date', completion_date),
            ('project_lead', project_lead),
            ('project_lead_role', project_lead_role),
            ('cc_ref', cc_ref),
        ):
            _record_fact_provenance(
                db, project_id, field_name, value, source_ccc,
            )

        _record_fact_provenance(
            db, project_id, 'grading', grading, source_cc or source_ccc,
        )
        _record_fact_provenance(
            db, project_id, 'role', role, 'DOC-PPP-001.pdf',
        )

        ref_source = db.execute(
            "SELECT source_file FROM reference_letters WHERE project_id = ? LIMIT 1",
            (project_id,),
        ).fetchone()
        _record_fact_provenance(
            db,
            project_id,
            'has_reference_letter',
            has_reference_letter,
            ref_source[0] if ref_source else source_ccc,
            confidence=1.0 if has_reference_letter else 0.95,
            validation_status='matched' if has_reference_letter else 'derived_absence',
        )


EXPECTED_COUNTS = {
    'projects': 155,
    'engineers': None,  # derived
    'certifications': 48,
    'reference_letters': 132,
    'source_documents': 687,
    'cvs': 39,
    'financial_statements': 7,
    'final_ra_bills': 6,
    'ra_bills': 6,
    'bank_statements': 8,
    'ledger_entries': 8,
    'performance_bonds': 60,
    'compliance_matrix': 40,
    'tender_dossiers': 6,
    'iso_certificates': 5,
    'annual_reports': 2
}


def validate_build(db: sqlite3.Connection):
    """Run quality gates on the built DB. Raises BuildValidationError on failure."""
    # Expected counts derived from the actual corpus
    expected = EXPECTED_COUNTS
    errors = []
    for table, expected_count in expected.items():
        if expected_count is None: continue
        actual = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if actual < expected_count:
            errors.append(f"{table}: expected >= {expected_count}, got {actual}")
    
    # Check extraction errors aren't overwhelming
    error_count = db.execute("SELECT COUNT(*) FROM extraction_errors").fetchone()[0]
    project_count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    if project_count > 0 and error_count > project_count:
        errors.append(
            f"extraction_errors ({error_count}) exceeds project count ({project_count})"
        )

    # Add semantic quality gates:
    missing_ccc = db.execute(
        "SELECT COUNT(*) FROM projects WHERE source_ccc IS NULL OR source_ccc = ''"
    ).fetchone()[0]
    if missing_ccc:
        errors.append(f"projects missing source_ccc links: {missing_ccc}")
        
    missing_cc = db.execute(
        "SELECT COUNT(*) FROM projects WHERE source_cc IS NULL OR source_cc = ''"
    ).fetchone()[0]
    if missing_cc:
        errors.append(f"projects missing source_cc links: {missing_cc}")
        
    orphaned_joins = db.execute(
        "SELECT COUNT(*) FROM engineer_projects WHERE engineer_id NOT IN (SELECT engineer_id FROM engineers) OR project_id NOT IN (SELECT project_id FROM projects)"
    ).fetchone()[0]
    if orphaned_joins:
        errors.append(f"orphaned joins in engineer_projects: {orphaned_joins}")
        
    unmapped_refs = db.execute(
        "SELECT COUNT(*) FROM reference_letters WHERE project_id IS NULL"
    ).fetchone()[0]
    if unmapped_refs:
        errors.append(f"unmapped reference letters: {unmapped_refs}")
        
    gradings = db.execute("SELECT grading, COUNT(*) FROM projects GROUP BY grading").fetchall()
    gradings_dict = {g[0]: g[1] for g in gradings if g[0]}
    if not gradings_dict or sum(gradings_dict.values()) < 50:
        errors.append(f"unexpected grading distribution: {gradings_dict}")
        
    blank_text = db.execute(
        "SELECT COUNT(*) FROM documents_text WHERE full_text IS NULL OR trim(full_text) = ''"
    ).fetchone()[0]
    if blank_text:
        errors.append(f"documents with blank extracted text: {blank_text}")

    missing_value_provenance = db.execute(
        """
        SELECT COUNT(*)
        FROM projects p
        WHERE p.contract_value IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM fact_provenance fp
              WHERE fp.entity_type = 'project'
                AND fp.entity_id = p.project_id
                AND fp.field_name = 'contract_value'
          )
        """
    ).fetchone()[0]
    if missing_value_provenance:
        errors.append(
            f"projects missing contract-value provenance: {missing_value_provenance}"
        )
    
    if errors:
        raise BuildValidationError(
            "Build quality gates failed:\n" + "\n".join(f"  - {e}" for e in errors)
        )


def build_knowledge_graph():
    """Build the complete knowledge graph from extracted data.
    
    Build is atomic: writes to a temporary file and only replaces
    the target DB after all quality gates pass.
    """
    
    # Load extracted data
    with open(DATA_PATH) as f:
        data = json.load(f)
    
    # Build into temporary path for atomic replacement
    tmp_path = DB_PATH + '.building'
    # SQLite leaves sidecar files behind after an interrupted WAL build.  They
    # belong only to this disposable build target; reusing them can make
    # ``executescript`` fail with a misleading disk-I/O error on the next run.
    for stale_path in (tmp_path, tmp_path + '-wal', tmp_path + '-shm'):
        if os.path.exists(stale_path):
            os.remove(stale_path)
    db = sqlite3.connect(tmp_path)
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    
    create_schema(db)
    
    # ── Step 0: Register source documents ────────────────────────
    print("Step 0: Registering source documents...")
    base_dir = os.path.join(SOLUTION_DIR, '..', 'documents')
    doc_count = _populate_source_documents(db, base_dir)
    print(f"  Registered {doc_count} source documents")
    
    # ── Step 1: Insert projects from CCC ─────────────────────────
    print("Step 1: Building projects from CCC...")
    
    for ccc in data['ccc']:
        project_name = ccc.get('project_name', '')
        if not project_name:
            continue
        
        client_clean = normalize_client_name(
            ccc.get('client_clean') or ccc.get('client', '')
        )
        
        db.execute('''
            INSERT INTO projects (
                project_name, pkg_number, client_name, client_type,
                category, contract_value, completion_date, grading,
                project_lead, project_lead_role, cc_ref, source_ccc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            project_name,
            extract_pkg_number(project_name),
            client_clean,
            ccc.get('client_type', ''),
            normalize_category(ccc.get('category', '')),
            ccc.get('contract_value'),
            ccc.get('completion_date'),
            ccc.get('grading', ''),
            ccc.get('project_lead', ''),
            ccc.get('project_lead_role', ''),
            ccc.get('cc_ref', ''),
            ccc.get('source_file', ''),
        ))
    
    db.commit()
    project_count = db.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
    print(f"  Inserted {project_count} projects")
    
    # ── Step 2: Merge role info from PPP ─────────────────────────
    print("Step 2: Merging role info from PPP...")
    
    role_updated = 0
    for ppp in data.get('ppp', []):
        ppp_name = ppp.get('project_name', '')
        ppp_role = ppp.get('role', '')
        
        if not ppp_name or not ppp_role:
            continue
        
        # Find matching project by fuzzy name matching
        pkg_num = extract_pkg_number(ppp_name)
        
        if pkg_num is not None:
            # Try exact Pkg-N match first (most reliable)
            cursor = db.execute(
                "SELECT project_id, project_name FROM projects WHERE pkg_number = ?",
                (pkg_num,)
            )
            matches = cursor.fetchall()
            
            if len(matches) == 1:
                db.execute(
                    "UPDATE projects SET role = ? WHERE project_id = ?",
                    (ppp_role, matches[0][0])
                )
                role_updated += 1
            elif len(matches) > 1:
                # Multiple projects with same pkg number — use fuzzy matching
                best_match = None
                best_score = 0
                for pid, pname in matches:
                    score = fuzz.ratio(ppp_name.lower(), pname.lower())
                    if score > best_score:
                        best_score = score
                        best_match = pid
                if best_match and best_score > 70:
                    db.execute(
                        "UPDATE projects SET role = ? WHERE project_id = ?",
                        (ppp_role, best_match)
                    )
                    role_updated += 1
    
    db.commit()
    print(f"  Updated {role_updated} projects with role info")
    
    # ── Step 3: Link and merge client completion certificates ────
    print("Step 3: Linking and merging grading from CC...")
    
    grading_updated = 0
    cc_by_filename = {
        cc.get('source_file'): cc for cc in data.get('cc', [])
        if cc.get('source_file')
    }

    # The document-number pairing is complete even where the parsed CC has no
    # usable project title, reference number, or grading.  Save it first so
    # every project retains a direct evidence link to its client certificate.
    linked_cc_count = 0
    for project_id, source_ccc in db.execute(
        "SELECT project_id, source_ccc FROM projects"
    ).fetchall():
        paired_filename = _paired_cc_filename(source_ccc)
        if paired_filename and paired_filename in cc_by_filename:
            db.execute(
                "UPDATE projects SET source_cc = ? WHERE project_id = ?",
                (paired_filename, project_id),
            )
            linked_cc_count += 1

    for cc in data.get('cc', []):
        cc_grading = cc.get('grading', '')
        cc_ref = cc.get('cc_ref', '')
        
        # Match by CC ref
        if cc_ref:
            cursor = db.execute(
                "SELECT project_id, grading FROM projects WHERE cc_ref = ?",
                (cc_ref,)
            )
            match = cursor.fetchone()
            if match:
                db.execute(
                    "UPDATE projects SET source_cc = ? WHERE project_id = ?",
                    (cc.get('source_file', ''), match[0])
                )
                if cc_grading and not match[1]:  # Only fill a missing grade
                    db.execute(
                        "UPDATE projects SET grading = ? WHERE project_id = ?",
                        (cc_grading, match[0])
                    )
                    grading_updated += 1
                continue
        
        # Match by project name
        project_name = cc.get('project_name', '')
        if project_name:
            cursor = db.execute(
                "SELECT project_id, project_name, grading FROM projects"
            )
            all_projects = cursor.fetchall()
            best_match = None
            best_score = 0
            for pid, pname, existing_grading in all_projects:
                score = fuzz.ratio(project_name.lower(), pname.lower())
                if score > best_score:
                    best_score = score
                    best_match = (pid, existing_grading)
            
            if best_match and best_score > 80:
                db.execute(
                    "UPDATE projects SET source_cc = ? WHERE project_id = ?",
                    (cc.get('source_file', ''), best_match[0]),
                )
                if cc_grading and not best_match[1]:
                    db.execute(
                        "UPDATE projects SET grading = ? WHERE project_id = ?",
                        (cc_grading, best_match[0]),
                    )
                    grading_updated += 1
    
    db.commit()
    print(
        f"  Linked {linked_cc_count} client certificates; "
        f"updated {grading_updated} missing gradings"
    )
    
    # ── Step 4: Build engineer table ─────────────────────────────
    print("Step 4: Building engineers...")
    
    # Collect all engineer names from CCC project leads
    engineer_names = set()
    cursor = db.execute("SELECT DISTINCT project_lead FROM projects WHERE project_lead != ''")
    for row in cursor:
        engineer_names.add(row[0])
    
    # Also from personnel certs
    for pcert in data.get('pcert', []):
        name = pcert.get('engineer_name', '')
        if name:
            engineer_names.add(name)
    
    # Insert engineers
    for name in sorted(engineer_names):
        # Find employee ID from pcert
        emp_id = ''
        for pcert in data.get('pcert', []):
            if pcert.get('engineer_name', '') == name:
                emp_id = pcert.get('employee_id', '')
                break
        
        db.execute(
            "INSERT OR IGNORE INTO engineers (name, employee_id) VALUES (?, ?)",
            (name, emp_id)
        )
    
    db.commit()
    eng_count = db.execute("SELECT COUNT(*) FROM engineers").fetchone()[0]
    print(f"  Inserted {eng_count} engineers")
    
    # ── Step 5: Link engineers to projects ───────────────────────
    print("Step 5: Linking engineers to projects...")
    
    link_count = 0
    cursor = db.execute("SELECT project_id, project_lead, project_lead_role FROM projects WHERE project_lead != ''")
    for pid, lead_name, lead_role in cursor.fetchall():
        eng_cursor = db.execute("SELECT engineer_id FROM engineers WHERE name = ?", (lead_name,))
        eng = eng_cursor.fetchone()
        if eng:
            db.execute(
                "INSERT OR IGNORE INTO engineer_projects (engineer_id, project_id, role_in_project) VALUES (?, ?, ?)",
                (eng[0], pid, lead_role if lead_role else 'Project Lead')
            )
            link_count += 1
    
    db.commit()
    print(f"  Created {link_count} engineer-project links")
    
    # ── Step 6: Insert certifications ────────────────────────────
    print("Step 6: Inserting certifications...")
    
    cert_count = 0
    for pcert in data.get('pcert', []):
        cert_id = pcert.get('cert_id', '')
        engineer_name = pcert.get('engineer_name', '')
        
        if not cert_id or not engineer_name:
            continue
        
        # Find engineer ID
        eng_cursor = db.execute("SELECT engineer_id FROM engineers WHERE name = ?", (engineer_name,))
        eng = eng_cursor.fetchone()
        
        if eng:
            db.execute('''
                INSERT OR IGNORE INTO certifications (
                    cert_id, engineer_id, cert_type, issuing_authority,
                    issue_date, valid_through, source_file
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                cert_id,
                eng[0],
                pcert.get('cert_type', ''),
                pcert.get('issuing_authority', ''),
                pcert.get('issue_date', ''),
                pcert.get('valid_through', ''),
                pcert.get('source_file', ''),
            ))
            cert_count += 1
    
    db.commit()
    print(f"  Inserted {cert_count} certifications")
    
    # ── Step 7: Match reference letters to projects ──────────────
    print("Step 7: Matching reference letters...")
    
    ref_matched = 0
    ref_unmatched = 0
    
    # Get all project names for fuzzy matching
    cursor = db.execute("SELECT project_id, project_name FROM projects")
    all_projects = cursor.fetchall()
    {pid: pname for pid, pname in all_projects}
    
    for ref in data.get('ref', []):
        ref_project = ref.get('project_name', '')
        
        if not ref_project:
            ref_unmatched += 1
            continue
        
        # Fuzzy match to a project
        best_match = None
        best_score = 0
        for pid, pname in all_projects:
            score = fuzz.ratio(ref_project.lower(), pname.lower())
            if score > best_score:
                best_score = score
                best_match = pid
        
        matched_pid = None
        if best_match and best_score > 75:
            matched_pid = best_match
            ref_matched += 1
        else:
            # Try pkg number matching
            pkg_num = extract_pkg_number(ref_project)
            if pkg_num is not None:
                for pid, pname in all_projects:
                    if extract_pkg_number(pname) == pkg_num:
                        matched_pid = pid
                        ref_matched += 1
                        break
            if not matched_pid:
                ref_unmatched += 1
        
        db.execute('''
            INSERT INTO reference_letters (source_file, project_name, project_id, contract_value, issuing_authority)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            ref.get('source_file', ''),
            ref_project,
            matched_pid,
            ref.get('contract_value'),
            ref.get('issuing_authority', ''),
        ))
        
        # Mark project as having a reference letter
        if matched_pid:
            db.execute(
                "UPDATE projects SET has_reference_letter = 1 WHERE project_id = ?",
                (matched_pid,)
            )
    
    db.commit()
    print(f"  Matched {ref_matched}, unmatched {ref_unmatched}")
    
    # ── Step 8: Populate Excel data tables ───────────────────────
    print("\nStep 8: Loading Excel data...")
    
    boq_count = 0
    meas_count = 0
    for xlsx in data.get('xlsx', []):
        fname = xlsx.get('source_file', '')
        
        # BOQ + Measurements (Contract_71 through Contract_79)
        contract_match = re.search(r'Contract_(\d+)', fname)
        if contract_match:
            cnum = int(contract_match.group(1))
            
            # BOQ items
            if 'BOQ' in xlsx.get('sheets', {}):
                for row in xlsx['sheets']['BOQ'].get('data', []):
                    if not row or not isinstance(row[0], (int, float)):
                        continue
                    try:
                        db.execute("""
                            INSERT INTO boq_items (contract_number, item_no, description, unit, quantity, rate, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (cnum, int(row[0]), row[1], row[2], row[3], row[4], row[5] if len(row) > 5 else None))
                        boq_count += 1
                    except Exception as e:
                        _log_error(db, fname, 'boq_insert', str(e))
            
            # Measurements
            if 'Measurements' in xlsx.get('sheets', {}):
                for row in xlsx['sheets']['Measurements'].get('data', []):
                    if not row or not isinstance(row[0], (int, float)):
                        continue
                    try:
                        measured_on = str(row[1]).split(' ')[0] if row[1] else None
                        db.execute("""
                            INSERT INTO measurements (contract_number, ra_no, measured_on, item_no, description, qty_measured, amount)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (cnum, int(row[0]), measured_on, int(row[2]) if row[2] else None, row[3], row[4], row[5] if len(row) > 5 else None))
                        meas_count += 1
                    except Exception as e:
                        _log_error(db, fname, 'measurement_insert', str(e))
        
        # Receivables Ageing
        elif 'Ageing' in fname and 'AR Ageing' in xlsx.get('sheets', {}):
            ar_count = 0
            for row in xlsx['sheets']['AR Ageing'].get('data', []):
                if not row or not row[0]:
                    continue
                try:
                    db.execute("""
                        INSERT INTO receivables (invoice_no, client, invoice_date, invoiced, status, received, outstanding)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (str(row[0]), row[1], str(row[2]).split(' ')[0] if row[2] else None,
                          row[3], row[4], row[5], row[6]))
                    ar_count += 1
                except Exception as e:
                    _log_error(db, fname, 'receivable_insert', str(e))
            print(f"  Loaded {ar_count} receivable entries")
        
        # Plant & Machinery Register
        elif 'Plant' in fname and 'Plant Register' in xlsx.get('sheets', {}):
            pl_count = 0
            for row in xlsx['sheets']['Plant Register'].get('data', []):
                if not row or not isinstance(row[0], (int, float)):
                    continue
                try:
                    safety = 1 if (len(row) > 8 and row[8]) else 0
                    db.execute("""
                        INSERT OR IGNORE INTO plant_register (asset_id, type, make, acquired, cost, condition, location, ownership, safety_certified)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (int(row[0]), row[1], row[2], int(row[3]) if row[3] else None, row[4], row[5], row[6],
                          row[7] if len(row) > 7 else None, safety))
                    pl_count += 1
                except Exception as e:
                    _log_error(db, fname, 'plant_insert', str(e))
            print(f"  Loaded {pl_count} plant/equipment entries")
        
        # Trial Balance
        elif 'Trial' in fname:
            tb_count = 0
            for sheet_name, sheet_data in xlsx.get('sheets', {}).items():
                fy_match = re.search(r'TB\s+(\d{4}-\d{2})', sheet_name)
                if fy_match:
                    fy = fy_match.group(1)
                    for row in sheet_data.get('data', []):
                        if not row or not row[0]:
                            continue
                        try:
                            db.execute("""
                                INSERT INTO trial_balance (fiscal_year, account, debit, credit, balance)
                                VALUES (?, ?, ?, ?, ?)
                            """, (fy, str(row[0]), row[1], row[2], row[3]))
                            tb_count += 1
                        except Exception as e:
                            _log_error(db, fname, 'trial_balance_insert', str(e))
            print(f"  Loaded {tb_count} trial balance entries")
    
    if boq_count:
        print(f"  Loaded {boq_count} BOQ items, {meas_count} measurements")
        
    # ── Step 9: Load Phase 4 Batch 1 documents ──────────────────────
    print("\nStep 9: Loading Phase 4 Batch 1 Documents...")
    
    cv_count = 0
    for cv in data.get('cv', []):
        try:
            db.execute("""
                INSERT INTO cvs (engineer_name, qualifications, experience_years, specializations, projects_listed)
                VALUES (?, ?, ?, ?, ?)
            """, (cv.get('engineer_name'), cv.get('qualifications'), cv.get('experience_years'), cv.get('specializations'), cv.get('projects_listed')))
            cv_count += 1
        except Exception as e:
            _log_error(db, "cv_extract", 'cv_insert', str(e))
    print(f"  Loaded {cv_count} CVs")
    
    fs_count = 0
    for fs in data.get('financial_statement', []):
        try:
            db.execute("""
                INSERT INTO financial_statements (fiscal_year, revenue, expenses, net_profit, total_assets, total_liabilities)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (fs.get('fiscal_year'), fs.get('revenue'), fs.get('expenses'), fs.get('net_profit'), fs.get('total_assets'), fs.get('total_liabilities')))
            fs_count += 1
        except Exception as e:
            _log_error(db, "fs_extract", 'fs_insert', str(e))
    print(f"  Loaded {fs_count} Financial Statements")
    
    frab_count = 0
    for frab in data.get('final_ra_bill', []):
        try:
            db.execute("""
                INSERT INTO final_ra_bills (project_ref, bill_amount, deductions, net_payable, bill_date)
                VALUES (?, ?, ?, ?, ?)
            """, (frab.get('project_ref'), frab.get('bill_amount'), frab.get('deductions'), frab.get('net_payable'), frab.get('bill_date')))
            frab_count += 1
        except Exception as e:
            _log_error(db, "frab_extract", 'frab_insert', str(e))
    print(f"  Loaded {frab_count} Final RA Bills")
    
    rab_count = 0
    for rab in data.get('ra_bill', []):
        try:
            db.execute("""
                INSERT INTO ra_bills (project_ref, ra_number, measured_qty, certified_amount)
                VALUES (?, ?, ?, ?)
            """, (rab.get('project_ref'), rab.get('ra_number'), rab.get('measured_qty'), rab.get('certified_amount')))
            rab_count += 1
        except Exception as e:
            _log_error(db, "rab_extract", 'rab_insert', str(e))
    print(f"  Loaded {rab_count} RA Bills")
    
    bs_count = 0
    for bs in data.get('bank_statement', []):
        try:
            db.execute("""
                INSERT INTO bank_statements (bank_name, account_no, period_start, period_end, opening_bal, closing_bal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (bs.get('bank_name'), bs.get('account_no'), bs.get('period_start'), bs.get('period_end'), bs.get('opening_bal'), bs.get('closing_bal')))
            bs_count += 1
        except Exception as e:
            _log_error(db, "bs_extract", 'bs_insert', str(e))
    print(f"  Loaded {bs_count} Bank Statements")
    
    le_count = 0
    for le in data.get('general_ledger_book', []):
        try:
            db.execute("""
                INSERT INTO ledger_entries (account_name, date, description, debit, credit, running_balance)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (le.get('account_name'), le.get('date'), le.get('description'), le.get('debit'), le.get('credit'), le.get('running_balance')))
            le_count += 1
        except Exception as e:
            _log_error(db, "le_extract", 'le_insert', str(e))
    print(f"  Loaded {le_count} Ledger Entries")
    
    # ── Step 10: Load Phase 4 Batch 2 documents ──────────────────────
    print("\nStep 10: Loading Phase 4 Batch 2 Documents...")
    
    pb_count = 0
    for pb in data.get('performance_bond', []):
        try:
            db.execute("""
                INSERT INTO performance_bonds (project_name, bond_value, issuing_bank, expiry_date, beneficiary)
                VALUES (?, ?, ?, ?, ?)
            """, (pb.get('project_name'), pb.get('bond_value'), pb.get('issuing_bank'), pb.get('expiry_date'), pb.get('beneficiary')))
            pb_count += 1
        except Exception as e:
            _log_error(db, "pb_extract", 'pb_insert', str(e))
    print(f"  Loaded {pb_count} Performance Bonds")
    
    cm_count = 0
    for cm in data.get('compliance_matrix', []):
        try:
            db.execute("""
                INSERT INTO compliance_matrix (tender_ref, requirement, clause, compliance_status, evidence_ref)
                VALUES (?, ?, ?, ?, ?)
            """, (cm.get('tender_ref'), cm.get('requirement'), cm.get('clause'), cm.get('compliance_status'), cm.get('evidence_ref')))
            cm_count += 1
        except Exception as e:
            _log_error(db, "cm_extract", 'cm_insert', str(e))
    print(f"  Loaded {cm_count} Compliance Matrix rows")
    
    td_count = 0
    for td in data.get('tender_dossier', []):
        try:
            db.execute("""
                INSERT INTO tender_dossiers (tender_ref, project_name, estimated_value, submission_date)
                VALUES (?, ?, ?, ?)
            """, (td.get('tender_ref'), td.get('project_name'), td.get('estimated_value'), td.get('submission_date')))
            td_count += 1
        except Exception as e:
            _log_error(db, "td_extract", 'td_insert', str(e))
    print(f"  Loaded {td_count} Tender Dossiers")
    
    iso_count = 0
    for iso in data.get('iso_certificate', []):
        try:
            db.execute("""
                INSERT INTO iso_certificates (cert_standard, cert_number, valid_from, valid_to, scope)
                VALUES (?, ?, ?, ?, ?)
            """, (iso.get('cert_standard'), iso.get('cert_number'), iso.get('valid_from'), iso.get('valid_to'), iso.get('scope')))
            iso_count += 1
        except Exception as e:
            _log_error(db, "iso_extract", 'iso_insert', str(e))
    print(f"  Loaded {iso_count} ISO Certificates")
    
    ar_count = 0
    for ar in data.get('annual_report', []):
        try:
            db.execute("""
                INSERT INTO annual_reports (fiscal_year, revenue, project_count, employee_count, highlights)
                VALUES (?, ?, ?, ?, ?)
            """, (ar.get('fiscal_year'), ar.get('revenue'), ar.get('project_count'), ar.get('employee_count'), ar.get('highlights')))
            ar_count += 1
        except Exception as e:
            _log_error(db, "ar_extract", 'ar_insert', str(e))
    print(f"  Loaded {ar_count} Annual Reports")
    
    # ── Step 11: Load documents text ──────────────────────────────
    print("\nStep 11: Loading documents text...")
    text_count = 0
    for doc in data.get('documents_text', []):
        try:
            db.execute("""
                INSERT OR REPLACE INTO documents_text (doc_id, doc_type, filename, full_text)
                VALUES (?, ?, ?, ?)
            """, (doc['filename'], doc['doc_type'], doc['filename'], doc['full_text']))
            
            db.execute("""
                INSERT OR REPLACE INTO documents_fts (doc_id, full_text)
                VALUES (?, ?)
            """, (doc['filename'], doc['full_text']))
            text_count += 1
        except Exception as e:
            _log_error(db, doc.get('filename', 'unknown'), 'documents_text_insert', str(e))
    print(f"  Loaded {text_count} documents text")

    # ── Step 12: Record project fact provenance ──────────────────
    print("\nStep 12: Recording project fact provenance...")
    _populate_project_provenance(db)
    provenance_count = db.execute(
        "SELECT COUNT(*) FROM fact_provenance WHERE entity_type = 'project'"
    ).fetchone()[0]
    print(f"  Recorded {provenance_count} project fact records")

    # ── Step 13: Reconcile contract values ───────────────────────
    print("\nStep 13: Reconciling contract values...")
    cursor = db.execute('''
        SELECT p.project_id, p.contract_value, r.contract_value
        FROM projects p
        JOIN reference_letters r ON p.project_id = r.project_id
        WHERE p.contract_value IS NOT NULL AND r.contract_value IS NOT NULL
    ''')
    reconciled_count = 0
    for pid, p_val, r_val in cursor.fetchall():
        if p_val != r_val and abs(p_val - r_val) < 1000000:  # Within 10 Lakhs (e.g. 2008200000 vs 2008199999)
            # The one with fewer trailing zeros is more exact
            def exactness(v): return len(str(int(v)).rstrip('0'))
            if exactness(r_val) > exactness(p_val):
                db.execute("UPDATE projects SET contract_value = ? WHERE project_id = ?", (r_val, pid))
                reconciled_count += 1
            elif exactness(p_val) > exactness(r_val):
                # p_val is already more exact, keep it
                pass
    print(f"  Reconciled {reconciled_count} contract values with independent documents")

    db.commit()
    
    # ── Final Report ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("KNOWLEDGE GRAPH BUILD REPORT")
    print("=" * 60)
    
    stats = {
        'projects': db.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
        'with_value': db.execute("SELECT COUNT(*) FROM projects WHERE contract_value IS NOT NULL").fetchone()[0],
        'with_grading': db.execute("SELECT COUNT(*) FROM projects WHERE grading != ''").fetchone()[0],
        'with_role': db.execute("SELECT COUNT(*) FROM projects WHERE role != ''").fetchone()[0],
        'with_ref': db.execute("SELECT COUNT(*) FROM projects WHERE has_reference_letter = 1").fetchone()[0],
        'engineers': db.execute("SELECT COUNT(*) FROM engineers").fetchone()[0],
        'certifications': db.execute("SELECT COUNT(*) FROM certifications").fetchone()[0],
        'eng_proj_links': db.execute("SELECT COUNT(*) FROM engineer_projects").fetchone()[0],
        'ref_letters': db.execute("SELECT COUNT(*) FROM reference_letters").fetchone()[0],
        'source_documents': db.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0],
        'extraction_errors': db.execute("SELECT COUNT(*) FROM extraction_errors").fetchone()[0],
        'fact_provenance': db.execute("SELECT COUNT(*) FROM fact_provenance").fetchone()[0],
    }
    
    for k, v in stats.items():
        print(f"  {k:20s}: {v}")
    
    # Check coverage
    no_value = db.execute("SELECT project_name FROM projects WHERE contract_value IS NULL").fetchall()
    if no_value:
        print("\n  ⚠️ Projects missing contract_value:")
        for row in no_value[:5]:
            print(f"    - {row[0]}")
        if len(no_value) > 5:
            print(f"    ... and {len(no_value)-5} more")
    
    no_grading = db.execute("SELECT COUNT(*) FROM projects WHERE grading = '' OR grading IS NULL").fetchone()[0]
    print(f"\n  Projects missing grading: {no_grading}/155")

    missing_client_cc = db.execute(
        "SELECT COUNT(*) FROM projects WHERE source_cc IS NULL OR source_cc = ''"
    ).fetchone()[0]
    print(f"  Projects missing client certificate link: {missing_client_cc}/155")
    
    # Distribution
    print("\n  Grading distribution:")
    for row in db.execute("SELECT grading, COUNT(*) FROM projects GROUP BY grading ORDER BY COUNT(*) DESC"):
        print(f"    {row[0] or '(missing)':15s}: {row[1]}")
    
    print("\n  Role distribution:")
    for row in db.execute("SELECT role, COUNT(*) FROM projects GROUP BY role ORDER BY COUNT(*) DESC"):
        print(f"    {row[0] or '(missing)':15s}: {row[1]}")
    
    print("\n  Top clients by project count:")
    for row in db.execute("""
        SELECT client_name, COUNT(*), SUM(contract_value) 
        FROM projects GROUP BY client_name 
        ORDER BY COUNT(*) DESC LIMIT 10
    """):
        val_str = f"₹{row[2]/1e7:.0f} Cr" if row[2] else "N/A"
        print(f"    {row[0]:45s}: {row[1]:3d} projects, {val_str}")
    
    # Show extraction errors summary
    error_count = stats['extraction_errors']
    if error_count > 0:
        print("\n  ⚠️ Extraction errors by step:")
        for row in db.execute(
            "SELECT step, COUNT(*) FROM extraction_errors GROUP BY step ORDER BY COUNT(*) DESC LIMIT 10"
        ):
            print(f"    {row[0]:30s}: {row[1]}")
    
    # ── Quality gates ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("QUALITY GATES")
    print("=" * 60)
    try:
        validate_build(db)
        print("  ✅ All quality gates passed")
    except BuildValidationError as e:
        print(f"  ❌ {e}")
        db.close()
        # Clean up temp file on validation failure
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise
    
    # ── Atomic replacement ───────────────────────────────────────
    # Checkpoint WAL before replacing
    db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    db.close()
    
    # Atomic same-filesystem replacement
    os.replace(tmp_path, DB_PATH)
    
    print(f"\n✅ Database atomically saved to {DB_PATH}")
    print(f"   Size: {os.path.getsize(DB_PATH):,} bytes")


if __name__ == '__main__':
    build_knowledge_graph()
