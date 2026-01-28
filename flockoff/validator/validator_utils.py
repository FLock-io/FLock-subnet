import json
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


def select_winner(db: ScoreDB, competition_id: str, hotkeys: dict) -> list | None:
    subs = db.get_competition_submissions(competition_id)
    scored = [s for s in subs.values() if s.get('eval_loss') is not None]
    if not scored:
        return None

    losses = {s['uid']: s['eval_loss'] for s in scored}
    L_min = min(losses.values())
    threshold = L_min * (1.0 + constants.LOSS_THRESHOLD_PCT)

    eligible = [s for s in scored if s['eval_loss'] <= threshold]
    if not eligible:
        return None

    def sort_key(s):
        return (s.get('commitment_block', 10 ** 18), s.get('commitment_timestamp', 10 ** 18))

    eligible_sorted = sorted(eligible, key=sort_key)
    scored_by_loss = sorted(scored, key=lambda s: s['eval_loss'])
    winners = [s['uid'] for s in eligible_sorted]

    for s in eligible_sorted:
        uid = s['uid']
        if s['hotkey'] != hotkeys[uid]:
            coldkey_replace = s['coldkey']
            winners.remove(uid)
            replacement_found = False
            for hotkey_uid, hotkey in hotkeys.items():
                if hotkey == s['hotkey']:
                    winners.append(hotkey_uid)
                    replacement_found = True
            if replacement_found:
                continue
            for candidate in scored_by_loss:
                candidate_uid = candidate['uid']
                if candidate['coldkey'] == coldkey_replace and candidate_uid != uid and \
                        candidate_uid not in winners and hotkeys[candidate_uid] == subs[candidate_uid]["hotkey"]:
                    winners.append(candidate_uid)
                    replacement_found = True
                    break
            if not replacement_found:
                for candidate in scored_by_loss:
                    candidate_uid = candidate['uid']
                    if candidate_uid not in winners and candidate_uid != uid and hotkeys[candidate_uid]==subs[candidate_uid]["hotkey"]:
                        winners.append(candidate_uid)
                        break

    return winners


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
