"""
matcher.py — Fuzzy product matcher using difflib + token overlap.

Given a user's normalised query string and a list of ProductResult objects
from a scraper, finds the best matching product and returns a confidence score.

No ML model, no external API — pure Python standard library.
"""

from difflib import SequenceMatcher
from typing import List, Optional, Tuple

from scrapers.base_scraper import ProductResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tokenise(text: str) -> set:
    """Lowercase, strip punctuation, split into tokens."""
    import re
    tokens = re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()
    return set(tokens)


def _sequence_ratio(a: str, b: str) -> float:
    """SequenceMatcher ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _token_overlap(a: str, b: str) -> float:
    """
    Jaccard similarity of token sets.
    Returns 0.0 if both sets are empty.
    """
    ta, tb = _tokenise(a), _tokenise(b)
    if not ta and not tb:
        return 0.0
    intersection = ta & tb
    union = ta | tb
    return len(intersection) / len(union)


def _combined_score(query: str, candidate: str) -> float:
    """
    Weighted combination of sequence ratio and token overlap.
    Weights tuned to work well on grocery product names.
    """
    seq  = _sequence_ratio(query, candidate)
    tok  = _token_overlap(query, candidate)
    return 0.45 * seq + 0.55 * tok


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

# Minimum confidence to consider a match valid
MIN_CONFIDENCE = 0.25


def best_match(
    query: str,
    candidates: List[ProductResult],
) -> Tuple[Optional[ProductResult], float]:
    """
    Find the best matching ProductResult for a query string.

    Parameters
    ----------
    query      : normalised product query (e.g. "Milk" or "Amul Milk")
    candidates : list of ProductResult objects from a scraper

    Returns
    -------
    (best_result, confidence)  where confidence ∈ [0, 1].
    If no candidate exceeds MIN_CONFIDENCE, returns (None, 0.0).
    """
    if not candidates:
        return None, 0.0

    best: Optional[ProductResult] = None
    best_score = 0.0

    for product in candidates:
        score = _combined_score(query, product.name)
        if score > best_score:
            best_score = score
            best = product

    if best_score < MIN_CONFIDENCE:
        return None, 0.0

    return best, round(best_score, 4)


def build_query(brand: Optional[str], name: str) -> str:
    """Build a search query string from a normalised GroceryItem."""
    parts = [p for p in (brand, name) if p]
    return " ".join(parts)
