#!/usr/bin/env python3
"""
test_build.py — Tests for the knowledge graph build process.

Validates that the build produces the expected observability tables,
quality gates, and document coverage.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestSchemaIntegrity:
    """Verify all required tables exist in the built DB."""

    REQUIRED_TABLES = [
        'projects', 'engineers', 'certifications', 'engineer_projects',
        'reference_letters', 'boq_items', 'measurements', 'receivables',
        'plant_register', 'trial_balance', 'documents_text',
        # Observability tables (Phase 1 additions)
        'extraction_errors', 'source_documents', 'fact_provenance',
    ]

    @pytest.mark.parametrize("table_name", REQUIRED_TABLES)
    def test_table_exists(self, knowledge_db, table_name):
        """Each required table must exist in the built DB."""
        cursor = knowledge_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        row = cursor.fetchone()
        assert row is not None, f"Table '{table_name}' missing from knowledge_graph.db"


class TestSourceDocuments:
    """Verify the source_documents manifest is populated correctly."""

    def test_source_documents_populated(self, knowledge_db):
        """source_documents should contain entries for all corpus files."""
        count = knowledge_db.execute(
            "SELECT COUNT(*) FROM source_documents"
        ).fetchone()[0]
        # 687 total documents in the corpus
        assert count >= 680, (
            f"source_documents has {count} entries, expected ~687"
        )

    def test_all_doc_types_present(self, knowledge_db):
        """All document types from the corpus should be represented."""
        types = [
            row[0] for row in knowledge_db.execute(
                "SELECT DISTINCT doc_type FROM source_documents"
            ).fetchall()
        ]
        expected_types = {
            'company_completion_certificate', 'completion_certificate',
            'reference_letter', 'personnel_certificate',
            'past_performance_portfolio', 'performance_bond',
            'cv', 'workbooks',
        }
        for t in expected_types:
            assert t in types, f"Document type '{t}' missing from source_documents"

    def test_checksums_populated(self, knowledge_db):
        """Every source document should have a SHA-256 checksum."""
        missing = knowledge_db.execute(
            "SELECT COUNT(*) FROM source_documents WHERE checksum_sha256 IS NULL"
        ).fetchone()[0]
        assert missing == 0, f"{missing} documents have no checksum"


class TestExtractionErrors:
    """Verify the extraction_errors table exists and is functional."""

    def test_extraction_errors_table_exists(self, knowledge_db):
        """The extraction_errors table should exist."""
        cursor = knowledge_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='extraction_errors'"
        )
        assert cursor.fetchone() is not None

    def test_errors_have_required_fields(self, knowledge_db):
        """If there are errors, they should have all required fields."""
        count = knowledge_db.execute(
            "SELECT COUNT(*) FROM extraction_errors"
        ).fetchone()[0]
        if count > 0:
            # Check no NULL required fields
            nulls = knowledge_db.execute(
                "SELECT COUNT(*) FROM extraction_errors "
                "WHERE source_file IS NULL OR step IS NULL"
            ).fetchone()[0]
            assert nulls == 0, f"{nulls} extraction errors have NULL required fields"


class TestQualityGates:
    """Verify that quality gate thresholds are met."""

    def test_project_count(self, knowledge_db):
        """Must have at least 155 projects (from 155 CCC documents)."""
        count = knowledge_db.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]
        assert count >= 155, f"Only {count} projects, expected >= 155"

    def test_reference_letter_count(self, knowledge_db):
        """Must have at least 130 reference letters (from 132 documents)."""
        count = knowledge_db.execute(
            "SELECT COUNT(*) FROM reference_letters"
        ).fetchone()[0]
        assert count >= 130, f"Only {count} reference letters, expected >= 130"

    def test_projects_have_values(self, knowledge_db):
        """Most projects should have contract values."""
        total = knowledge_db.execute(
            "SELECT COUNT(*) FROM projects"
        ).fetchone()[0]
        with_value = knowledge_db.execute(
            "SELECT COUNT(*) FROM projects WHERE contract_value IS NOT NULL"
        ).fetchone()[0]
        ratio = with_value / max(total, 1)
        assert ratio >= 0.95, (
            f"Only {with_value}/{total} projects have contract values ({ratio:.0%})"
        )

    def test_projects_have_clients(self, knowledge_db):
        """All projects should have client names."""
        missing = knowledge_db.execute(
            "SELECT COUNT(*) FROM projects "
            "WHERE client_name IS NULL OR client_name = ''"
        ).fetchone()[0]
        assert missing == 0, f"{missing} projects have no client name"

    def test_every_project_links_to_client_certificate(self, knowledge_db):
        """Each CCC has a paired client completion certificate in this corpus."""
        missing = knowledge_db.execute(
            "SELECT COUNT(*) FROM projects WHERE source_cc IS NULL OR source_cc = ''"
        ).fetchone()[0]
        assert missing == 0, f"{missing} projects have no client certificate link"

    def test_contract_values_have_provenance(self, knowledge_db):
        """Every parsed project value must be traceable to a source document."""
        missing = knowledge_db.execute(
            """
            SELECT COUNT(*)
            FROM projects p
            WHERE p.contract_value IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1 FROM fact_provenance fp
                  WHERE fp.entity_type = 'project'
                    AND fp.entity_id = p.project_id
                    AND fp.field_name = 'contract_value'
                    AND fp.source_document_id IS NOT NULL
              )
            """
        ).fetchone()[0]
        assert missing == 0, f"{missing} project values lack provenance"
