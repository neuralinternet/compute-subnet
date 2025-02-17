1. **Score Calculation Function:**
    - The `score` function aggregates performance data from different hardware components.
    - It calculates individual scores for CPU, GPU, hard disk, and RAM.
    - These scores are then weighted and summed to produce a total score.
    - A registration bonus is applied if the miner is registered, enhancing the total score.

2. **Component-Specific Scoring Functions:**
    - `get_cpu_score`, `get_gpu_score`, `get_hard_disk_score`, and `get_ram_score` are functions dedicated to
      calculating scores for each respective hardware component.
    - These functions consider the count, frequency, capacity, and speed of each component, applying a specific level
      value for normalization.
    - The scores are derived based on the efficiency and capacity of the hardware.

3. **Weight Assignment:**
    - The script defines weights for each hardware component's score, signifying their importance in the overall
      performance.
    - GPU has the highest weight (0.55), reflecting its significance in mining operations.
    - CPU, hard disk, and RAM have lower weights (0.2, 0.1, and 0.15, respectively).

4. **Registration Check:**
    - The `check_if_registered` function verifies if a miner is registered using an external API (`wandb.Api()`).
    - Registered miners receive a bonus to their total score, incentivizing official registration in the network.

5. **Score Aggregation:**
    - The individual scores are combined into a numpy array, `score_list`.
    - The weights are also arranged in an array, `weight_list`.
    - The final score is calculated using a dot product of these arrays, multiplied by 10, and then adjusted with the
      registration bonus.

6. **Handling Multiple CPUs/GPUs:**
    - The scoring functions for CPUs (`get_cpu_score`) and GPUs (`get_gpu_score`) are designed to process data that can
      represent multiple units.
    - For CPUs, the `count` variable in `cpu_info` represents the number of CPU cores or units available. The score is
      calculated based on the cumulative capability, taking into account the total count and frequency of all CPU cores.
    - For GPUs, similar logic applies. The script can handle data representing multiple GPUs, calculating a cumulative
      score based on their collective capacity and speed.

7. **CPU Scoring (Multiple CPUs):**
    - The CPU score is computed by multiplying the total number of CPU cores (`count`) by their average
      frequency (`frequency`), normalized against a predefined level.
    - This approach ensures that configurations with multiple CPUs are appropriately rewarded for their increased
      processing power.

8. **GPU Scoring (Multiple GPUs):**
    - The GPU score is calculated by considering the total capacity (`capacity`) and the average speed (average
      of `graphics_speed` and `memory_speed`) of all GPUs in the system.
    - The score reflects the aggregate performance capabilities of all GPUs, normalized against a set level.
    - This method effectively captures the enhanced computational power provided by multiple GPU setups.

9. **Aggregated Performance Assessment:**
    - The final score calculation in the `score` function integrates the individual scores from CPU, GPU, hard disk, and
      RAM.
    - This integration allows the scoring system to holistically assess the collective performance of all hardware
      components, including scenarios with multiple CPUs and GPUs.

10. **Implications for Miners:**

- Miners with multiple GPUs and/or CPUs stand to gain a higher score due to the cumulative calculation of their
  hardware's capabilities.
- This approach incentivizes miners to enhance their hardware setup with additional CPUs and GPUs, thereby contributing
  more processing power to the network.

The weight assignments are as follows:

- **GPU Weight:** 0.55
- **CPU Weight:** 0.2
- **Hard Disk Weight:** 0.1
- **RAM Weight:** 0.15

### Example 1: Miner A's Hardware Scores and Weighted Total

1. **CPU Score:** Calculated as `(2 cores * 3.0 GHz) / 1024 / 50`.
2. **GPU Score:** Calculated as `(8 GB * (1 GHz + 1 GHz) / 2) / 200000`.
3. **Hard Disk Score:** Calculated as `(500 GB * (100 MB/s + 100 MB/s) / 2) / 1000000`.
4. **RAM Score:** Calculated as `(16 GB * 2 GB/s) / 200000`.

Now, applying the weights:

- Total Score = (CPU Score × 0.2) + (GPU Score × 0.55) + (Hard Disk Score × 0.1) + (RAM Score × 0.15)
- If registered, add a registration bonus.

### Example 2: Miner B's Hardware Scores and Weighted Total

1. **CPU Score:** Calculated as `(4 cores * 2.5 GHz) / 1024 / 50`.
2. **GPU Score:** Calculated as `((6 GB + 6 GB) * (1.5 GHz + 1.2 GHz) / 2) / 200000`.
3. **Hard Disk Score:** Calculated as `(1 TB * (200 MB/s + 150 MB/s) / 2) / 1000000`.
4. **RAM Score:** Calculated as `(32 GB * 3 GB/s) / 200000`.

Applying the weights:

- Total Score = (CPU Score × 0.2) + (GPU Score × 0.55) + (Hard Disk Score × 0.1) + (RAM Score × 0.15)
- Since Miner B is not registered, no registration bonus is added.

### Impact of Weights on Total Score

- The GPU has the highest weight (0.55), signifying its paramount importance in mining tasks, which are often
  GPU-intensive. Miners with powerful GPUs will thus receive a significantly higher portion of their total score from
  the GPU component.
- The CPU, while important, has a lower weight (0.2), reflecting its lesser but still vital role in the mining process.
- The hard disk and RAM have the lowest weights (0.1 and 0.15, respectively), indicating their supportive but less
  critical roles compared to GPU and CPU.

It is important to note that the role of validators, in contrast to miners, does not require the integration of GPU
instances. Their function revolves around data integrity and accuracy verification, involving relatively modest network
traffic and lower computational demands. As a result, their hardware requirements are less intensive, focusing more on
stability and reliability rather than high-performance computation.
