#!/usr/bin/env python3
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from extract import extract_ppp, normalize_project_name


def test_normalize_project_name():
    # Should not touch acronyms or standard formatted names
    assert normalize_project_name("WTP — Gujarat Pkg-10") == "WTP — Gujarat Pkg-10"
    assert normalize_project_name("rCC BridGe — maharashtra PkG-50") == "RCC Bridge — Maharashtra Pkg-50"
    assert normalize_project_name("drainaGe Works — GUJarat PkG-135") == "Drainage Works — Gujarat Pkg-135"
    assert normalize_project_name("Some Standard Name") == "Some Standard Name"

def test_ppp_extraction(documents_dir):
    path = os.path.join(documents_dir, 'past_performance_portfolio/DOC-PPP-001.pdf')
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
        
    projects = extract_ppp(path)
    assert len(projects) == 155, f"Expected 155 projects, got {len(projects)}"
    
    ranks = [p['ppp_rank'] for p in projects]
    assert len(set(ranks)) == 155, "Ranks should be unique 1 to 155"
    assert min(ranks) == 1
    assert max(ranks) == 155
    
    # Check that rank 114 was found (had issues with JV Partner newline)
    p114 = next((p for p in projects if p['ppp_rank'] == 114), None)
    assert p114 is not None, "Rank 114 is missing"
    assert p114['role'] == 'JV Partner'
