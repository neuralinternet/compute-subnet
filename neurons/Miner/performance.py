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
import igpu
import GPUtil
import cpuinfo as cpuinfo
import bittensor as bt

#The following function is responsible for providing gpu information
def gpu_info():
    try:
        #Count of existing gpus
        gpu_count = igpu.count_devices()

        #Get the detailed information for each gpu (name, capacity)
        gpu_details = []
        if gpu_count != 0:
            gpus = GPUtil.getGPUs()
            for i, gpu in enumerate(gpus):
                gpu_details.append({"name" : gpu.name, "memoryTotal" : gpu.memoryTotal, "memoryUsed" : gpu.memoryUsed, "load" : gpu.load})
        return {"count":gpu_count, "details": gpu_details}
    except Exception as e:
        #bt.logging.info(f"An error occurred: {e}")
        return {"count":0}

#The following function is responsible for providing cpu information
def cpu_info():
    try:
        info = {}
    
        # Create an instance of the CpuInfo class
        cpu_info = cpuinfo.get_cpu_info()

        # Get various CPU details
        info["vendor_id_raw"] = cpu_info["vendor_id_raw"]
        info["brand_raw"] = cpu_info["brand_raw"]
        info["hz_advertised_friendly"] = cpu_info["hz_advertised_friendly"]
        info["arch"] = cpu_info["arch"]
        info["bits"] = cpu_info["bits"]
        info["count"] = cpu_info["count"]
        return info
    except Exception as e:
        #bt.logging.info(f"An error occurred: {e}")
        return {"count":0}

#The following function is responsible for providing hard disk information on windows
def hard_disk_info_windows():
    try:
        w = wmi.WMI()
        result = []
        for disk in w.Win32_DiskDrive():
            result.append({'capacity_gb':int(disk.Size) * 1.0 / (1024**3), 'model': disk.Model, 'status' : disk.Status})
        return result
    except Exception as e:
        bt.logging.info(f"Error: {e}")
    return None


#The following function is responsible for providing hard disk info on linux
def get_hard_disk_info_linux(device):
    try:
        result = subprocess.run(['smartctl', '-i', device], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        bt.logging.info(f"Could not retrieve information for {device}")

#The following function is responsible for providing ram information on windows
def get_ram_info_windows():
    try:
        ram_speed = get_ram_speed_windows()
        memory_info = psutil.virtual_memory()
        capacity_gb = memory_info.total / (1024**3)  # Convert to gigabytes
        used_gb = memory_info.used / (1024**3)
        return {capacity_gb, used_gb, ram_speed}
    except Exception as e:
        bt.logging.info(f"Error: {e}")
    return None

#The following function is responsible for providing ram speed on windows
def get_ram_speed_windows():
    try:
        w = wmi.WMI()
        for memory in w.Win32_PhysicalMemory():
            return memory.ConfiguredClockSpeed
    except Exception as e:
        bt.logging.info(f"Error: {e}")
    return None

#The following function is responsible for providing ram speed on windows
def get_ram_info_linux():
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError:
        bt.logging.info("Could not retrieve RAM information.")
