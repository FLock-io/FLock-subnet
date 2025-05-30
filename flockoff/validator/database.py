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
        """Initialize the database with a table to store UID, hotkey, raw_score, and normalized_score."""
        try:
            c = self.conn.cursor()
            c.execute(
                """CREATE TABLE IF NOT EXISTS miner_scores
                         (uid INTEGER, 
                          hotkey TEXT, 
                          raw_score REAL, 
                          normalized_score REAL, 
                          PRIMARY KEY (uid, hotkey))"""
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
        self, uid: int, hotkey: str, base_raw_score: float = 0.0, initial_normalized_score: float = 1.0 / 255.0
    ):
        """Insert a new UID or reset its scores if the hotkey has changed (UID recycled).
        
        Args:
            uid (int): The UID of the miner.
            hotkey (str): The hotkey of the miner.
            base_raw_score (float, optional): The initial raw score to set. 
                                             Defaults to 0.0 if not provided by the caller.
            initial_normalized_score (float, optional): The initial normalized score (weight).
                                                        Defaults to 1.0 / 255.0 if not provided by the caller.
        """
        try:
            c = self.conn.cursor()
            c.execute("SELECT hotkey FROM miner_scores WHERE uid = ?", (uid,))
            result = c.fetchone()
            if result is None:
                # UID doesn't exist, insert new record
                c.execute(
                    """INSERT INTO miner_scores 
                         (uid, hotkey, raw_score, normalized_score) 
                         VALUES (?, ?, ?, ?)""",
                    (uid, hotkey, base_raw_score, initial_normalized_score),
                )
            elif result[0] != hotkey:
                # UID exists but hotkey changed, update the existing row with new hotkey and reset scores
                c.execute(
                    """UPDATE miner_scores 
                       SET hotkey = ?, raw_score = ?, normalized_score = ? 
                       WHERE uid = ?""",
                    (hotkey, base_raw_score, initial_normalized_score, uid),
                )
            # If UID and hotkey match, we don't reset scores, assuming they are current.
            # Specific updates to raw_score or normalized_score will be handled by dedicated methods.
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to insert/reset UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to insert/reset UID: {str(e)}") from e

    def update_raw_eval_score(self, uid: int, new_raw_score: float):
        """Update the raw evaluation score for a given UID."""
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE miner_scores SET raw_score = ? WHERE uid = ?", (new_raw_score, uid)
            )
            if c.rowcount == 0:
                # If somehow a UID is being updated that wasn't inserted, log a warning or error.
                logger.warning(f"Attempted to update raw_score for non-existent UID {uid}, no changes made.")
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to update raw_score for UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to update raw_score: {str(e)}") from e

    def update_final_normalized_score(self, uid: int, new_normalized_score: float):
        """Update the final normalized score for a given UID."""
        try:
            c = self.conn.cursor()
            c.execute(
                "UPDATE miner_scores SET normalized_score = ? WHERE uid = ?", (new_normalized_score, uid)
            )
            if c.rowcount == 0:
                logger.warning(f"Attempted to update normalized_score for non-existent UID {uid}, no changes made.")
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to update normalized_score for UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to update normalized_score: {str(e)}") from e

    def get_raw_eval_score(self, uid: int) -> float | None:
        """Retrieve the raw evaluation score for a given UID, defaulting to None if not found."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT raw_score FROM miner_scores WHERE uid = ?", (uid,))
            result = c.fetchone()
            return result[0] if result else None
        except sqlite3.Error as e:
            logger.error(f"Failed to get raw_score for UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve raw_score: {str(e)}") from e

    def get_all_normalized_scores(self, uids: list) -> list:
        """Retrieve normalized scores for a list of UIDs, defaulting to 0.0 if not found."""
        # This replaces the old get_scores for the purpose of initializing weights.
        try:
            c = self.conn.cursor()
            # Ensure there are UIDs to prevent empty IN clause
            if not uids:
                return []
            
            placeholders = ','.join('?' * len(uids))
            c.execute(
                f"SELECT uid, normalized_score FROM miner_scores WHERE uid IN ({placeholders})",
                uids,
            )
            scores_dict = {uid_val: score for uid_val, score in c.fetchall()}
            # Default to 0.0 for UIDs not found in the database
            return [scores_dict.get(uid_val, 0.0) for uid_val in uids]
        except sqlite3.Error as e:
            logger.error(f"Failed to get normalized_scores for UIDs {uids}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve normalized_scores: {str(e)}") from e
    
    def get_normalized_score(self, uid: int) -> float:
        """Retrieve the normalized score for a given UID, defaulting to 0.0 if not found."""
        try:
            c = self.conn.cursor()
            c.execute("SELECT normalized_score FROM miner_scores WHERE uid = ?", (uid,))
            result = c.fetchone()
            return result[0] if result else 0.0
        except sqlite3.Error as e:
            logger.error(f"Failed to get normalized_score for UID {uid}: {str(e)}")
            raise DatabaseError(f"Failed to retrieve normalized_score: {str(e)}") from e

    def __del__(self):
        """Close the connection when the instance is destroyed."""
        try:
            if hasattr(self, "conn"):
                self.conn.close()
        except sqlite3.Error as e:
            logger.error(f"Failed to close database connection: {str(e)}")
