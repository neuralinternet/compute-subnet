# The MIT License (MIT)
# Copyright © 2023 GitPhantom

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.
# Step 1: Import necessary libraries and modules
import string
import secrets
import bcrypt
import sqlite3
import random
import bittensor as bt

# Connect to the database (or create it if it doesn't exist)
conn = sqlite3.connect('database.db')

# Create a cursor
cursor = conn.cursor()

# Create a table
cursor.execute('CREATE TABLE IF NOT EXISTS hash_tb (id INTEGER PRIMARY KEY, origin_str TEXT, hashed_str TEXT, hash_count INTEGER)')

# This function is responsible for generating the str randomly.
def generate_random_str(hash_count, str_length):
    alphabet = string.ascii_letters + string.digits  # You can customize this as needed
    random_str = ''.join(secrets.choice(alphabet) for _ in range(str_length))

    hashed_str = random_str.encode('utf-8')
    for index in range(hash_count):
        hashed_str = bcrypt.hashpw(hashed_str, b'$2b$12$9/zKmaaYPld3zfuC.Kb.Qe')
    hashed_str = hashed_str.decode('utf-8')

    insert_str_to_db(random_str, hashed_str, hash_count)
    return {'origin_str': random_str, 'hashed_str': hashed_str}


# This function is responsible for generating the str.
def select_str_list(str_count, complexity):
    #Fetch hash_count strings from database
    cursor.execute("SELECT * FROM hash_tb where hash_count = ? limit ?", (complexity, str_count))
    rows = cursor.fetchall()
    row_count = len(rows)

    #Calculate missing count of string compared with str_count
    missing_count = max(str_count - row_count, 0)

    #Generate strings with generate_random_str
    origin_str_list = []
    hashed_str_list = []

    new_count = 0

    if random.random() >= 0.7:
        new_count += random.randint(0, 3)

    count_new_generation = min(missing_count + new_count, str_count)
    for index in range(count_new_generation):
        pair_str = generate_random_str(complexity, 10)
        origin_str_list.append(pair_str['origin_str'])
        hashed_str_list.append(pair_str['hashed_str'])
    
    #Fetch strings from database and add them to selected string list
    while len(origin_str_list) < str_count:
        row_i = rows[random.randint(0, row_count - 1)]
        origin_str_list.append(row_i[1])
        hashed_str_list.append(row_i[2])

    return {'origin' : origin_str_list, 'hashed' : hashed_str_list}

# This function is responsible for inserting the str to db.
def insert_str_to_db(origin_str, hashed_str, hash_count):
    # Insert data
    cursor.execute("INSERT INTO hash_tb (origin_str, hashed_str, hash_count) VALUES (?, ?, ?)", (origin_str, hashed_str, hash_count))


# This function is responsible for evaluating the hashed_str with the database
def evaluate(original_list, result_str_list):
    answer_str_list = original_list['str_list']
    complexity = original_list['complexity']

    right_count = 0.0
    for i, answer_i in enumerate(answer_str_list):
        if answer_i == result_str_list[i]:
            right_count += complexity
    return right_count
