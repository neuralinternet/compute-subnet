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


def select_challenge_stats(db: ComputeDb) -> dict:
    cursor = db.get_cursor()
    cursor.execute(
        """
SELECT
    main_query.uid,
    main_query.ss58_address,
    main_query.challenge_attempts,
    main_query.challenge_successes,
    main_query.challenge_elapsed_time_avg,
    main_query.challenge_difficulty_avg,
    sub_query.challenge_failed
FROM (
    SELECT
        uid,
        ss58_address,
        COUNT(*) AS challenge_attempts,
        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS challenge_successes,
        AVG(CASE WHEN success = 1 THEN elapsed_time END) AS challenge_elapsed_time_avg,
        AVG(CASE WHEN success = 1 THEN difficulty END) AS challenge_difficulty_avg
    FROM challenge_details
    GROUP BY uid, ss58_address
) AS main_query
LEFT JOIN (
    SELECT
        uid,
        ss58_address,
        COUNT(*) AS challenge_failed
    FROM (
        SELECT
            uid,
            ss58_address
        FROM challenge_details
        WHERE success = FALSE
        ORDER BY created_at DESC
        LIMIT 10
    )
    GROUP BY uid, ss58_address
) AS sub_query ON main_query.uid = sub_query.uid AND main_query.ss58_address = sub_query.ss58_address
        """
    )

    results = cursor.fetchall()

    stats = {}
    for result in results:
        uid, ss58_address, challenge_attempts, challenge_successes, challenge_elapsed_time_avg, challenge_difficulty_avg, challenge_failed = result
        pk = (uid, ss58_address)
        stats[pk] = {
            "challenge_attempts": challenge_attempts,
            "challenge_successes": challenge_successes,
            "challenge_failed": int(challenge_failed) if challenge_failed else 0,
            "challenge_elapsed_time_avg": challenge_elapsed_time_avg,
            "challenge_difficulty_avg": challenge_difficulty_avg,
        }

    cursor.close()
    return stats


def update_challenge_details(db: ComputeDb, pow_benchmarks: list):
    """
    Update the challenge details of the current batch miners.
    :param db:
    :param pow_benchmarks:
    [
        {"uid": "uid1", "ss58_address": "address1", "success": True, "elapsed_time": 10.5, "difficulty": 3},
        {"uid": "uid2", "ss58_address": "address2", "success": False, "elapsed_time": 15.2, "difficulty": 2},
    ]
    :return:
    """
    cursor = db.get_cursor()
    try:
        miner_to_insert = [
            (
                benchmark.get("uid"),
                benchmark.get("ss58_address"),
            )
            for benchmark in pow_benchmarks
        ]

        # Prepare data for bulk insert
        challenge_details_to_insert = [
            (
                benchmark.get("uid"),
                benchmark.get("ss58_address"),
                benchmark.get("success"),
                benchmark.get("elapsed_time"),
                benchmark.get("difficulty"),
                datetime.datetime.now(),
            )
            for benchmark in pow_benchmarks
        ]

        cursor.executemany("INSERT OR IGNORE INTO miner (uid, ss58_address) VALUES (?, ?)", miner_to_insert)
        db.conn.commit()

        # Perform bulk insert using executemany
        cursor.executemany(
            "INSERT INTO challenge_details (uid, ss58_address, success, elapsed_time, difficulty, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            challenge_details_to_insert,
        )

        # Commit changes
        db.conn.commit()
    except Exception as e:
        db.conn.rollback()
        bt.logging.error(f"Error while updating challenge_details: {e}")
    finally:
        cursor.close()


def purge_challenge_entries(db: ComputeDb, uid: str, hotkey: str):
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
        db.conn.commit()

        if cursor.rowcount > 0:
            bt.logging.info(f"Entries for UID '{uid}' and Hotkey '{hotkey}' purged successfully.")
        else:
            bt.logging.info(f"No matching entries found for UID '{uid}' and Hotkey '{hotkey}'. No deletion performed.")
    except Exception as e:
        bt.logging.error(f"Error while purging entries: {e}")
    finally:
        cursor.close()
