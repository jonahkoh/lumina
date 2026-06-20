import sys
from pathlib import Path

# Add backend/driver/ to sys.path so 'from app.xxx import' resolves to driver's app.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "driver"))
