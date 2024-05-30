import socket
import threading
import json
import os

directory = ""

def receive_notifications(client_socket):
    while True:
        try:
            message = client_socket.recv(4096).decode('utf-8')
            if message:
                response = json.loads(message)
                handle_server_response(response, client_socket)
        except ConnectionResetError:
            break

def handle_server_response(response, client_socket):
    if "notification" in response:
        print(f"Notification: {response['notification']}")
    elif "action" in response:
        if response["action"] == "deliver_file":
            file_name = response["file"]
            file_content = response["content"]
            try:
                file_content_bytes = file_content.encode('latin1')
                file_path = os.path.join(directory, file_name)
                with open(file_path, 'wb') as f:
                    f.write(file_content_bytes)
                print(f"File {file_name} received and saved at {file_path}")
            except IOError as e:
                print(f"Error saving file: {e}")
        elif response["action"] == "send_file_content":
            file_name = response["file"]
            requester = response["requester"]
            send_file_content(file_name, requester, client_socket)

def send_file_content(file_name, requester, client_socket):
    try:
        file_path = os.path.join(directory, file_name)
        with open(file_path, 'rb') as f:
            file_content = f.read()
        file_content_str = file_content.decode('latin1')
        response = {"action": "deliver_file", "file": file_name, "content": file_content_str}
        client_socket.send(json.dumps(response).encode('utf-8'))
        print(f"File {file_name} sent to {requester}")
    except FileNotFoundError:
        error_message = f"File {file_name} not found."
        client_socket.send(json.dumps({"error": error_message}).encode('utf-8'))

def monitor_directory(dir_to_monitor, client_socket, username):
    before = dict([(f, None) for f in os.listdir(dir_to_monitor)])
    while True:
        after = dict([(f, None) for f in os.listdir(dir_to_monitor)])
        added = [f for f in after if not f in before]
        removed = [f for f in before if not f in after]
        if added:
            for f in added:
                client_socket.send(json.dumps({"action": "publish_files", "username": username, "files": [f]}).encode('utf-8'))
        if removed:
            for f in removed:
                client_socket.send(json.dumps({"action": "notify", "notification": f"File {f} was removed by {username}"}).encode('utf-8'))
        before = after

def start_client(username, dir_to_monitor):
    global directory
    directory = dir_to_monitor
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect(("127.0.0.1", 5000))

    files = os.listdir(directory)
    client_socket.send(json.dumps({"action": "authenticate", "username": username, "files": files}).encode('utf-8'))
    
    response = json.loads(client_socket.recv(4096).decode('utf-8'))
    if response.get("status") == "authenticated":
        print("Authenticated successfully.")
        print("Files shared by other users:")
        for user, user_files in response.get("files", {}).items():
            print(f"{user}: {user_files}")
    
    print("\nWelcome to the file sharing client!")
    print("Available commands:")
    print("  request <username> <filename>  - Request a file from another user")
    print("  exit                            - End the session and exit\n")

    threading.Thread(target=receive_notifications, args=(client_socket,)).start()
    threading.Thread(target=monitor_directory, args=(directory, client_socket, username)).start()

    while True:
        command = input(f"{username}@client> ")
        if command.startswith("request"):
            _, file_owner, file_name = command.split()
            print(f"Sending file request to server for file {file_name} owned by {file_owner}")
            client_socket.send(json.dumps({"action": "request_file", "owner": file_owner, "file": file_name, "username": username}).encode('utf-8'))
        elif command == "exit":
            client_socket.send(json.dumps({"action": "end_session", "username": username}).encode('utf-8'))
            response = client_socket.recv(4096).decode('utf-8')
            if response:
                try:
                    response_json = json.loads(response)
                    if response_json.get("status") == "session_ended":
                        print("Session ended successfully.")
                except json.JSONDecodeError:
                    print("Received invalid JSON response during session end.")
            else:
                print("Received empty response during session end.")
            client_socket.close()
            break

if __name__ == "__main__":
    username = input("Enter your username: ")
    directory_to_monitor = input("Enter the directory to monitor: ")
    start_client(username, directory_to_monitor)

