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

from compute.utils.cache import ttl_cache

bt_blocktime = bt.__blocktime__


@ttl_cache(maxsize=1, ttl=bt_blocktime)
def get_current_block(subtensor: bt.subtensor) -> int:
    return subtensor.block


@ttl_cache(maxsize=1, ttl=bt_blocktime)
def is_registered(wallet: bt.wallet, metagraph: bt.metagraph, subtensor: bt.subtensor, entity: str = "validator"):
    if wallet.hotkey.ss58_address not in metagraph.hotkeys:
        bt.logging.error(f"\nYour {entity}: {wallet} is not registered to chain connection: {subtensor} \nRun btcli register and try again.")
        exit(1)
    else:
        # Each miner gets a unique identity (UID) in the network for differentiation.
        my_subnet_uid = metagraph.hotkeys.index(wallet.hotkey.ss58_address)
        bt.logging.info(f"Running {entity} on uid: {my_subnet_uid}")
        return my_subnet_uid


def calculate_next_block_time(block_origin, block_destiny) -> datetime.timedelta:
    return datetime.timedelta(seconds=(block_destiny - block_origin) * bt_blocktime)
