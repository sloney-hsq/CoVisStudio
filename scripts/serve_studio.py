"""Run the current studio with its explicitly selected local Qwen configuration."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.__main__ import main


if __name__ == '__main__':
    main()
