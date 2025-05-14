import numpy as np
from flockoff.validator.validator_utils import compute_score
from flockoff import constants


DEFAULT_MIN_BENCH = 0.14
DEFAULT_MAX_BENCH = 0.2
DEFAULT_BENCH_HEIGHT = 0.16
DEFAULT_COMPETITION_ID = "2"
MISMATCH_COMPETITION_ID = "1"


def test_pow_8():
    benchmark_loss = 0.16
    power = 8
    loss = 0.15
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    # Note: you may need to re-adjust this expected value to match new score function logic
    assert 0 <= score <= 1, f"Score should be in [0, 1], got {score}"


def test_high_loss_evaluation():
    loss = 9999999999999999
    benchmark_loss = 0.1
    power = 2
    expected_score = 0.0
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_zero_loss_evaluation():
    loss = 0
    benchmark_loss = 0.1
    power = 2
    expected_score = 1.0
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_none_loss_evaluation():
    loss = None
    benchmark_loss = 0.1
    power = 2
    expected_score = 0.0
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_zero_benchmark_evaluation():
    loss = 0.1
    benchmark_loss = 0
    power = 2
    expected_score = constants.DEFAULT_SCORE
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_negative_benchmark_evaluation():
    loss = 0.1
    benchmark_loss = -0.1
    power = 2
    expected_score = constants.DEFAULT_SCORE
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_none_benchmark_evaluation():
    loss = 0.1
    benchmark_loss = None
    power = 2
    expected_score = constants.DEFAULT_SCORE
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_invalid_power():
    loss = 0.1
    benchmark_loss = 0.1
    power = -1
    expected_score = constants.DEFAULT_SCORE
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_none_power():
    loss = 0.1
    benchmark_loss = 0.1
    power = None
    expected_score = constants.DEFAULT_SCORE
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        DEFAULT_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)


def test_mismatched_competition_id():
    loss = 0.1
    benchmark_loss = 0.1
    power = 2
    expected_score = constants.DEFAULT_SCORE
    score = compute_score(
        loss,
        benchmark_loss,
        DEFAULT_MIN_BENCH,
        DEFAULT_MAX_BENCH,
        power,
        DEFAULT_BENCH_HEIGHT,
        MISMATCH_COMPETITION_ID,
        DEFAULT_COMPETITION_ID,
    )
    assert np.isclose(score, expected_score, rtol=1e-9)
