#!/usr/bin/env python3
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from extract import extract_pcert


def test_pcert_table_extraction(documents_dir):
    # A certificate with a table layout
    path = os.path.join(documents_dir, 'personnel_certificate/DOC-PCERT-006.pdf')
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
        
    res = extract_pcert(path)
    assert res.get('cert_id'), "Table layout cert_id not extracted"
    assert res.get('engineer_name'), "Table layout engineer_name not extracted"

def test_pcert_prose_extraction(documents_dir):
    # A certificate with a prose layout (DOC-PCERT-009)
    path = os.path.join(documents_dir, 'personnel_certificate/DOC-PCERT-009.pdf')
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
        
    res = extract_pcert(path)
    assert res.get('cert_id') == 'PMI-200009', "Prose layout cert_id not extracted properly"
    assert res.get('engineer_name') == 'Amit Iyer', "Prose layout engineer_name not extracted properly"
    assert res.get('cert_type') == 'PMP'
