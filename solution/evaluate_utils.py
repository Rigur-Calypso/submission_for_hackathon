#!/usr/bin/env python3
"""evaluate_utils.py — Scoring helper extracted from evaluate.py for reuse."""


def score_one(gold, got):
    """Score a single answer. Returns 0.0 if the answer is missing or unparseable."""
    if got is None:
        return 0.0
    try:
        gold, got = float(gold), float(got)
    except (TypeError, ValueError):
        return 0.0
    if abs(gold) < 100:                               # counts and percentages
        if got == gold:
            return 1.0
        return 0.3 if abs(got - gold) <= 1 else 0.0
    err = abs(got - gold) / abs(gold)
    if err <= 0.005:
        return 1.0
    if err <= 0.02:
        return 0.7
    if err <= 0.10:
        return 0.3
    return 0.0
