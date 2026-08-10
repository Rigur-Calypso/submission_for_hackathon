#!/usr/bin/env python3
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from extract import _best_text_for_fields, _extract_text_dual


def test_dual_extractor(documents_dir):
    # Use DOC-CC-001 as it's known to have missing pages in pdfplumber
    path = os.path.join(documents_dir, 'completion_certificate/DOC-CC-001.pdf')
    if not os.path.exists(path):
        pytest.skip(f"Test file not found: {path}")
        
    dual = _extract_text_dual(path)
    
    pypdf_text = dual['pypdf_text']
    plumber_text = dual['pdfplumber_text']
    
    # pypdf should recover significantly more text on multi-page certificates
    assert len(pypdf_text) > len(plumber_text) * 2, "pypdf did not recover expected text"
    
    # Check that best text logic works correctly for grading
    grading_labels = ['Quality Assessment', 'assessed', 'graded', 'Excellent',
                      'Very Good', 'Good', 'Satisfactory']
    best = _best_text_for_fields(dual, grading_labels)
    assert best == pypdf_text, "Should have chosen pypdf for grading fields"
    assert "Quality Assessment" in best, "Best text missing expected grading label"
