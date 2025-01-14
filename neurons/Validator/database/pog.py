# The MIT License (MIT)
# Copyright © 2023 Rapiiidooo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
import datetime
import json

import bittensor as bt

from compute.utils.db import ComputeDb

def update_pog_stats(db: ComputeDb, hotkey, gpu_name, num_gpus):
        """
        Inserts a new GPU spec entry for a given hotkey and ensures that only
        the latest three entries are retained.

        :param hotkey: The miner's hotkey identifier.
        :param gpu_name: The name/model of the GPU.
        :param num_gpus: The number of GPUs.
        """
        cursor = db.get_cursor()
        try:
            # Insert the new GPU spec
            cursor.execute(
                """
                INSERT INTO pog_stats (hotkey, gpu_name, num_gpus)
                VALUES (?, ?, ?)
                """,
                (hotkey, gpu_name, num_gpus)
            )

            # Delete older entries if more than 4 exist for the hotkey
            cursor.execute(
                """
                DELETE FROM pog_stats
                WHERE id NOT IN (
                    SELECT id FROM pog_stats
                    WHERE hotkey = ?
                    ORDER BY created_at DESC
                    LIMIT 4
                )
                AND hotkey = ?
                """,
                (hotkey, hotkey)
            )

            db.conn.commit()
            # bt.logging.info(f"Updated pog_stats for hotkey: {hotkey}")
        except Exception as e:
            db.conn.rollback()
            # bt.logging.error(f"Error updating pog_stats for {hotkey}: {e}")
        finally:
            cursor.close()

def get_pog_specs(db: ComputeDb, hotkey):
    """
    Retrieves the most recent GPU spec entry for a given hotkey where gpu_name is not None.

    :param hotkey: The miner's hotkey identifier.
    :return: A dictionary with 'gpu_name' and 'num_gpus' or None if no valid entries exist.
    """
    cursor = db.get_cursor()
    try:
        cursor.execute(
            """
            SELECT gpu_name, num_gpus
            FROM pog_stats
            WHERE hotkey = ? AND gpu_name IS NOT NULL AND num_gpus IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (hotkey,)
        )
        row = cursor.fetchone()
        if row:
            gpu_name, num_gpus = row
            # bt.logging.info(f"Retrieved pog_stats for hotkey {hotkey}: GPU Name={gpu_name}, Num GPUs={num_gpus}")
            return {"gpu_name": gpu_name, "num_gpus": num_gpus}
        else:
            # bt.logging.warning(f"No valid pog_stats found for hotkey {hotkey}")
            return None
    except Exception as e:
        # bt.logging.error(f"Error retrieving pog_stats for {hotkey}: {e}")
        return None
    finally:
        cursor.close()

def write_stats(self, stats):
    cursor = self.get_cursor()
    try:
        for uid, data in stats.items():
            raw_specs = data.get("gpu_specs")

            # If raw_specs is *already a dict*, we do one json.dumps():
            if isinstance(raw_specs, dict):
                gpu_specs = json.dumps(raw_specs)  # Properly convert dict -> JSON string
            else:
                # If None or a string that you trust is *already* JSON, handle that gracefully
                gpu_specs = raw_specs

            # Ensure 'score' is numeric if storing as REAL
            numeric_score = float(data.get("score", 0))

            cursor.execute(
                """
                INSERT INTO stats (uid, hotkey, gpu_specs, score, allocated, own_score, reliability_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(uid) DO UPDATE SET
                    hotkey=excluded.hotkey,
                    gpu_specs=excluded.gpu_specs,
                    score=excluded.score,
                    allocated=excluded.allocated,
                    own_score=excluded.own_score,
                    reliability_score=excluded.reliability_score,
                    created_at=CURRENT_TIMESTAMP
                """,
                (
                    uid,
                    data.get("hotkey"),
                    gpu_specs,  # store JSON or None
                    numeric_score,
                    data.get("allocated"),
                    data.get("own_score"),
                    data.get("reliability_score"),
                ),
            )
        self.conn.commit()
    except Exception as e:
        self.conn.rollback()
        bt.logging.error(f"Failed to write stats: {e}")
    finally:
        cursor.close()

def retrieve_stats(db: ComputeDb):
    cursor = db.get_cursor()
    try:
        cursor.execute("SELECT * FROM stats")
        rows = cursor.fetchall()

        stats_dict = {}
        for row in rows:
            uid = row[0]
            hotkey = row[1]

            # row[2] is the gpu_specs from DB, which might be JSON or None
            raw_gpu_specs = row[2]
            gpu_specs = None
            if raw_gpu_specs:
                try:
                    gpu_specs = json.loads(raw_gpu_specs)  # Convert from JSON -> dict
                except Exception as e:
                    bt.logging.error(
                        f"Failed to parse gpu_specs for UID {uid} (hotkey={hotkey}): {raw_gpu_specs}\nError: {e}"
                    )
                    gpu_specs = None

            stats_dict[uid] = {
                "uid": uid,
                "hotkey": hotkey,
                "gpu_specs": gpu_specs,  # Now a dict or None
                "score": float(row[3] or 0),  # ensure numeric
                "allocated": bool(row[4]),
                "own_score": bool(row[5]),
                "reliability_score": row[6],
                "created_at": row[7],
            }

        return stats_dict

    except Exception as e:
        bt.logging.error(f"Failed to retrieve stats: {e}")
        return {}
    finally:
        cursor.close()
