import pytest
from flockoff.validator.database import ScoreDB


@pytest.fixture
def db():
    """Fixture to create an in-memory database for each test."""
    db_instance = ScoreDB(":memory:")
    yield db_instance


def test_init_db(db):
    """Test that the database initializes with the correct table and columns."""
    c = db.conn.cursor()
    c.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='miner_scores'"
    )
    assert c.fetchone() is not None, "The 'miner_scores' table should be created"
    c.execute("PRAGMA table_info(miner_scores)")
    columns = {row[1] for row in c.fetchall()}
    expected_columns = {"uid", "hotkey", "raw_score", "normalized_score"}
    assert columns == expected_columns, f"Expected columns {expected_columns}, got {columns}"


def test_insert_or_reset_uid(db):
    """Test inserting or resetting UIDs with hotkeys, raw_score, and normalized_score."""
    base_raw = 0.05  # Example base raw score
    initial_norm = 0.0  # Example initial normalized score

    # Insert new UID
    db.insert_or_reset_uid(1, "hotkey1", base_raw, initial_norm)
    raw_score = db.get_raw_eval_score(1)
    norm_score = db.get_normalized_score(1)
    assert raw_score == pytest.approx(base_raw), f"New UID should have raw_score {base_raw}"
    assert norm_score == pytest.approx(initial_norm), f"New UID should have normalized_score {initial_norm}"

    # Update scores and check no reset with same hotkey
    db.update_raw_eval_score(1, 0.75)
    db.update_final_normalized_score(1, 0.85)
    raw_score = db.get_raw_eval_score(1)
    norm_score = db.get_normalized_score(1)
    assert raw_score == 0.75, "Raw score should be updated"
    assert norm_score == 0.85, "Normalized score should be updated"
    
    db.insert_or_reset_uid(1, "hotkey1", base_raw, initial_norm) # This should not overwrite existing if hotkey matches
    raw_score_after_reinsert = db.get_raw_eval_score(1)
    norm_score_after_reinsert = db.get_normalized_score(1)
    assert raw_score_after_reinsert == 0.75, "Raw score should remain after re-insert with same hotkey"
    assert norm_score_after_reinsert == 0.85, "Normalized score should remain after re-insert with same hotkey"

    # Reset scores with different hotkey
    new_base_raw = 0.06
    new_initial_norm = 0.01
    db.insert_or_reset_uid(1, "hotkey2", new_base_raw, new_initial_norm)
    raw_score = db.get_raw_eval_score(1)
    norm_score = db.get_normalized_score(1)
    assert raw_score == pytest.approx(new_base_raw), f"Raw score should reset to {new_base_raw} with new hotkey"
    assert norm_score == pytest.approx(new_initial_norm), f"Normalized score should reset to {new_initial_norm} with new hotkey"


def test_update_raw_eval_score(db):
    """Test updating raw evaluation scores for UIDs."""
    db.insert_or_reset_uid(1, "hotkey1", 0.1, 0.0)
    db.update_raw_eval_score(1, 0.77)
    raw_score = db.get_raw_eval_score(1)
    assert raw_score == 0.77, "Raw score should be updated to 0.77"

    # Test updating non-existent UID (should not raise error, no change)
    db.update_raw_eval_score(2, 0.88) 
    raw_score_2 = db.get_raw_eval_score(2)
    assert raw_score_2 is None, "Raw score for non-existent UID 2 should be None"


def test_update_final_normalized_score(db):
    """Test updating final normalized scores for UIDs."""
    db.insert_or_reset_uid(1, "hotkey1", 0.1, 0.0)
    db.update_final_normalized_score(1, 0.99)
    norm_score = db.get_normalized_score(1)
    assert norm_score == 0.99, "Normalized score should be updated to 0.99"

    # Test updating non-existent UID (should not raise error, no change)
    db.update_final_normalized_score(2, 0.88)
    norm_score_2 = db.get_normalized_score(2)
    assert norm_score_2 == 0.0, "Normalized score for non-existent UID 2 should be default 0.0"


def test_get_raw_eval_score(db):
    """Test retrieving raw evaluation scores."""
    # Test non-existing UID
    score = db.get_raw_eval_score(1)
    assert score is None, "Non-existing UID should return None for raw score"

    # Insert UID and check raw score
    db.insert_or_reset_uid(1, "hotkey1", 0.123, 0.0)
    score = db.get_raw_eval_score(1)
    assert score == 0.123, "Raw score should be 0.123"

    # Update raw score and check
    db.update_raw_eval_score(1, 0.456)
    score = db.get_raw_eval_score(1)
    assert score == 0.456, "Raw score should be updated to 0.456"

def test_get_all_normalized_scores(db):
    """Test retrieving all normalized scores for a list of UIDs."""
    db.insert_or_reset_uid(1, "hotkey1", 0.1, 0.5)
    db.insert_or_reset_uid(2, "hotkey2", 0.2, 0.6)
    db.update_final_normalized_score(1, 0.55)
    db.update_final_normalized_score(2, 0.66)

    # Get scores for existing UIDs
    scores = db.get_all_normalized_scores([1, 2])
    assert len(scores) == 2, "Should return two scores"
    assert scores[0] == 0.55, "UID 1 should have normalized score 0.55"
    assert scores[1] == 0.66, "UID 2 should have normalized score 0.66"

    # Get score for non-existing UID
    scores = db.get_all_normalized_scores([3])
    assert scores == [0.0], "Non-existing UID should return [0.0]"

    # Get scores for mixed UIDs
    scores = db.get_all_normalized_scores([1, 3])
    assert len(scores) == 2, "Should return two scores"
    assert scores[0] == 0.55, "Existing UID 1 should have normalized score 0.55"
    assert scores[1] == 0.0, "Non-existing UID 3 should have normalized score 0.0"
    
    # Test with empty list
    scores = db.get_all_normalized_scores([])
    assert scores == [], "Empty UID list should return empty list"


def test_get_normalized_score(db):
    """Test retrieving a single normalized score for a UID."""
    # Test non-existing UID
    score = db.get_normalized_score(1)
    assert score == 0.0, "Non-existing UID should return 0.0 for normalized score"

    # Insert UID and check initial normalized score
    db.insert_or_reset_uid(1, "hotkey1", 0.1, 0.05)
    score = db.get_normalized_score(1)
    assert score == 0.05, "Initial normalized score should be 0.05"

    # Update normalized score and check
    db.update_final_normalized_score(1, 0.75)
    score = db.get_normalized_score(1)
    assert score == 0.75, "Normalized score should be updated to 0.75"

    # Test with multiple UIDs
    db.insert_or_reset_uid(2, "hotkey2", 0.2, 0.15)
    db.update_final_normalized_score(2, 0.85)
    score1 = db.get_normalized_score(1)
    score2 = db.get_normalized_score(2)
    assert score1 == 0.75, "UID 1 normalized score should be 0.75"
    assert score2 == 0.85, "UID 2 normalized score should be 0.85"
