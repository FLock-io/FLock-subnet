import bittensor as bt
import numpy as np
from flockoff import constants


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
        return constants.DEFAULT_SCORE

    if real_comp_id is None:
        bt.logging.error(
            f"Invalid real_comp_id ({real_comp_id}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if miner_comp_id != real_comp_id:
        bt.logging.error(
            f"Miner commitment ID ({miner_comp_id}) does not match real commitment ID ({real_comp_id}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if benchmark_loss is None or benchmark_loss <= 0:
        bt.logging.error(
            f"Invalid benchmark_loss ({benchmark_loss}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if min_bench is None or max_bench is None:
        bt.logging.error(
            f"Invalid min_bench ({min_bench}) or max_bench ({max_bench}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if min_bench >= max_bench:
        bt.logging.error(
            f"Invalid min_bench ({min_bench}) >= max_bench ({max_bench}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

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
