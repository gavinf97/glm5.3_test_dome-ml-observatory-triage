"""Agreement and accuracy statistics for two raters, as plain functions over label lists.

Every function takes two equal-length sequences of labels (rater A, rater B) for the same items.
Undefined results (e.g. kappa when both raters used one category only) come back as NaN, never raise.
"""

from __future__ import annotations

import math
from typing import Callable, Sequence

import numpy as np
from scipy.stats import binomtest
from statsmodels.stats.proportion import proportion_confint


def _check(a: Sequence, b: Sequence) -> None:
    if len(a) != len(b):
        raise ValueError("the two raters must have the same number of labels")


def _table(a: Sequence, b: Sequence, categories: Sequence) -> np.ndarray:
    index = {c: i for i, c in enumerate(categories)}
    t = np.zeros((len(categories), len(categories)))
    for x, y in zip(a, b):
        t[index[x], index[y]] += 1
    return t


def _categories(a, b, categories=None) -> list:
    return list(categories) if categories is not None else sorted(set(a) | set(b), key=str)


def percent_agreement(a, b) -> float:
    _check(a, b)
    return float(np.mean([x == y for x, y in zip(a, b)])) if len(a) else math.nan


def cohen_kappa(a, b, categories=None) -> float:
    """Cohen's kappa (unweighted)."""
    _check(a, b)
    if not len(a):
        return math.nan
    cats = _categories(a, b, categories)
    t = _table(a, b, cats) / len(a)
    po = np.trace(t)
    pe = float(t.sum(1) @ t.sum(0))
    return math.nan if math.isclose(pe, 1.0) else float((po - pe) / (1 - pe))


def weighted_kappa(a, b, categories: Sequence, weights: str = "linear") -> float:
    """Weighted kappa for ordered categories (given low to high). weights: 'linear' or 'quadratic'."""
    _check(a, b)
    if not len(a):
        return math.nan
    k = len(categories)
    t = _table(a, b, categories) / len(a)
    i, j = np.meshgrid(range(k), range(k), indexing="ij")
    d = np.abs(i - j) if weights == "linear" else (i - j) ** 2
    w = d / d.max() if d.max() else d
    expected = np.outer(t.sum(1), t.sum(0))
    denom = float((w * expected).sum())
    return math.nan if math.isclose(denom, 0.0) else float(1 - (w * t).sum() / denom)


def gwet_ac1(a, b, categories=None) -> float:
    """Gwet's AC1. Stable when one category dominates (where kappa is pulled down by prevalence)."""
    _check(a, b)
    if not len(a):
        return math.nan
    cats = _categories(a, b, categories)
    q = len(cats)
    if q < 2:
        return math.nan
    t = _table(a, b, cats) / len(a)
    po = np.trace(t)
    pi = (t.sum(1) + t.sum(0)) / 2
    pe = float((pi * (1 - pi)).sum() / (q - 1))
    return math.nan if math.isclose(pe, 1.0) else float((po - pe) / (1 - pe))


def pabak(a, b, q: int = 2) -> float:
    """Prevalence- and bias-adjusted kappa: (q * po - 1) / (q - 1)."""
    po = percent_agreement(a, b)
    return math.nan if math.isnan(po) else (q * po - 1) / (q - 1)


def specific_agreement(a, b, positive=True) -> tuple[float, float]:
    """Positive and negative specific agreement for binary labels (positive = `positive`)."""
    _check(a, b)
    both_pos = sum(x == positive and y == positive for x, y in zip(a, b))
    both_neg = sum(x != positive and y != positive for x, y in zip(a, b))
    disc = len(a) - both_pos - both_neg
    pa = 2 * both_pos / (2 * both_pos + disc) if (2 * both_pos + disc) else math.nan
    na = 2 * both_neg / (2 * both_neg + disc) if (2 * both_neg + disc) else math.nan
    return pa, na


def mcnemar_exact(a, b, positive=True) -> float:
    """Exact McNemar p-value: does one rater call items positive more often than the other?"""
    _check(a, b)
    a_only = sum(x == positive and y != positive for x, y in zip(a, b))
    b_only = sum(x != positive and y == positive for x, y in zip(a, b))
    n = a_only + b_only
    return 1.0 if n == 0 else float(binomtest(a_only, n, 0.5).pvalue)


def wilson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    if n == 0:
        return math.nan, math.nan
    lo, hi = proportion_confint(k, n, alpha=alpha, method="wilson")
    return float(lo), float(hi)


def binom_p_greater(k: int, n: int, p0: float) -> float:
    """One-sided exact binomial p for H1: true rate > p0."""
    return math.nan if n == 0 else float(binomtest(k, n, p0, alternative="greater").pvalue)


def bootstrap_ci(stat: Callable, a: Sequence, b: Sequence, reps: int = 5000, seed: int = 0,
                 alpha: float = 0.05) -> tuple[float, float]:
    """Percentile bootstrap CI over items (each item is one paper's pair of labels)."""
    _check(a, b)
    n = len(a)
    if n < 2:
        return math.nan, math.nan
    rng = np.random.default_rng(seed)
    a, b = list(a), list(b)
    values = []
    for _ in range(reps):
        idx = rng.integers(0, n, n)
        v = stat([a[i] for i in idx], [b[i] for i in idx])
        if not math.isnan(v):
            values.append(v)
    if len(values) < reps * 0.5:
        return math.nan, math.nan
    lo, hi = np.percentile(values, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)
