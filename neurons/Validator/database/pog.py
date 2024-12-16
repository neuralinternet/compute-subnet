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
