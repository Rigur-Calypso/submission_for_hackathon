#!/usr/bin/env python3
"""Scoring helper kept exactly in sync with the official evaluator."""


def score_one(gold, got):
    """Score a single answer. Returns 0.0 if the answer is missing or unparseable."""
    if got is None:
        return 0.0
    try:
        gold, got = float(gold), float(got)
    except (TypeError, ValueError):
        return 0.0
    if gold == 0:
        return 1.0 if got == 0 else 0.0
    return max(0.0, 1.0 - abs(got - gold) / abs(gold))
