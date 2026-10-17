"""Keep the default test run offline and deterministic: no Gemma calls."""
import os
import sys
from pathlib import Path

os.environ["ENABLE_AI_EXPLANATION"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
