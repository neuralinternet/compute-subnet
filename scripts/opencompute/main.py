# Streamlit main script
import streamlit as st
import pandas as pd
import requests

# Configure the page to use wide layout
st.set_page_config(page_title="Opencompute", layout="wide", page_icon="icon.ico")

# Server details, insert the server IP and port
SERVER_IP = "opencompute-backend"
SERVER_PORT = "8316"
SERVER_URL = f"http://{SERVER_IP}:{SERVER_PORT}"

def get_data_from_server(endpoint):
    response = requests.get(f"{SERVER_URL}/{endpoint}")
    if response.status_code == 200:
        return response.json()
    else:
        return {}

def display_hardware_specs(specs_details, allocated_keys, penalized_keys):
    # Compute all necessary data before setting up the tabs
    column_headers = ["UID", "Hotkey", "GPU Name", "GPU Capacity (GiB)", "GPU Count", "CPU Count", "RAM (GiB)", "Disk Space (GiB)", "Status", "Conformity"]
    table_data = []

    gpu_instances = {}
    total_gpu_counts = {}

    for index in sorted(specs_details.keys()):
        hotkey = specs_details[index]['hotkey']
        details = specs_details[index]['details']
        if details:
            try:
                gpu_miner = details['gpu']
                gpu_capacity = "{:.2f}".format(gpu_miner['capacity'] / 1024)  # Capacity is in MiB
                gpu_name = str(gpu_miner['details'][0]['name']).lower()
                gpu_count = gpu_miner['count']

                cpu_miner = details['cpu']
                cpu_count = cpu_miner['count']

                ram_miner = details['ram']
                ram = "{:.2f}".format(ram_miner['available'] / 1024.0 ** 3)  # Convert bytes to GiB

                hard_disk_miner = details['hard_disk']
                hard_disk = "{:.2f}".format(hard_disk_miner['free'] / 1024.0 ** 3)  # Convert bytes to GiB

                status = "Res." if hotkey in allocated_keys else "Avail."
                conform = "No" if hotkey in penalized_keys else "Yes"

                row = [str(index), hotkey[:6] + ('...'), gpu_name, gpu_capacity, str(gpu_count), str(cpu_count), ram, hard_disk, status, conform]

                # Update summaries for GPU instances and total counts
                if isinstance(gpu_name, str) and isinstance(gpu_count, int):
                    row = [str(index), hotkey[:6] + ('...'), gpu_name, gpu_capacity, str(gpu_count), str(cpu_count), ram, hard_disk, status, conform]
                    gpu_key = (gpu_name, gpu_count)
                    gpu_instances[gpu_key] = gpu_instances.get(gpu_key, 0) + 1
                    total_gpu_counts[gpu_name] = total_gpu_counts.get(gpu_name, 0) + gpu_count
                else:
                    row = [str(index), hotkey[:6] + ('...'), "No GPU data"] + ["N/A"] * 7

            except (KeyError, IndexError, TypeError):
                row = [str(index), hotkey[:6] + ('...'), "Invalid details"] + ["N/A"] * 7
        else:
            row = [str(index), hotkey[:6] + ('...'), "No details available"] + ["N/A"] * 7

        table_data.append(row)

    # Display the tabs
    tab1, tab2, tab3 = st.tabs(["Hardware Overview", "Instances Summary", "Total GPU Counts"])

    with tab1:
        df = pd.DataFrame(table_data, columns=column_headers)
        st.table(df)

    with tab2:
        summary_data = [[gpu_name, str(gpu_count), str(instances)] for (gpu_name, gpu_count), instances in gpu_instances.items()]
        if summary_data:
            st.table(pd.DataFrame(summary_data, columns=["GPU Name", "GPU Count", "Instances Count"]))

    with tab3:
        summary_data = [[name, str(count)] for name, count in total_gpu_counts.items()]
        if summary_data:
            st.table(pd.DataFrame(summary_data, columns=["GPU Name", "Total GPU Count"]))

# Streamlit App Layout
st.title('Compute Subnet - Hardware Specifications')

# Fetching data from external server
with st.spinner('Fetching data from server...'):
    try:
        hotkeys_response = get_data_from_server("keys")
        hotkeys = hotkeys_response.get("keys", [])

        specs_response = get_data_from_server("specs")
        specs_details = specs_response.get("specs", {})

        allocated_keys_response = get_data_from_server("allocated_keys")
        allocated_keys = allocated_keys_response.get("allocated_keys", [])

        penalized_keys_response = get_data_from_server("penalized_keys")
        penalized_keys = penalized_keys_response.get("penalized_keys", [])

    except:
        print("Error: ConnectionError")

# Display fetched hardware specs
try:
    display_hardware_specs(specs_details, allocated_keys, penalized_keys)
except:
    st.write("Unable to connect to the server. Please try again later.")
    print("Error: ConnectionError occurred while attempting to connect to the server.")

