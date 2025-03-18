from pathlib import Path
from dataclasses import dataclass
from typing import List

# The uid for this subnet.
# testnet
SUBNET_UID = 257
# The start block of this subnet
ROOT_DIR = Path(__file__).parent.parent


@dataclass
class CompetitionParameters:
    """Class defining model parameters"""

    # Reward percentage
    reward_percentage: float
    # Competition id
    competition_id: str


COMPETITION_SCHEDULE: List[CompetitionParameters] = [
    CompetitionParameters(
        reward_percentage=1.0,
        competition_id="f127",
    ),
]
CONSTANT_ALPHA = 0.2  # enhance vtrust
timestamp_epsilon = 0.04  # enhance vtrust
temperature = 0.08

# validator weight moving average term. alpha = 1-lr.
lr = 0.2

ORIGINAL_COMPETITION_ID = "f127"

# eval dataset huggingface
eval_namespace = "xiaofengzi/flcok_test"
eval_commit = "main"
