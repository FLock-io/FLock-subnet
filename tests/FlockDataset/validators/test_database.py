import pytest
from flockoff.validator.database import ScoreDB


@pytest.fixture
def db():
    """Fixture to create an in-memory database for each test."""
    db_instance = ScoreDB(":memory:")
    yield db_instance


def test_init_db(db):
    """Test that the database initializes with the correct table."""
    c = db.conn.cursor()
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_scores'"
    )
    assert c.fetchone() is not None, "The 'miner_scores' table should be created"


def test_insert_or_reset_uid(db):
    """Test inserting or resetting UIDs with hotkeys."""
    base = 1.0 / 255.0

    # Insert new UID
    db.insert_or_reset_uid(1, "hotkey1")
    scores = db.get_scores([1])
    assert scores == [pytest.approx(base)], f"New UID should have score {base}"

    # Update score and check no reset with same hotkey
    db.update_score(1, 5.0)
    scores = db.get_scores([1])
    assert scores == [5.0], "Score should be updated to 5.0"
    db.insert_or_reset_uid(1, "hotkey1")
    scores = db.get_scores([1])
    assert scores == [5.0], "Score should remain 5.0 when hotkey is the same"

    # Reset score with different hotkey
    db.insert_or_reset_uid(1, "hotkey2")
    scores = db.get_scores([1])
    assert scores == [
        pytest.approx(base)
    ], f"Score should reset to {base} with new hotkey"


def test_update_score(db):
    """Test updating scores for UIDs."""
    # Insert UID and overwrite score
    db.insert_or_reset_uid(1, "hotkey1")
    db.update_score(1, 3.0)
    scores = db.get_scores([1])
    assert scores == [3.0], "Score should be updated to 3.0"

    # Overwrite with a new value
    db.update_score(1, 2.0)
    scores = db.get_scores([1])
    assert scores == [2.0], "Score should be overwritten to 2.0"


def test_get_scores(db):
    """Test retrieving scores for UIDs."""
    # Insert multiple UIDs
    db.insert_or_reset_uid(1, "hotkey1")
    db.insert_or_reset_uid(2, "hotkey2")
    db.update_score(1, 10.0)
    db.update_score(2, 20.0)

    # Get scores for existing UIDs
    scores = db.get_scores([1, 2])
    assert len(scores) == 2, "Should return two scores"
    assert scores[0] == 10.0, "UID 1 should have score 10.0"
    assert scores[1] == 20.0, "UID 2 should have score 20.0"

    # Get score for non-existing UID
    scores = db.get_scores([3])
    assert scores == [0.0], "Non-existing UID should return 0.0"

    # Get scores for mixed UIDs
    scores = db.get_scores([1, 3])
    assert len(scores) == 2, "Should return two scores"
    assert scores[0] == 10.0, "Existing UID 1 should have score 10.0"
    assert scores[1] == 0.0, "Non-existing UID 3 should have score 0.0"


def test_get_score(db):
    """Test retrieving a single score for a UID."""
    # Test non-existing UID
    score = db.get_score(1)
    assert score == 0.0, "Non-existing UID should return 0.0"

    # Insert UID and check score
    db.insert_or_reset_uid(1, "hotkey1")
    score = db.get_score(1)
    assert score == pytest.approx(1.0 / 255.0), f"New UID should have score {1.0/255.0}"

    # Update score and check
    db.update_score(1, 5.0)
    score = db.get_score(1)
    assert score == 5.0, "Score should be updated to 5.0"

    # Test with multiple UIDs
    db.insert_or_reset_uid(2, "hotkey2")
    db.update_score(2, 10.0)
    score1 = db.get_score(1)
    score2 = db.get_score(2)
    assert score1 == 5.0, "UID 1 should have score 5.0"
    assert score2 == 10.0, "UID 2 should have score 10.0"
