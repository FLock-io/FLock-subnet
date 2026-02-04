import json
import sqlite3
import time
import logging
from flockoff import constants

logger = logging.getLogger(__name__)


class DatabaseError(Exception):
    """Custom exception for database-related errors."""
    pass


class ScoreDB:
    def __init__(self, db_path: str):
        self.db_path = db_path
        try:
            self.conn = sqlite3.connect(self.db_path)  # Single connection
            self._init_db()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database at {db_path}: {str(e)}")
            raise DatabaseError(f"Database initialization failed: {str(e)}") from e

    def _init_db(self):
        """Initialize the database with a table to store UID, hotkey, raw_score, and normalized_score."""
        try:
            c = self.conn.cursor()
            c.execute(
                """CREATE TABLE IF NOT EXISTS daily_competitions (
                          competition_id TEXT PRIMARY KEY,
                          dataset_commit TEXT, 
                          submission_start_timestamp INTEGER,
                          submission_end_timestamp INTEGER,
                          winner_uid int,
                          winner_loss REAL,
                          status TEXT,
                          use_yesterday_reward INTEGER,
                          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                          );"""
            )

            c.execute(
                """CREATE TABLE IF NOT EXISTS competition_submissions (
                           competition_id TEXT,
                           uid INTEGER,
                           coldkey TEXT,
                           hotkey TEXT,
                           commitment_block INTEGER,
                           commitment_timestamp INTEGER,
                           eval_loss REAL,
                           namespace TEXT,
                           revision TEXT,
                           is_eligible INTEGER,
                           PRIMARY KEY (competition_id, uid),
                           FOREIGN KEY (competition_id) REFERENCES daily_competitions(competition_id)
                           )"""
            )

            c.execute(
                """CREATE TABLE IF NOT EXISTS dataset_revisions
                           (local_path TEXT PRIMARY KEY, namespace TEXT, revision TEXT)"""
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database tables: {str(e)}")
            raise DatabaseError(f"Failed to create database tables: {str(e)}") from e

    def _add_column_if_not_exists(self, cursor, table_name, column_name, column_type):
        try:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [column[1] for column in cursor.fetchall()]

            if column_name not in columns:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                logger.info(f"Added column {column_name} to table {table_name}")

        except sqlite3.Error as e:
            logger.warning(f"Failed to add column {column_name} to {table_name}: {e}")

    def get_competition_info(self, competition_id: str) -> str:
        if not competition_id:
            return ""
        try:
            c = self.conn.cursor()
            cur = c.execute("SELECT dataset_commit FROM daily_competitions WHERE competition_id = ?", (competition_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get get_competition_info: {str(e)}")
            raise DatabaseError(f"Failed to get get_competition_info: {str(e)}") from e

    def create_competition(self, competition_id: str, submission_start_timestamp: int, dataset_commit: str):
        try:
            status = 'submission'
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO daily_competitions (competition_id,submission_start_timestamp,submission_end_timestamp, dataset_commit, status,use_yesterday_reward) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (competition_id, submission_start_timestamp, submission_start_timestamp + 60 * constants.submission_window_mins, dataset_commit, status)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to create competition_id {competition_id}: {str(e)}")
            raise DatabaseError(f"Failed to create competition_id: {str(e)}") from e

    def copy_competition_id(self, new_id, old_id):
        sql = """
        INSERT INTO daily_competitions (
            competition_id,
            dataset_commit,
            submission_start_timestamp,
            submission_end_timestamp,
            winner_uid,
            winner_loss,
            status,
            use_yesterday_reward
        )
        SELECT
            ?,
            dataset_commit,
            submission_start_timestamp,
            submission_end_timestamp,
            winner_uid,
            winner_loss,
            ?,
            1
        FROM daily_competitions
        WHERE competition_id = ?;
        """
        try:
            c = self.conn.cursor()
            c.execute(sql, (new_id, "rewarding", old_id))
            self.conn.commit()

        except sqlite3.Error as e:
            logger.error(f"Failed to copy competition_id {new_id}: {str(e)}")
            raise DatabaseError(f"Failed to copy competition_id: {str(e)}") from e

    def update_competition_status(self, competition_id: str, status: str):
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE daily_competitions SET status = ? WHERE competition_id = ?",
                (status, competition_id)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to set update_competition_status: {str(e)}")
            raise DatabaseError(f"Failed to set update_competition_status: {str(e)}") from e

    def update_competition_score(self, competition_id: str, winner_uid: int, winner_loss: float):
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE daily_competitions SET winner_uid=?,winner_loss=? WHERE competition_id = ?",
                (winner_uid,  winner_loss, competition_id)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to set update_competition_status: {str(e)}")
            raise DatabaseError(f"Failed to set update_competition_status: {str(e)}") from e

    def record_submission(self, competition_id: str, uid: int, hotkey: str, coldkey: str, commitment_block: int, commitment_timestamp: int,namespace: str,revision: str):
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO competition_submissions (competition_id, uid, hotkey, coldkey, commitment_block, commitment_timestamp,namespace,revision) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(competition_id, uid) DO UPDATE SET hotkey = excluded.hotkey, coldkey = excluded.coldkey,"
                "commitment_block = excluded.commitment_block,commitment_timestamp = excluded.commitment_timestamp,"
                "namespace = excluded.namespace,revision = excluded.revision;",
                (competition_id, uid, hotkey, coldkey, commitment_block, commitment_timestamp,namespace,revision)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to set record_submission {uid}: {str(e)}")
            raise DatabaseError(f"Failed to update record_submission: {str(e)}") from e


    def record_submission_loss(self, competition_id: str, uid: int,eval_loss: float, is_eligible: bool):
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT INTO competition_submissions (competition_id, uid, eval_loss, is_eligible) "
                "VALUES (?, ?, ?, ?) ON CONFLICT(competition_id, uid) DO UPDATE SET eval_loss = excluded.eval_loss, is_eligible = excluded.is_eligible;",
                (competition_id, uid, eval_loss, is_eligible)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to set record_submission_loss {uid}: {str(e)}")
            raise DatabaseError(f"Failed to record_submission_loss: {str(e)}") from e

    def get_competition_submissions(self, competition_id: str) -> dict:
        try:
            c = self.conn.cursor()
            cur = c.execute(
                "SELECT uid, coldkey, hotkey, commitment_block, commitment_timestamp, eval_loss,namespace,revision, is_eligible FROM competition_submissions WHERE competition_id = ?",
                (competition_id,)
            )
            cols = ['uid', 'coldkey', 'hotkey', 'commitment_block', 'commitment_timestamp', 'eval_loss', 'namespace','revision','is_eligible']
            rows = cur.fetchall()
            return {row[0]: dict(zip(cols, row)) for row in rows}
        except sqlite3.Error as e:
            logger.error(f"Failed to get_competition_submissions competition_id {competition_id}: {str(e)}")
            raise DatabaseError(f"Failed to get_competition_submissions: {str(e)}") from e

    def get_competition_status(self, competition_id: str) -> str:
        try:
            c = self.conn.cursor()
            cur = c.execute("SELECT status FROM daily_competitions WHERE competition_id = ?", (competition_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get get_competition_status: {str(e)}")
            raise DatabaseError(f"Failed to get get_competition_status: {str(e)}") from e

    def get_revision(self, namespace: str, local_path: str) -> str:
        try:
            c = self.conn.cursor()
            cur = c.execute("SELECT revision FROM dataset_revisions WHERE namespace = ? AND local_path = ?", (namespace, local_path))
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get get_revision: {str(e)}")
            raise DatabaseError(f"Failed to get get_revision: {str(e)}") from e

    def set_revision(self, namespace: str, revision: str, local_path: str):
        try:
            c = self.conn.cursor()
            c.execute(
                "INSERT OR REPLACE INTO dataset_revisions (local_path, namespace, revision) VALUES (?, ?, ?)",
                (local_path, namespace, revision)
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to set set_revision {local_path}: {str(e)}")
            raise DatabaseError(f"Failed to record_submission_loss: {str(e)}") from e

    def get_competition_winner(self, competition_id: str) -> int:
        try:
            c = self.conn.cursor()
            cur = c.execute("SELECT winner_uid FROM daily_competitions WHERE competition_id = ?", (competition_id,))
            row = cur.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get get_competition_status: {str(e)}")
            raise DatabaseError(f"Failed to get get_competition_status: {str(e)}") from e

    def __del__(self):
        """Close the connection when the instance is destroyed."""
        try:
            if hasattr(self, "conn"):
                self.conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to close database connection: {str(e)}")
