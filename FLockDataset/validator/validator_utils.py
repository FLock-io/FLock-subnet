
import bittensor as bt
import numpy as np
import typing
from FLockDataset import constants
from scipy import optimize


def iswin(loss_i, loss_j, block_i, block_j):
    loss_i = (1 - constants.timestamp_epsilon) * loss_i if block_i < block_j else loss_i
    loss_j = (1 - constants.timestamp_epsilon) * loss_j if block_j < block_i else loss_j
    return loss_i < loss_j


def compute_wins(
        uids: typing.List[int],
        scores_per_uid: typing.Dict,
        block: typing.Dict,
):
    blacklist_uids = []
    for i, uid_i in enumerate(uids):
        if uid_i in blacklist_uids:
            continue
        if scores_per_uid[uid_i] == 0:
            blacklist_uids.append(uid_i)
            continue

    whitelist_uids = [uid for uid in uids if uid not in blacklist_uids]

    wins = {uid: 0 for uid in uids}
    win_rate_1 = {uid: 0 for uid in uids}
    for i, uid_i in enumerate(whitelist_uids):
        total_matches = 0
        block_i = block[uid_i]
        for j, uid_j in enumerate(whitelist_uids):
            if i == j:
                continue
            block_j = block[uid_j]

            scores_i = scores_per_uid[uid_i]
            scores_j = scores_per_uid[uid_j]
            wins[uid_i] += 1 if iswin(scores_i, scores_j, block_i, block_j) else 0
            total_matches += 1
        # Calculate win rate for uid i
        win_rate_1[uid_i] = wins[uid_i] / total_matches if total_matches > 0 else 0

    weights = [(win_rate_1, 1)]
    weights_sum = sum([w for _, w in weights])
    weights = [(winrate_dict, weight / weights_sum) for winrate_dict, weight in weights]
    win_rate = {uid: sum([win_rate_dict[uid] * weight for win_rate_dict, weight in weights]) for uid in uids}
    return wins, win_rate


def adjust_for_vtrust(weights: np.ndarray, consensus: np.ndarray, vtrust_min: float = 0.5):
    """
    Interpolate between the current weight and the normalized consensus weights so that the
    vtrust does not fall below vturst_min, assuming the consensus does not change.
    """
    vtrust_loss_desired = 1 - vtrust_min

    # If the predicted vtrust is already above vtrust_min, then just return the current weights.
    orig_vtrust_loss = np.maximum(0.0, weights - consensus).sum()
    if orig_vtrust_loss <= vtrust_loss_desired:
        bt.logging.info("Weights already satisfy vtrust_min. {} >= {}.".format(1 - orig_vtrust_loss, vtrust_min))
        return weights

    # If maximum vtrust allowable by the current consensus is less that vtrust_min, then choose the smallest lambda
    # that still maximizes the predicted vtrust. Otherwise, find lambda that achieves vtrust_min.
    vtrust_loss_min = 1 - np.sum(consensus)
    if vtrust_loss_min > vtrust_loss_desired:
        bt.logging.info(
            "Maximum possible vtrust with current consensus is less than vtrust_min. {} < {}.".format(
                1 - vtrust_loss_min, vtrust_min
            )
        )
        vtrust_loss_desired = 1.05 * vtrust_loss_min

    # We could solve this with a LP, but just do rootfinding with scipy.
    consensus_normalized = consensus / np.sum(consensus)

    def fn(lam: float):
        new_weights = (1 - lam) * weights + lam * consensus_normalized
        vtrust_loss = np.maximum(0.0, new_weights - consensus).sum()
        return vtrust_loss - vtrust_loss_desired

    sol = optimize.root_scalar(fn, bracket=[0, 1], method="brentq")
    lam_opt = sol.root

    new_weights = (1 - lam_opt) * weights + lam_opt * consensus_normalized
    vtrust_pred = np.minimum(weights, consensus).sum()
    bt.logging.info("Interpolated weights to satisfy vtrust_min. {} -> {}.".format(1 - orig_vtrust_loss, vtrust_pred))
    return new_weights


class EvalQueue:
    """Class for managing the order and frequency of evaluating models.

    Evaluation is split into epochs, where each epoch validates some subset of all the models using the same seed.
    Importantly, the weights are only updated at the end of each epoch.

    Each epoch, a total of 32 models are evaluated. Of these 32, we pick
    - The top 8 models based on the current weights.
    - 16 models randomly sampled with probability proportional to their current rank.
    - The 8 models that have not been evaluated for the longest time.
      This guarantees that each model will be evaluated at least once every 32 epochs.

    Except for the first epoch, where we evaluate all models to get some estimaate of how they perform.
    """

    def __init__(self, weights: np.ndarray):
        self.n_models = len(weights)
        self._weights = weights
        self.rng = np.random.default_rng()
        self.age_queue = self.rng.choice(self.n_models, self.n_models, replace=False).tolist()
        self.seed, self.queue = self._get_shuffled_init()
        self.epochs = 0

    @property
    def epoch_is_done(self):
        return len(self.queue) == 0

    def update_weights(self, weights: np.ndarray):
        self._weights = weights

    def _select_model(self, uid: int):
        """Place it at the end of the age_queue."""
        self.age_queue.remove(uid)
        self.age_queue.append(uid)

    def _get_shuffled_init(self) -> tuple[int, list]:
        seed = self.rng.integers(0, 2 ** 16)
        return seed, self.rng.choice(self.n_models, self.n_models, replace=False).tolist()

    def _get_shuffled(self) -> tuple[int, list]:
        # Sample random seed.
        seed = self.rng.integers(0, 2 ** 16)

        # Top 8 models based on the current weights.
        idxs = np.argsort(self._weights)[::-1]
        top_8 = idxs[:8]
        is_top_8 = np.zeros(self.n_models, dtype=bool)
        is_top_8[top_8] = True
        for uid in top_8:
            self._select_model(uid)

        # 16 models randomly sampled with probability using their current rank.
        ranks = np.zeros(self.n_models)
        ranks[idxs] = np.arange(self.n_models)
        probs = np.exp(-ranks / 32)
        #    Don't sample the top 8.
        probs[is_top_8] = 0
        probs /= probs.sum()
        random_16 = self.rng.choice(self.n_models, 16, p=probs, replace=False)
        for uid in random_16:
            self._select_model(uid)

        # The 8 models that have not been evaluated for the longest time.
        age_8 = self.age_queue[:8]
        for uid in age_8:
            self._select_model(uid)

        uids = top_8.tolist() + random_16.tolist() + age_8
        return seed, uids

    def take(self, n: int):
        uids = []
        # Don't start a new epoch in the middle.
        if len(self.queue) > 0:
            n = min(n, len(self.queue))

        for _ in range(n):
            _, uid = self.next()
            uids.append(uid)
        return uids

    def take_all(self):
        return self.take(len(self.queue))

    def next(self):
        if len(self.queue) == 0:
            self.seed, self.queue = self._get_shuffled()
            self.epochs += 1
        return self.seed, self.queue.pop()
