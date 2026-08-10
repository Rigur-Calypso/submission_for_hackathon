#!/usr/bin/env python3
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from currency import parse_indian_money, parse_threshold_words


def test_indian_money_parsing():
    # Test standard formats from the corpus
    assert parse_indian_money("INR 33.38 Cr") == 333800000
    assert parse_indian_money("Rs. 1403.00 Lakh") == 140300000
    assert parse_indian_money("Rs. 11.23 Crore") == 112300000
    assert parse_indian_money("33,38,00,000") == 333800000
    assert parse_indian_money("₹ 33.38 crore") == 333800000
    assert parse_indian_money("INR 200.00 Cr") == 2000000000
    assert parse_indian_money("Rs. -1,03,75,31,068") == -1037531068
    assert parse_indian_money("Rs. 18.26 Crore") == 182600000
    
    # Test precise Decimal evaluation (no floating point errors)
    # 2.01 * 10000000 in floats can sometimes be 20100000.000000004
    assert parse_indian_money("INR 2.01 Cr") == 20100000

def test_threshold_words():
    # Test word parser for thresholds
    assert parse_threshold_words("seventy-three crore") == 730000000
    assert parse_threshold_words("five hundred crore") == 5000000000
    assert parse_threshold_words("two lakh") == 200000
