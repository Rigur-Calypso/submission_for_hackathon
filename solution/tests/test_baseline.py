#!/usr/bin/env python3
"""
test_baseline.py — Regression gate: all 25 sample questions must score 1.0.

This test runs the deterministic query engine (no LLM) against every sample
question and asserts a perfect score. It is the primary regression gate for
all subsequent changes.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from evaluate_utils import score_one
from query_engine import answer_question


class TestBaseline:
    """All 25 sample questions must score perfectly via deterministic engine."""

    def test_all_samples_score_perfectly(self, knowledge_db, sample_questions):
        """Every sample question must get score 1.0."""
        failures = []
        for q in sample_questions:
            res = answer_question(q['question'], knowledge_db)
            answer = res.value
            s = score_one(q['answer'], answer)
            if s < 1.0:
                failures.append(
                    f"{q['qid']} ({q.get('shape', '?')}): "
                    f"gold={q['answer']}, got={answer}, score={s}"
                )

        if failures:
            msg = f"{len(failures)}/{len(sample_questions)} questions failed:\n"
            msg += "\n".join(f"  {f}" for f in failures)
            pytest.fail(msg)

    @pytest.mark.parametrize("question_idx", range(25))
    def test_individual_sample(self, knowledge_db, sample_questions, question_idx):
        """Each sample question tested individually for clear failure reporting."""
        if question_idx >= len(sample_questions):
            pytest.skip("Question index out of range")

        q = sample_questions[question_idx]
        res = answer_question(q['question'], knowledge_db)
        answer = res.value
        s = score_one(q['answer'], answer)

        assert s == 1.0, (
            f"Q: {q['question'][:100]}...\n"
            f"  QID: {q['qid']}, Shape: {res.status.value}\n"
            f"  Gold: {q['answer']}, Got: {answer}, Score: {s}\n"
            f"  Status: {res.status}"
        )
