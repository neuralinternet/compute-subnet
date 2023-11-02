# The MIT License (MIT)
# Copyright © 2023 Crazydevlegend

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
import psutil
import igpu

#Return the detailed information of cpu
def get_cpu_info():
    try:
        # Get the number of physical CPU cores
        physical_cores = psutil.cpu_count(logical=False)

        # Get CPU frequency
        cpu_frequency = psutil.cpu_freq()

        info = {}
        info["count"] = physical_cores
        info["frequency"] = cpu_frequency.current

        usage_info = {}

        # Get CPU usage for each core
        cpu_percent = psutil.cpu_percent(interval=1, percpu=True)

        for core, usage in enumerate(cpu_percent):
            usage_info[str(core)] = usage

        info["usage"] = usage_info

        return info
    except Exception as e:
        #print(f"Error getting cpu information : {e}")
        return {}

#Return the detailed information of gpu
def get_gpu_info():
    try:
        #Count of existing gpus
        gpu_count = igpu.count_devices()

        #Get the detailed information for each gpu (name, capacity)
        gpu_details = []
        capacity = 0
        for i in range(gpu_count):
            gpu = igpu.get_device(i)
            gpu_details.append({"name" : gpu.name, "capacity" : gpu.memory.total, "utilization" : gpu.utilization.gpu})
            capacity += gpu.memory.total
        return {"count":gpu_count, "capacity": capacity, "details": gpu_details}
            
    except Exception as e:
        #print(f"Error getting cpu information : {e}")
        return {}

#Return the detailed information of hard disk
def get_hard_disk_info():
    try:

        usage = psutil.disk_usage("/")
        info = {"total": usage.total, "free": usage.free, "used": usage.used}

        partition_info = []
        partitions = psutil.disk_partitions(all=True)
        for partition in partitions:
            try:
                usage = psutil.disk_usage(partition.device)
                partition_info.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free
                })
            except Exception as e:
                #print(f"Error getting disk information for {partition.device}: {e}")
                continue

        info["partition"] = partition_info
        
        return info
    except Exception as e:
        #print(f"Error getting disk information {e}")
        return {}
    
#Return the detailed information of ram
def get_ram_info():
    try:
        virtual_memory = psutil.virtual_memory()
        swap_memory = psutil.swap_memory()

        info = {
            "total": virtual_memory.total,
            "available": virtual_memory.available,
            "used": virtual_memory.used,
            "free": virtual_memory.free,
            "swap_total": swap_memory.total,
            "swap_used": swap_memory.used,
            "swap_free": swap_memory.free
        }

        return info
    except Exception as e:
        #print(f"Error getting ram information {e}")
        return {}

def get_perf_info():
    cpu_info = get_cpu_info()
    gpu_info = get_gpu_info()
    hard_disk_info = get_hard_disk_info()
    ram_info = get_ram_info()

    return {"cpu" : cpu_info, "gpu" : gpu_info, "hard_disk" : hard_disk_info, "ram" : ram_info}

if __name__ == "__main__":
    print(f"{get_perf_info()}")