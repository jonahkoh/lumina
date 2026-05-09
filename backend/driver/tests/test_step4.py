from app.schemas import CompleteBody, RejectBody


def test_reject_body_reason_optional():
    """RejectBody accepts a missing reason without error."""
    body = RejectBody()
    assert body.reason is None

    body_with = RejectBody(reason="driver unavailable")
    assert body_with.reason == "driver unavailable"


def test_complete_body_requires_both_fields():
    """CompleteBody rejects missing required fields."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        CompleteBody(photo_url="https://example.com/photo.jpg")  # missing dropoff_confirmed

    valid = CompleteBody(photo_url="https://example.com/photo.jpg", dropoff_confirmed=True)
    assert valid.dropoff_confirmed is True
