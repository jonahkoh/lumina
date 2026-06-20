import sys
from pathlib import Path

# Add backend/trip_audit/ to sys.path so 'from app.xxx import' resolves to trip_audit's app.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "trip_audit"))
