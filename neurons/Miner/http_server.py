import http.server
import socketserver
from socketserver import TCPServer
import subprocess
import threading

def kill_process_on_port(port):
    # Find the process using the port
    find_process = f"lsof -t -i:{port}"
    try:
        process_id = subprocess.check_output(find_process, shell=True).strip()
        if process_id:
            # Kill the process using the port
            subprocess.run(f"kill -9 {process_id.decode()}", shell=True)
            print(f"Process on port {port} has been killed.")
        else:
            print(f"No process found using port {port}.")
    except subprocess.CalledProcessError:
        print(f"Port {port} is not in use.")        

def start_server(port) -> TCPServer:
    kill_process_on_port(port)
    
    handler = http.server.SimpleHTTPRequestHandler
    httpd: TCPServer = socketserver.TCPServer(("", int(port)), handler)
    
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return httpd

def stop_server(httpd: TCPServer) -> None:
    if httpd:
        httpd.shutdown()
        httpd.server_close() 
    