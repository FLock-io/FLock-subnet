from pathlib import Path
from dataclasses import dataclass
from typing import Optional

ROOT_DIR = Path(__file__).parent.parent
DECAY_RATE = 1
MIN_WEIGHT_THRESHOLD = 1e-6
DEFAULT_RAW_SCORE = 999
DEFAULT_NORMALIZED_SCORE = 0.0
DEFAULT_DUPLICATE_COUNT = 33

SCORE_PRECISION = 10_000

SELECTION_SIZE = 100            # miners choose 100 rows
LOSS_THRESHOLD_PCT = 0.05

submission_start_utc_min = 12 * 60
submission_window_mins = 30
validate_start_utc_min = 12 * 60 + submission_window_mins
reward_start_utc_min = 11 * 60 + 30

@dataclass
class Competition:
    """Class defining model parameters"""
    id: str = "1"
    repo: str = "flock-io/flock-off-s1-competition"
    bench: float = 2.60
    minb: float = 2.40
    maxb: float = 2.80
    bheight: float = 0.05
    pow: int = 2
    rows: int = SELECTION_SIZE

    @classmethod
    def from_defaults(cls) -> "Competition":
        """Return an instance with constant default values"""
        return cls()


# eval dataset huggingface
eval_commit = "main"


