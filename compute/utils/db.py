import sqlite3

import bittensor as bt


class ComputeDb:
    def __init__(self):
        # Connect to the database (or create it if it doesn't exist)
        self.conn = sqlite3.connect("database.db")
        self.init()

    def close(self):
        self.conn.close()

    def get_cursor(self):
        return self.conn.cursor()

    def init(self):
        cursor = self.get_cursor()

        try:
            cursor.execute("CREATE TABLE IF NOT EXISTS miner (uid INTEGER PRIMARY KEY, ss58_address TEXT UNIQUE)")
            cursor.execute("CREATE TABLE IF NOT EXISTS miner_details (id INTEGER PRIMARY KEY, hotkey TEXT, details TEXT)")
            cursor.execute("CREATE TABLE IF NOT EXISTS tb (id INTEGER PRIMARY KEY, hotkey TEXT, details TEXT)")
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS challenge_details (
                    uid INTEGER,
                    ss58_address TEXT,
                    success BOOLEAN,
                    elapsed_time REAL,
                    difficulty INTEGER,
                    created_at TIMESTAMP,
                    FOREIGN KEY (uid) REFERENCES miner(uid) ON DELETE CASCADE,
                    FOREIGN KEY (ss58_address) REFERENCES miner(ss58_address) ON DELETE CASCADE
                )
            """
            )
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_uid ON challenge_details (uid)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ss58_address ON challenge_details (ss58_address)")

            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            bt.logging.error(f"ComputeDb error: {e}")
        finally:
            cursor.close()
