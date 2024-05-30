import socket
import threading
import json
import os

clients = {}
files = {}

def handle_client(client_socket, client_address):
    try:
        while True:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                break

            request = json.loads(message)
            action = request.get("action")
            
            if action == "authenticate":
                handle_authentication(client_socket, request)
            elif action == "publish_files":
                handle_publish_files(client_socket, request)
            elif action == "request_file":
                handle_request_file(client_socket, request)
            elif action == "send_file_content":
                handle_send_file_content(client_socket, request)
            elif action == "end_session":
                handle_end_session(client_socket, request)
                break
            elif action == "notify":
                handle_notify(client_socket, request)
    finally:
        handle_client_disconnect(client_socket)

def handle_authentication(client_socket, request):
    username = request.get("username")
    user_files = request.get("files")
    if username and user_files:
        clients[username] = client_socket
        files[username] = user_files

        all_files = {user: files_list for user, files_list in files.items() if user != username}
        response = {"status": "authenticated", "files": all_files}
        client_socket.send(json.dumps(response).encode('utf-8'))

        notify_all_clients(f"User {username} has joined with files {user_files}", client_socket)

def handle_publish_files(client_socket, request):
    username = request.get("username")
    user_files = request.get("files")
    if username and user_files:
        files[username] = user_files
        notify_all_clients(f"User {username} has published new files: {user_files}", client_socket)

def handle_request_file(client_socket, request):
    file_owner = request.get("owner")
    file_name = request.get("file")
    requesting_user = request.get("username")
    if file_owner in clients:
        owner_socket = clients[file_owner]
        owner_socket.send(json.dumps({"action": "send_file_content", "requester": requesting_user, "file": file_name}).encode('utf-8'))
    else:
        client_socket.send(json.dumps({"error": "File owner not found."}).encode('utf-8'))

def handle_send_file_content(client_socket, request, directory="."):
    file_name = request.get("file")
    requesting_user = request.get("requester")
    if file_name and requesting_user in clients:
        try:
            file_path = os.path.join(directory, file_name)
            with open(file_path, 'rb') as f:
                file_content = f.read()
            response = {"action": "deliver_file", "file": file_name, "content": file_content.decode('latin1')}
            clients[requesting_user].send(json.dumps(response).encode('utf-8'))
        except FileNotFoundError:
            error_message = f"File {file_name} not found."
            clients[requesting_user].send(json.dumps({"error": error_message}).encode('utf-8'))

def handle_notify(client_socket, request):
    notification = request.get("notification")
    notify_all_clients(notification, client_socket)

def handle_end_session(client_socket, request):
    username = request.get("username")
    if username in clients:
        response = {"status": "session_ended"}
        client_socket.send(json.dumps(response).encode('utf-8'))
        del clients[username]
        del files[username]
        notify_all_clients(f"User {username} has disconnected", client_socket)

def handle_client_disconnect(client_socket):
    for username, socket in list(clients.items()):
        if socket == client_socket:
            del clients[username]
            del files[username]
            notify_all_clients(f"User {username} has disconnected", client_socket)
            break

def notify_all_clients(message, exclude_socket=None):
    for client_socket in clients.values():
        if client_socket != exclude_socket:
            client_socket.send(json.dumps({"notification": message}).encode('utf-8'))

def start_server():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("0.0.0.0", 5000))
    server.listen(5)
    print("Server started on port 5000")

    while True:
        client_socket, client_address = server.accept()
        print(f"Accepted connection from {client_address}")
        client_handler = threading.Thread(target=handle_client, args=(client_socket, client_address))
        client_handler.start()

if __name__ == "__main__":
    start_server()
