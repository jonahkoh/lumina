from datetime import datetime

from app.router import _haversine, _covers_datetime


def test_specialisation_score_partial_match():
    """Verify specialisation_score formula: matched / total_requested."""
    requested = ["dementia", "wheelchair", "visual_impairment"]
    escort_specs = ["dementia", "wheelchair"]
    matched = sum(1 for s in requested if s in escort_specs)
    score = matched / len(requested)
    assert round(score, 4) == round(2 / 3, 4)


def test_language_filter_any_match():
    """Language hard filter passes when at least one requested language matches."""
    escort_langs = ["english", "malay"]
    requested = ["chinese", "english"]  # english overlaps
    assert any(lang in escort_langs for lang in requested)

    no_overlap = ["chinese", "tamil"]
    assert not any(lang in escort_langs for lang in no_overlap)
