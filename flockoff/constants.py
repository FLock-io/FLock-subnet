from pathlib import Path
import bittensor as bt
from dataclasses import dataclass
from typing import Optional

ROOT_DIR = Path(__file__).parent.parent
DECAY_RATE = 1
MIN_WEIGHT_THRESHOLD = 1e-6
DEFAULT_SCORE = 0.0


def get_subnet_owner(is_testnet: bool = False) -> str:
    """
    Returns the subnet owner based on whether it's a testnet or mainnet.
    """
    if is_testnet:
        return "5Cex1UGEN6GZBcSBkWXtrerQ6Zb7h8eD7oSe9eDyZmj4doWu"
    else:
        return "5DFcEniKrQRbCakLFGY3UqPL3ZbNnTQHp8LTvLfipWhE2Yfr"


@dataclass
class Competition:
    """Class defining model parameters"""

    id: str
    repo: str
    bench: float
    minb: float
    maxb: float
    bheight: float
    pow: int
    rows: int

    @classmethod
    def from_dict(cls, data: dict) -> Optional["Competition"]:
        """Create a ChainCommitment from a dictionary"""
        if not data:
            return None

        try:
            id_val = str(data.get("id", ""))
            repo_val = str(data.get("repo", ""))
            bench_val = float(data.get("bench", 0.0))
            minb_val = float(data.get("minb", 0.0))
            maxb_val = float(data.get("maxb", 0.0))
            bheight_val = float(data.get("bheight", 0.0))
            rows_val = int(data.get("rows", 250))
            pow_val = int(data.get("pow", 0))
            return cls(
                id=id_val,
                repo=repo_val,
                bench=bench_val,
                rows=rows_val,
                pow=pow_val,
                minb=minb_val,
                maxb=maxb_val,
                bheight=bheight_val,
            )
        except (TypeError, ValueError) as e:
            bt.logging.warning(f"Failed to parse Competition from dict: {e}")
            return None


# eval dataset huggingface
eval_commit = "main"
