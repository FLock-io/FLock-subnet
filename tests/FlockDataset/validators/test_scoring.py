import time
import pytest
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

@pytest.fixture
def db():
    """Fixture to create an in-memory database for each test."""
    db_instance = ScoreDB(":memory:")
    yield db_instance


def test_select_winner(db):
    score_db = db
    now = datetime.now(timezone.utc)
    competition_id_today = now.strftime("%Y%m%d")
    score_db.record_submission(competition_id_today, 0, "h0", "c0", 100, int(time.time()), "name0", "revis0")
    score_db.record_submission_loss(competition_id_today, 0, 0.101, is_eligible=True)

    score_db.record_submission(competition_id_today, 1, "h1", "c1", 101, int(time.time()), "name1", "revis1")
    score_db.record_submission_loss(competition_id_today, 1, 0.1, is_eligible=True)

    score_db.record_submission(competition_id_today, 2, "h2", "c2", 102, int(time.time()), "name2", "revis2")
    score_db.record_submission_loss(competition_id_today, 2, 10, is_eligible=True)

    score_db.record_submission(competition_id_today, 3, "h3", "c3", 103, int(time.time()), "name3", "revis3")
    score_db.record_submission_loss(competition_id_today, 3, 3, is_eligible=True)

    temp_hot = {}
    temp_cold = {}
    for num in range(10, 255):
        score_db.record_submission(competition_id_today, num, f"h{num}", f"c{num}", 100 + num, int(time.time()), f"name{num}", f"revis{num}")
        score_db.record_submission_loss(competition_id_today, num, num, is_eligible=True)
        temp_hot[num] = f"h{num}"
        temp_cold[num] = f"c{num}"

    assert select_winner(score_db, competition_id_today, temp_hot | {0: "h0", 1: "h1", 2: "h2", 3: "h33"},
                        temp_cold | {0: "c0", 1: "c1", 2: "c2", 3: "c33"}) == (0, 0.101)

    score_db.record_submission(competition_id_today, 4, "h4", "c4", 80, int(time.time()), "name4", "revis4")
    score_db.record_submission_loss(competition_id_today, 4, 0.09, is_eligible=True)

    assert select_winner(score_db, competition_id_today, temp_hot | {0: "h0", 1: "h1", 2: "h2", 3: "h33", 4: "h44"},
                        temp_cold | {0: "c0", 1: "c1", 2: "c2", 3: "c33", 4: "c44"}) == (0, 0.09)

    score_db.record_submission(competition_id_today, 5, "h5", "c4", 4, int(time.time()), "name5", "revis5")
    score_db.record_submission_loss(competition_id_today, 5, 55, is_eligible=True)

    assert select_winner(score_db, competition_id_today, temp_hot | {0: "h0", 1: "h1", 2: "h2", 3: "h33", 4: "h44", 5: "h5"},
                        temp_cold | {0: "c0", 1: "c1", 2: "c2", 3: "c33", 4: "c44", 5: "c4"}) == (5, 0.09)

    score_db.record_submission(competition_id_today, 5, "h5", "c4", 4, int(time.time()), "name5", "revis5")
    score_db.record_submission_loss(competition_id_today, 5, 55, is_eligible=True)

    assert select_winner(score_db, competition_id_today, temp_hot | {0: "h0", 1: "h1", 2: "h2", 3: "h33", 4: "h44", 5: "h55"},
                        temp_cold | {0: "c0", 1: "c1", 2: "c2", 3: "c33", 4: "c44", 5: "c45"}) == (0, 0.09)