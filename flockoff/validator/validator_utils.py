import json
from typing import Tuple, Any

import bittensor as bt
import numpy as np
from flockoff import constants
from flockoff.validator.database import ScoreDB


def compute_score(
        loss,
        benchmark_loss,
        min_bench,
        max_bench,
        power,
        bench_height,
        miner_comp_id,
        real_comp_id,
):
    """
    Compute the score based on the loss and benchmark loss.

    Args:
        loss: The loss value to evaluate
        benchmark_loss: The benchmark loss to compare against
        power: The steepness of the function


    Returns:
        float: Score value between 0 and 1
    """
    if loss is None:
        bt.logging.warning("Loss is None, returning score of 0")
        return 0

    if power is None or power <= 0:
        bt.logging.warning("Power is None or negative, returning score of 0")
        return constants.DEFAULT_NORMALIZED_SCORE

    if real_comp_id is None:
        bt.logging.error(
            f"Invalid real_comp_id ({real_comp_id}). Returning baseline score."
        )
        return constants.DEFAULT_NORMALIZED_SCORE

    if miner_comp_id != real_comp_id:
        bt.logging.error(
            f"Miner commitment ID ({miner_comp_id}) does not match real commitment ID ({real_comp_id}). Returning baseline score."
        )
        return constants.DEFAULT_NORMALIZED_SCORE

    if benchmark_loss is None or benchmark_loss <= 0:
        bt.logging.error(
            f"Invalid benchmark_loss ({benchmark_loss}). Returning baseline score."
        )
        return constants.DEFAULT_NORMALIZED_SCORE

    if min_bench is None or max_bench is None:
        bt.logging.error(
            f"Invalid min_bench ({min_bench}) or max_bench ({max_bench}). Returning baseline score."
        )
        return constants.DEFAULT_NORMALIZED_SCORE

    if min_bench >= max_bench:
        bt.logging.error(
            f"Invalid min_bench ({min_bench}) >= max_bench ({max_bench}). Returning baseline score."
        )
        return constants.DEFAULT_NORMALIZED_SCORE

    if loss < min_bench:
        return 1.0
    if loss > max_bench:
        return 0.0

    # For values between min_bench and benchmark_loss:
    # Calculate a score that decreases from 1.0 at min_bench to bench_height at benchmark_loss
    if min_bench <= loss <= benchmark_loss:
        numerator = (1 - bench_height) * np.pow(loss - benchmark_loss, power)
        denominator = np.pow((min_bench - benchmark_loss), power)
        return numerator / denominator + bench_height

    # For values between benchmark_loss and max_bench:
    # Calculate a score that decreases from bench_height at benchmark_loss to 0.0 at max_bench
    if benchmark_loss <= loss <= max_bench:
        numerator = -(bench_height) * np.pow(loss - benchmark_loss, power)
        denominator = np.pow((max_bench - benchmark_loss), power)
        return numerator / denominator + bench_height


def select_winner(db: ScoreDB, competition_id: str, hotkeys: dict, coldkeys: dict) -> tuple[None, None] | tuple[int, float]:
    subs = db.get_competition_submissions(competition_id)
    scored = [s for s in subs.values() if s.get('eval_loss') is not None]
    if not scored:
        return None, None

    threshold_number = max(int(len(hotkeys) * constants.LOSS_THRESHOLD_PCT), 1)
    scored_by_loss = sorted(scored, key=lambda s: s['eval_loss'])
    eligible = scored_by_loss[:threshold_number]

    if not eligible:
        return None, None

    def sort_key(s):
        return (s.get('commitment_block', 10 ** 18), s.get('commitment_timestamp', 10 ** 18))

    eligible_sorted = sorted(eligible, key=sort_key)
    bt.logging.info(f"competition_id:{competition_id} , eligible_sorted:{eligible_sorted}")
    winner = eligible_sorted[0]

    uid = winner['uid']
    if winner['hotkey'] != hotkeys[uid]:
        replacement_found = False
        for hotkey_uid, hotkey in hotkeys.items():
            if hotkey == winner['hotkey']:
                winner['uid'] = hotkey_uid
                replacement_found = True
            if replacement_found:
                bt.logging.info(f"{competition_id} competition_id winner found in hotkeys :{hotkey_uid}")
                return winner['uid'], winner['eval_loss']

        for coldkey_uid, coldkey in coldkeys.items():
            if coldkey == winner['coldkey']:
                winner['uid'] = coldkey_uid
                replacement_found = True
            if replacement_found:
                bt.logging.info(f"{competition_id} competition_id winner found in coldkeys :{coldkey_uid}")
                return winner['uid'], winner['eval_loss']

        if not replacement_found:
            for candidate in eligible_sorted:
                candidate_uid = candidate['uid']
                if candidate_uid != uid and hotkeys[candidate_uid] == candidate['hotkey']:
                    winner['uid'] = candidate_uid
                    bt.logging.info(f"{competition_id} competition_id winner found in eligible_sorted :{candidate_uid}")
                    return winner['uid'], winner['eval_loss']

            for candidate in scored_by_loss:
                candidate_uid = candidate['uid']
                if candidate_uid != uid and hotkeys[candidate_uid] == candidate['hotkey']:
                    winner['uid'] = candidate_uid
                    bt.logging.info(f"{competition_id} competition_id winner found in scored_by_loss :{candidate_uid}")
                    break

    return winner['uid'], winner['eval_loss']


def load_jsonl(path, max_rows=None):
    with open(path, 'r', encoding='utf-8') as f:
        data = [json.loads(line.strip()) for line in f if line.strip()]
        if max_rows is not None:
            data = data[:max_rows]
        return data


def count_similar(jsonl1, jsonl2):
    set1 = set(json.dumps(item, sort_keys=True) for item in jsonl1)
    set2 = set(json.dumps(item, sort_keys=True) for item in jsonl2)
    return len(set1 & set2)
