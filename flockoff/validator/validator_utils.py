import bittensor as bt
from flockoff import constants


def compute_score(loss, benchmark_loss, power, miner_comp_id, real_comp_id):
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
    if power is None:
        bt.logging.warning("Power is None, returning score of 0")
        return constants.DEFAULT_SCORE

    if miner_comp_id is None or real_comp_id is None:
        bt.logging.error(
            f"Invalid miner_comp_id ({miner_comp_id}) or real_comp_id ({real_comp_id}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if miner_comp_id != real_comp_id:
        bt.logging.error(
            f"Miner commitment ID ({miner_comp_id}) does not match real commitment ID ({real_comp_id}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if power % 2 != 0 or power < 0:
        bt.logging.error(
            f"Power must be a positive even number. Got {power}. Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    if benchmark_loss is None or benchmark_loss <= 0:
        bt.logging.error(
            f"Invalid benchmark_loss ({benchmark_loss}). Returning baseline score."
        )
        return constants.DEFAULT_SCORE

    center_point = get_center_point(power, benchmark_loss)
    score = 1 / (1 + center_point * loss**power)
    return score


def get_center_point(power, benchmark_loss):
    """
    Get the center point for the sigmoid function.

    Args:
        power: The steepness of the function
        benchmark_loss: The benchmark loss to compare against
    """
    a = (power - 1) / (power + 1) * (1 / benchmark_loss) ** power
    return a
