import http.server
import socketserver
from socketserver import TCPServer
import threading

def start_server(port) -> TCPServer:
    handler = http.server.SimpleHTTPRequestHandler
    httpd: TCPServer = socketserver.TCPServer(("", int(port)), handler)
    
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return httpd

def stop_server(httpd: TCPServer) -> None:
    httpd.shutdown()