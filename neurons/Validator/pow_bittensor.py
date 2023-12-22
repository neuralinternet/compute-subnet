import math
import multiprocessing
import time
from queue import Empty
from typing import List, Optional, Union

import bittensor
import torch
from bittensor.utils.registration import (
    POWSolution,
    _UsingSpawnStartMethod,
    _CUDASolver,
    _get_block_with_retry,
    _update_curr_block,
    RegistrationStatistics,
    RegistrationStatisticsLogger,
    _check_for_newest_block_and_update,
    _terminate_workers_and_wait_for_exit,
)


def _solve_for_difficulty_fast_cuda(
    subtensor: "bittensor.subtensor",
    wallet: "bittensor.wallet",
    netuid: int,
    output_in_place: bool = True,
    update_interval: int = 50_000,
    tpb: int = 512,
    dev_id: Union[List[int], int] = 0,
    n_samples: int = 10,
    alpha_: float = 0.80,
    log_verbose: bool = False,
) -> Optional[POWSolution]:
    """
    Solves the registration fast using CUDA
    Args:
        subtensor: bittensor.subtensor
            The subtensor node to grab blocks
        wallet: bittensor.wallet
            The wallet to register
        netuid: int
            The netuid of the subnet to register to.
        output_in_place: bool
            If true, prints the output in place, otherwise prints to new lines
        update_interval: int
            The number of nonces to try before checking for more blocks
        tpb: int
            The number of threads per block. CUDA param that should match the GPU capability
        dev_id: Union[List[int], int]
            The CUDA device IDs to execute the registration on, either a single device or a list of devices
        n_samples: int
            The number of samples of the hash_rate to keep for the EWMA
        alpha_: float
            The alpha for the EWMA for the hash_rate calculation
        log_verbose: bool
            If true, prints more verbose logging of the registration metrics.
    Note: The hash rate is calculated as an exponentially weighted moving average in order to make the measure more robust.
    """
    if isinstance(dev_id, int):
        dev_id = [dev_id]
    elif dev_id is None:
        dev_id = [0]

    if update_interval is None:
        update_interval = 50_000

    if not torch.cuda.is_available():
        raise Exception("CUDA not available")

    limit = int(math.pow(2, 256)) - 1

    # Set mp start to use spawn so CUDA doesn't complain
    with _UsingSpawnStartMethod(force=True):
        curr_block, curr_block_num, curr_diff = _CUDASolver.create_shared_memory()

        ## Create a worker per CUDA device
        num_processes = len(dev_id)

        # Establish communication queues
        stopEvent = multiprocessing.Event()
        stopEvent.clear()
        solution_queue = multiprocessing.Queue()
        finished_queues = [multiprocessing.Queue() for _ in range(num_processes)]
        check_block = multiprocessing.Lock()

        hotkey_bytes = wallet.hotkey.public_key
        # Start workers
        solvers = [
            _CUDASolver(
                i,
                num_processes,
                update_interval,
                finished_queues[i],
                solution_queue,
                stopEvent,
                curr_block,
                curr_block_num,
                curr_diff,
                check_block,
                limit,
                dev_id[i],
                tpb,
            )
            for i in range(num_processes)
        ]

        # Get first block
        block_number, difficulty, block_hash = _get_block_with_retry(subtensor=subtensor, netuid=netuid)

        difficulty = 4
        block_bytes = bytes.fromhex(block_hash[2:])
        old_block_number = block_number

        # Set to current block
        _update_curr_block(
            curr_diff,
            curr_block,
            curr_block_num,
            block_number,
            block_bytes,
            difficulty,
            hotkey_bytes,
            check_block,
        )

        # Set new block events for each solver to start at the initial block
        for worker in solvers:
            worker.newBlockEvent.set()

        for worker in solvers:
            worker.start()  # start the solver processes

        start_time = time.time()  # time that the registration started
        time_last = start_time  # time that the last work blocks completed

        curr_stats = RegistrationStatistics(
            time_spent_total=0.0,
            time_average=0.0,
            rounds_total=0,
            time_spent=0.0,
            hash_rate_perpetual=0.0,
            hash_rate=0.0,  # EWMA hash_rate (H/s)
            difficulty=difficulty,
            block_number=block_number,
            block_hash=block_hash,
        )

        start_time_perpetual = time.time()

        console = bittensor.__console__
        logger = RegistrationStatisticsLogger(console, output_in_place)
        logger.start()

        hash_rates = [0] * n_samples  # The last n true hash_rates
        weights = [alpha_**i for i in range(n_samples)]  # weights decay by alpha

        solution = None
        while netuid == -1:
            # Wait until a solver finds a solution
            try:
                solution = solution_queue.get(block=True, timeout=0.15)
                if solution is not None:
                    break
            except Empty:
                # No solution found, try again
                pass

            # check for new block
            old_block_number = _check_for_newest_block_and_update(
                subtensor=subtensor,
                netuid=netuid,
                hotkey_bytes=hotkey_bytes,
                curr_diff=curr_diff,
                curr_block=curr_block,
                curr_block_num=curr_block_num,
                old_block_number=old_block_number,
                curr_stats=curr_stats,
                update_curr_block=_update_curr_block,
                check_block=check_block,
                solvers=solvers,
            )

            num_time = 0
            # Get times for each solver
            for finished_queue in finished_queues:
                try:
                    proc_num = finished_queue.get(timeout=0.1)
                    num_time += 1

                except Empty:
                    continue

            time_now = time.time()  # get current time
            time_since_last = time_now - time_last  # get time since last work block(s)
            if num_time > 0 and time_since_last > 0.0:
                # create EWMA of the hash_rate to make measure more robust

                hash_rate_ = (num_time * tpb * update_interval) / time_since_last
                hash_rates.append(hash_rate_)
                hash_rates.pop(0)  # remove the 0th data point
                curr_stats.hash_rate = sum([hash_rates[i] * weights[i] for i in range(n_samples)]) / (sum(weights))

                # update time last to now
                time_last = time_now

                curr_stats.time_average = (curr_stats.time_average * curr_stats.rounds_total + curr_stats.time_spent) / (curr_stats.rounds_total + num_time)
                curr_stats.rounds_total += num_time

            # Update stats
            curr_stats.time_spent = time_since_last
            new_time_spent_total = time_now - start_time_perpetual
            curr_stats.hash_rate_perpetual = (curr_stats.rounds_total * (tpb * update_interval)) / new_time_spent_total
            curr_stats.time_spent_total = new_time_spent_total

            # Update the logger
            logger.update(curr_stats, verbose=log_verbose)

        # exited while, found_solution contains the nonce or wallet is registered

        stopEvent.set()  # stop all other processes
        logger.stop()

        # terminate and wait for all solvers to exit
        _terminate_workers_and_wait_for_exit(solvers)

        return solution


def proof_of_work(subtensor, wallet, netuid=27):
    print(_solve_for_difficulty_fast_cuda(subtensor=subtensor, wallet=wallet, netuid=27))


if __name__ == "__main__":
    proof_of_work()
