#!/usr/bin/env python3
"""
conftest.py — Shared pytest fixtures for the BITS Hackathon solution tests.
"""
import json
import os
import sqlite3
import sys

import pytest

# Ensure solution dir is on the path
SOLUTION_DIR = os.path.join(os.path.dirname(__file__), '..')
PROJECT_ROOT = os.path.join(SOLUTION_DIR, '..')
sys.path.insert(0, os.path.abspath(SOLUTION_DIR))


@pytest.fixture(scope="session")
def solution_dir():
    """Absolute path to the solution/ directory."""
    return os.path.abspath(SOLUTION_DIR)


@pytest.fixture(scope="session")
def project_root():
    """Absolute path to the project root."""
    return os.path.abspath(PROJECT_ROOT)


@pytest.fixture(scope="session")
def documents_dir(project_root):
    """Absolute path to the documents/ directory."""
    return os.path.join(project_root, 'documents')


@pytest.fixture(scope="session")
def sample_questions(project_root):
    """Load the sample_questions.json as a list of question dicts."""
    path = os.path.join(project_root, 'sample_questions.json')
    with open(path) as f:
        data = json.load(f)
    return data['questions']


@pytest.fixture(scope="session")
def knowledge_db(solution_dir):
    """Connect to the built knowledge_graph.db (read-only).
    
    Requires the DB to exist — run build_kg.py first.
    """
    db_path = os.path.join(solution_dir, 'knowledge_graph.db')
    if not os.path.exists(db_path):
        pytest.skip("knowledge_graph.db not found — run build_kg.py first")
    db = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    yield db
    db.close()


@pytest.fixture
def fresh_db():
    """Create a fresh in-memory SQLite DB with the full schema.
    
    Useful for unit tests that need to insert controlled test data.
    """
    from build_kg import create_schema
    db = sqlite3.connect(":memory:")
    create_schema(db)
    yield db
    db.close()


@pytest.fixture(scope="session")
def document_index(project_root):
    """Load the document_index.csv and return a dict of {filename: doc_type}."""
    import csv
    index_path = os.path.join(project_root, 'document_index.csv')
    if not os.path.exists(index_path):
        pytest.skip("document_index.csv not found")
    result = {}
    with open(index_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            result[row.get('filename', row.get('file', ''))] = row
    return result
