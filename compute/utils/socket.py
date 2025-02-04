import bittensor as bt
import socket

def check_port(host, port):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(1)  # Set a timeout for the connection attempt
            result = sock.connect_ex((host, port))
            if result == 0:
                return True
            else:
                return False
    except socket.gaierror:
        bt.logging.warning(f"API: Hostname {host} could not be resolved")
        return None
    except socket.error:
        bt.logging.error(f"API: Couldn't connect to server {host}")
        return None
