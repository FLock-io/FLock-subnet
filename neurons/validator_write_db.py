import torch
import bittensor as bt
from flockoff.validator.database import ScoreDB
from datetime import datetime, timezone, timedelta


score_db = ScoreDB("scores.db")

now = datetime.now(timezone.utc)
competition_id_today = now.strftime("%Y%m%d")
competition_id_yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")

netuid = 96
subtensor = bt.subtensor()
metagraph = subtensor.metagraph(netuid)
new_weights = torch.zeros_like(torch.tensor(metagraph.S), dtype=torch.float32)
winner = score_db.get_competition_winner(competition_id_yesterday)
if winner:
    new_weights[winner] = 1

score_db.set_state("active_competition_id", competition_id_today)
score_db.set_state("reward_competition_id", competition_id_yesterday)
score_db.set_state("use_yesterday_reward", True)
score_db.set_state("weights", new_weights.tolist())

