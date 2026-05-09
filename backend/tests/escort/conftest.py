import sys
from pathlib import Path

# Add backend/escort/ to sys.path so 'from app.xxx import' resolves to escort's app.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "escort"))
