from pathlib import Path
import bittensor as bt
from dataclasses import dataclass
from typing import Optional

ROOT_DIR = Path(__file__).parent.parent
DECAY_RATE = 1
MIN_WEIGHT_THRESHOLD = 1e-6
DEFAULT_RAW_SCORE = 999
DEFAULT_NORMALIZED_SCORE = 0.0
DEFAULT_DUPLICATE_COUNT = 200



@dataclass
class Competition:
    """Class defining model parameters"""
    id: str = "1"
    repo: str = "flock-io/flock-off-s1-text-2-sql"
    bench: float = 0.16
    minb: float = 0.138
    maxb: float = 0.165
    bheight: float = 0.05
    pow: int = 2
    rows: int = 250

    @classmethod
    def from_defaults(cls) -> "Competition":
        """Return an instance with constant default values"""
        return cls()


# eval dataset huggingface
eval_commit = "f39608ce0921580ccea12cd31e60890797a15ba1"
