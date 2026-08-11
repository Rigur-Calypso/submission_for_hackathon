"""Keep local regression scoring identical to evaluate.py."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from evaluate_utils import score_one


def test_official_proportional_scoring():
    assert score_one(1_000_000_000, 1_000_000_000) == 1.0
    assert score_one(1_000_000_000, 1_050_000_000) == 0.95
    assert score_one(1_000_000_000, 1_500_000_000) == 0.5
    assert score_one(1_000_000_000, 2_000_000_000) == 0.0


def test_zero_gold_matches_official_scoring():
    assert score_one(0, 0) == 1.0
    assert score_one(0, 1) == 0.0
