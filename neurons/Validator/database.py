# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend & Rapiiidooo
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
# Step 1: Import necessary libraries and modules

import sqlite3

import bittensor as bt

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect("database.db")

# Create a cursor
cursor = conn.cursor()

# Retrieve the existing table's schema if it exists
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='miner_details'")
existing_schema = cursor.fetchone()

# Define the desired new schema
new_schema = """
    CREATE TABLE IF NOT EXISTS miner_details (
        id INTEGER PRIMARY KEY,
        hotkey TEXT,
        difficulty INTEGER,
        time_elapsed INTEGER,
        verified BOOLEAN,
    )
"""

# Compare the schemas
if existing_schema is not None and existing_schema[0] != new_schema:
    # Drop the existing table if the schemas are different
    cursor.execute("DROP TABLE miner_details")
    bt.logging.info(f"Migration needed : Existing table dropped.")

    # Create the new table with the new schema
    cursor.execute(new_schema)
    bt.logging.info(f"Migration done : New table created.")

    # Commit changes and close the connection
    conn.commit()
    bt.logging.info(f"Applying the changes.")


# Fetch hotkeys from database that meets device_requirement
def select_miners_hotkey(requirement):
    try:
        # Fetch all records from miner_details table
        cursor.execute(new_schema)
        cursor.execute("SELECT * FROM miner_details")
        rows = cursor.fetchall()

        # Check if the miner meets device_requirement
        hotkey_list = []
        for row in rows:
            difficulty = row[2]
            time_elapsed = row[3]
            verified = row[4]
            if difficulty >= requirement.get("difficulty") and time_elapsed < requirement.get("time_elapsed") and verified == requirement.get("verified"):
                hotkey_list.append(row[1])
        return hotkey_list
    except Exception as e:
        bt.logging.error(f"Error while getting hotkeys from miner_details : {e}")
        return []


#  Update the miner_details with challenge details
def update(uids_details: dict):
    try:
        cursor.execute(f"DELETE FROM miner_details")
        for uid, details in uids_details.items():
            cursor.execute(
                "INSERT INTO miner_details (hotkey, difficulty, time_elapsed, verified) VALUES (?, ?, ?, ?)",
                (
                    details.get("axon").hotkey,
                    details.get("difficulty"),
                    details.get("time_elapsed"),
                    details.get("verified"),
                ),
            )
        conn.commit()
    except Exception as e:
        bt.logging.error(f"Error while updating miner_details : {e}")
