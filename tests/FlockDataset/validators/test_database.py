import pytest
from flockoff.validator.database import ScoreDB


@pytest.fixture
def db():
    """Fixture to create an in-memory database for each test."""
    db_instance = ScoreDB(":memory:")
    yield db_instance


def test_init_db(db):
    """Test that the database initializes with the correct tables."""
    c = db.conn.cursor()

    # Check for daily_competitions
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_competitions'")
    assert c.fetchone() is not None, "Table 'daily_competitions' should exist"

    # Check for competition_submissions
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='competition_submissions'")
    assert c.fetchone() is not None, "Table 'competition_submissions' should exist"

    # Check for dataset_revisions
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dataset_revisions'")
    assert c.fetchone() is not None, "Table 'dataset_revisions' should exist"


def test_competition_lifecycle(db):
    """Test creating a competition, retrieving info, and updating status."""
    comp_id = "comp_2023_10_01"
    start_time = 1700000000
    commit_hash = "abc12345"

    # 1. Create Competition
    db.create_competition(comp_id, start_time, commit_hash)

    # 2. Get Info
    retrieved_commit = db.get_competition_info(comp_id)
    assert retrieved_commit == commit_hash, "Should retrieve the correct dataset commit"

    # 3. Check Initial Status
    status = db.get_competition_status(comp_id)
    assert status == "submission", "Initial status should be 'submission'"

    # 4. Update Status
    db.update_competition_status(comp_id, "evaluating")
    new_status = db.get_competition_status(comp_id)
    assert new_status == "evaluating", "Status should be updated to 'evaluating'"


def test_record_submission(db):
    """Test recording and retrieving miner submissions."""
    comp_id = "comp_1"
    db.create_competition(comp_id, 1000, "commit_x")

    uid = 5
    hotkey = "hk_5"
    coldkey = "ck_5"

    # 1. Record Submission
    db.record_submission(
        competition_id=comp_id,
        uid=uid,
        hotkey=hotkey,
        coldkey=coldkey,
        commitment_block=100,
        commitment_timestamp=1001,
        namespace="hf_repo",
        revision="main"
    )

    # 2. Retrieve Submissions
    submissions = db.get_competition_submissions(comp_id)
    assert uid in submissions
    data = submissions[uid]
    assert data['hotkey'] == hotkey
    assert data['namespace'] == "hf_repo"
    assert data['eval_loss'] is None  # Should be None initially

    # 3. Update Submission (Upsert) - Change revision
    db.record_submission(
        competition_id=comp_id,
        uid=uid,
        hotkey=hotkey,
        coldkey=coldkey,
        commitment_block=105,
        commitment_timestamp=1005,
        namespace="hf_repo",
        revision="dev_branch"
    )

    submissions_updated = db.get_competition_submissions(comp_id)
    assert submissions_updated[uid]['revision'] == "dev_branch", "Submission should be updated"


def test_record_submission_loss(db):
    """Test updating the evaluation loss and eligibility."""
    comp_id = "comp_1"
    uid = 10
    db.create_competition(comp_id, 1000, "commit_x")

    # Must exist before recording loss
    db.record_submission(comp_id, uid, "hk", "ck", 1, 1, "ns", "rev")

    # 1. Record Loss
    loss_val = 0.456
    is_eligible = True
    db.record_submission_loss(comp_id, uid, loss_val, is_eligible)

    # 2. Verify
    submissions = db.get_competition_submissions(comp_id)
    assert submissions[uid]['eval_loss'] == loss_val
    assert submissions[uid]['is_eligible'] == 1  # SQLite stores bool as 0/1


def test_competition_winner_and_score(db):
    """Test setting and retrieving the competition winner."""
    comp_id = "comp_winner_test"
    db.create_competition(comp_id, 1000, "commit_x")

    winner_uid = 42
    winner_loss = 0.123

    # 1. Update Score/Winner
    db.update_competition_score(comp_id, winner_uid, winner_loss)

    # 2. Get Winner
    retrieved_winner = db.get_competition_winner(comp_id)
    assert retrieved_winner == winner_uid

    # Check directly via SQL that loss was saved
    c = db.conn.cursor()
    c.execute("SELECT winner_loss FROM daily_competitions WHERE competition_id=?", (comp_id,))
    assert c.fetchone()[0] == winner_loss


def test_dataset_revisions(db):
    """Test setting and getting local dataset revisions."""
    namespace = "myset"
    revision = "v1.0"
    local_path = "/tmp/data"

    # 1. Set Revision
    db.set_revision(namespace, revision, local_path)

    # 2. Get Revision
    retrieved = db.get_revision(namespace, local_path)
    assert retrieved == revision

    # 3. Update Revision
    db.set_revision(namespace, "v1.1", local_path)
    retrieved_updated = db.get_revision(namespace, local_path)
    assert retrieved_updated == "v1.1"

    # 4. Non-existent
    assert db.get_revision("other", "path") is None


def test_copy_competition_id(db):
    """Test the functionality of copying/archiving a competition ID."""
    old_id = "comp_yesterday"
    new_id = "comp_rewarding_record"

    # Setup initial competition
    db.create_competition(old_id, 1000, "commit_old")
    db.update_competition_score(old_id, winner_uid=7, winner_loss=0.5)

    # Perform Copy
    db.copy_competition_id(new_id, old_id)

    # Verify New Entry
    c = db.conn.cursor()
    c.execute("SELECT dataset_commit, winner_uid, use_yesterday_reward, status FROM daily_competitions WHERE competition_id=?", (new_id,))
    row = c.fetchone()

    assert row is not None
    assert row[0] == "commit_old"  # Should copy commit
    assert row[1] == 7  # Should copy winner
    assert row[2] == 1  # use_yesterday_reward should be 1
    assert row[3] == "rewarding"  # status should be 'rewarding'


