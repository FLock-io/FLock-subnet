import sqlite3
import logging

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
        """Initialize the database with a table to store UID, hotkey, and score."""
        try:
            c = self.conn.cursor()
            c.execute(
                """CREATE TABLE IF NOT EXISTS miner_scores
                         (uid INTEGER, hotkey TEXT, score REAL, PRIMARY KEY (uid, hotkey))"""
            )

            c.execute(
                """CREATE TABLE IF NOT EXISTS dataset_revisions
                           (namespace TEXT PRIMARY KEY, revision TEXT)"""
            )

            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to initialize database tables: {str(e)}")
            raise DatabaseError(f"Failed to create database tables: {str(e)}") from e

    def get_revision(self, namespace: str) -> str | None:
        """Return last stored revision for this namespace (or None)."""
        try:
            c = self.conn.cursor()
            c.execute(
                "SELECT revision FROM dataset_revisions WHERE namespace = ?",
                (namespace,),
            )
            row = c.fetchone()
            return row[0] if row else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get revision for namespace {namespace}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve revision: {str(e)}") from e

    def set_revision(self, namespace: str, revision: str):
        """Upsert the revision for this namespace."""
        try:
            c = self.conn.cursor()
            c.execute(
                """
                INSERT INTO dataset_revisions(namespace, revision)
                VALUES (?, ?)
                ON CONFLICT(namespace) DO UPDATE SET revision=excluded.revision
                """,
                (namespace, revision),
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to set revision for namespace {namespace}: {str(e)}")
            raise DatabaseError(f"Failed to update revision: {str(e)}") from e

    def insert_or_reset_uid(
        self, uid: int, hotkey: str, base_score: float = 1.0 / 255.0
    ):
        """Insert a new UID or reset its score if the hotkey has changed (UID recycled)."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT hotkey FROM miner_scores WHERE uid = ?", (uid,))
            result = c.fetchone()
            if result is None or result[0] != hotkey:
                c.execute(
                    "INSERT OR REPLACE INTO miner_scores (uid, hotkey, score) VALUES (?, ?, ?)",
                    (uid, hotkey, base_score),
                )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to insert/reset UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to insert/reset UID: {str(e)}") from e

    def update_score(self, uid: int, new_score: float):
        """Update the score for a given UID"""
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE miner_scores SET score = ? WHERE uid = ?", (new_score, uid)
            )
            if c.rowcount == 0:
                # row absent – insert with unknown hotkey
                c.execute(
                    "INSERT INTO miner_scores (uid, hotkey, score) VALUES (?, '', ?)",
                    (uid, new_score),
                )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to update score for UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to update score: {str(e)}") from e

    def get_scores(self, uids: list) -> list:
        """Retrieve scores for a list of UIDs, defaulting to 0.0 if not found."""
        try:
            c = self.conn.cursor()
            c.execute(
                f"SELECT uid, score FROM miner_scores WHERE uid IN ({','.join('?'*len(uids))})",
                uids,
            )
            scores_dict = {uid: score for uid, score in c.fetchall()}
            return [scores_dict.get(uid, 0.0) for uid in uids]
        except sqlite3.Error as e:
            logger.error(f"Failed to get scores for UIDs {uids}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve scores: {str(e)}") from e
    
    def get_score(self, uid: int) -> float:
        """Retrieve the score for a given UID, defaulting to 0.0 if not found."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT score FROM miner_scores WHERE uid = ?", (uid,))
            result = c.fetchone()
            return result[0] if result else 0.0
        except sqlite3.Error as e:
            logger.error(f"Failed to get score for UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve score: {str(e)}") from e

    def __del__(self):
        """Close the connection when the instance is destroyed."""
        try:
            if hasattr(self, "conn"):
                self.conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to close database connection: {str(e)}")
