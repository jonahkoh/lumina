import inspect

from app.router import _render_dashboard, dashboard_data


def test_admin_past_trips_table_includes_trip_type_column():
    """Admin dashboard HTML must include trip_type in the past trips table headers."""
    html = _render_dashboard("admin", None)
    assert "trip_type" in html


def test_trip_type_labels_in_dashboard_html():
    """Dashboard HTML must map enum values to human-readable labels."""
    html = _render_dashboard("admin", None)
    assert "Driver only" in html
    assert "Escort only" in html
    assert "Driver + Escort" in html
