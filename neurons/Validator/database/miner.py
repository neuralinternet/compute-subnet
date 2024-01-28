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

import bittensor as bt

from compute.utils.db import ComputeDb


def select_miners(db: ComputeDb) -> dict:
    cursor = db.get_cursor()
    cursor.execute("SELECT uid, ss58_address FROM miner")

    results = cursor.fetchall()

    miners = {}
    for result in results:
        uid, ss58_address = result
        miners[uid] = ss58_address

    cursor.close()
    return miners


def update_miners(db: ComputeDb, miners: list):
    """
    Update the challenge details of the current batch miners.
    :param db:
    :param miners:
    [
        (uid, ss58_address),
        (uid1, ss58_address1),
    ]
    :return:
    """
    cursor = db.get_cursor()
    try:
        cursor.executemany("INSERT OR IGNORE INTO miner (uid, ss58_address) VALUES (?, ?)", miners)
        db.conn.commit()

        # Commit changes
        db.conn.commit()
    except Exception as e:
        db.conn.rollback()
        bt.logging.error(f"Error while updating update_miners: {e}")
    finally:
        cursor.close()


def purge_miner_entries(db: ComputeDb, uid: int, hotkey: str):
    """
    When a pair of (uid and hotkey) changed, it means miner got deregister,
    we need to vacuum all entries corresponding to this miner.
    :param db:
    :param uid:
    :param hotkey:
    :return:
    """
    cursor = db.get_cursor()
    try:
        cursor.execute(
            "DELETE FROM miner WHERE uid = ? AND ss58_address = ?",
            (uid, hotkey),
        )
        cursor.execute(
            "DELETE FROM challenge_details WHERE uid = ? AND ss58_address = ?",
            (uid, hotkey),
        )
        db.conn.commit()

        if cursor.rowcount > 0:
            bt.logging.info(f"Entries for UID '{uid}' and Hotkey '{hotkey}' purged successfully.")
        else:
            bt.logging.info(f"No matching entries found for UID '{uid}' and Hotkey '{hotkey}'. No deletion performed.")
    except Exception as e:
        bt.logging.error(f"Error while purging entries: {e}")
    finally:
        cursor.close()
