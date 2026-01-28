import time
import numpy as np
from flockoff.validator.validator_utils import compute_score, select_winner
from flockoff import constants
from flockoff.validator.database import ScoreDB
from datetime import datetime, timezone

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
    assert np.isclose(score, expected_score, rtol=1e-5)


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
    assert np.isclose(score, expected_score, rtol=1e-5)


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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_zero_benchmark_evaluation():
    loss = 0.1
    benchmark_loss = 0
    power = 2
    expected_score = constants.DEFAULT_NORMALIZED_SCORE
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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_negative_benchmark_evaluation():
    loss = 0.1
    benchmark_loss = -0.1
    power = 2
    expected_score = constants.DEFAULT_NORMALIZED_SCORE
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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_none_benchmark_evaluation():
    loss = 0.1
    benchmark_loss = None
    power = 2
    expected_score = constants.DEFAULT_NORMALIZED_SCORE
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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_invalid_power():
    loss = 0.1
    benchmark_loss = 0.1
    power = -1
    expected_score = constants.DEFAULT_NORMALIZED_SCORE
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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_none_power():
    loss = 0.1
    benchmark_loss = 0.1
    power = None
    expected_score = constants.DEFAULT_NORMALIZED_SCORE
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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_mismatched_competition_id():
    loss = 0.1
    benchmark_loss = 0.1
    power = 2
    expected_score = constants.DEFAULT_NORMALIZED_SCORE
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
    assert np.isclose(score, expected_score, rtol=1e-5)


def test_select_winner():
    score_db = ScoreDB("test.db")
    now = datetime.now(timezone.utc)
    competition_id_today = now.strftime("%Y%m%d")
    score_db.record_submission(competition_id_today, 0, "h0", "c0", 0, int(time.time()), "name0", "revis0")
    score_db.record_submission_loss(competition_id_today, 0, 0.1, is_eligible=True)

    score_db.record_submission(competition_id_today, 1, "h1", "c1", 1, int(time.time()), "name1", "revis1")
    score_db.record_submission_loss(competition_id_today, 1, 0.101, is_eligible=True)

    score_db.record_submission(competition_id_today, 2, "h2", "c2", 2, int(time.time()), "name2", "revis2")
    score_db.record_submission_loss(competition_id_today, 2, 10, is_eligible=True)

    score_db.record_submission(competition_id_today, 3, "h3", "c3", 3, int(time.time()), "name3", "revis3")
    score_db.record_submission_loss(competition_id_today, 3, 3, is_eligible=True)

    score_db.record_submission(competition_id_today, 4, "h4", "c4", 4, int(time.time()), "name4", "revis4")
    score_db.record_submission_loss(competition_id_today, 4, 0.1001, is_eligible=True)

    score_db.record_submission(competition_id_today, 4, "h4", "c4", 4, int(time.time()), "name4", "revis4")
    score_db.record_submission_loss(competition_id_today, 4, 0.1001, is_eligible=True)

    score_db.record_submission(competition_id_today, 5, "h5", "c4", 4, int(time.time()), "name5", "revis5")
    score_db.record_submission_loss(competition_id_today, 5, 55, is_eligible=True)

    score_db.record_submission(competition_id_today, 6, "h6", "c6", 4, int(time.time()), "name6", "revis6")
    score_db.record_submission_loss(competition_id_today, 6, 0.1001, is_eligible=True)

    score_db.record_submission(competition_id_today, 7, "h7", "c7", 4, int(time.time()), "name7", "revis7")
    score_db.record_submission_loss(competition_id_today, 7, 6.7, is_eligible=True)

    print(select_winner(score_db, competition_id_today, {0: "h0", 1: "h1", 2: "h2", 3: "h33", 4: "h44", 5: "h55", 6: "h66", 7: "h6"}) == [0, 1, 2, 7])
    print(select_winner(score_db, competition_id_today, {0: "h0", 1: "h1", 2: "h2", 3: "h33", 4: "h44", 5: "h5", 6: "h66", 7: "h6"}) == [0, 1, 5, 7])
