#!/usr/bin/env python3
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from extract import extract_xlsx


def test_workbook_formula_resolution(documents_dir):
    # Receivables Ageing is known to have SUM formulas
    path = os.path.join(documents_dir, 'workbooks/Receivables_Ageing.xlsx')
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
        
    res = extract_xlsx(path)
    sheet = res['sheets'].get('AR Ageing')
    assert sheet is not None, "AR Ageing sheet not found"
    
    assert sheet['formulas_found'] > 0, "Formulas should have been detected"
    assert sheet['formulas_resolved'] == sheet['formulas_found'], "All formulas should be resolved"
    assert sheet['formulas_unresolved'] == 0, "Should have no unresolved formulas"
