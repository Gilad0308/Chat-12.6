# Server for 12.6 chat project from "Gvahim" book.
# Auther: Gilad Moyal.

import socket
import select
import time
import ctypes

"""Represents every user (client) that joins the chat.
Described by:
name (string)
is_manager (boolean)
is_silenced (boolean)
"""


class User:
    def __init__(self, name=None, is_manager=False, is_silenced=False):
        self.name = name
        self.is_manager = is_manager
        self.is_silenced = is_silenced


"""
Represents every message that needs to be sent
Described by:
message (string)
recv_sockets (list of sockets) - the sockets that the message will be sent to them.
remove_recipient (boolean) - whether or not the message is a remove message (a message sent to the user after a manager 
        had removed him from the chat or if the user decided to quit).
"""


class Message:
    def __init__(self, message, recv_sockets, remove_recipient=False):
        self.message = message
        self.recv_sockets = recv_sockets
        self.remove_recipient = remove_recipient


MAX_BYTES = 100000  # The maximal size of every "chunk" of bytes sent threw the socket (6 digits)
MAX_NAME_LENGTH = 99  # The maximal length of the user's name (2 digits).
MAX_MESSAGE_LENGTH = 9999  # The maximal length of a message the user sends (4 digits).
MANAGER_SYMBOL = "@"  # The character that will be printed at the beginning of the manager's name

# Commands and their numbers:
CHAT_MESSAGE = 1
APPOINT_MANAGER = 2  # for managers only
REMOVE_FROM_CHAT = 3  # for managers only
SILENCE_USER = 4  # for managers only
PRIVATE_MESSAGE = 5
# Without a number and added data (only letters):
VIEW_MANAGERS = "view-managers"
QUIT = "quit"

users_dict = {}  # A dictionary in which the key is the id of the connected socket, and the value is a User object.
connected_client_sockets = []  # A list of sockets connected to the server.
messages_to_send = []  # A list of type Message - contains all the messages that need to be sent.
managers_names = []  # A list of the managers names.
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # AF_INET refers to ipv4, SOCK_STREAM refers to TCP


def main():
    server_socket.bind(('127.0.0.1', 1111))  # Binds the socket to address (ip, port).
    server_socket.listen(5)  # Waits for incoming connection requests

    while True:
        rlist, wlist, xlist = select.select([server_socket] + connected_client_sockets, connected_client_sockets, [])
        # Receives messages by readable sockets.
        # It can be a connection request, a regular message or disconnection request.
        for current_socket in rlist:
            handle_incoming_data(current_socket)
            # If there are no managers (if the chat just opened or if the last manager left the chat).
            if len(managers_names) == 0:
                automatic_manager_appointment()

        # Sends the messages to the writable sockets, that are recipients of the message. Removes the sockets and the
        # users that received a remove message.
        for message in messages_to_send:
            send_and_remove(wlist, message)


"""
Receives data that was sent by the client that contains a command number, and separates from it the user/s name/s, 
command and message (suitable to the command), according to the protocol.
Returns a tuple of these details, in the same order they appeared in the data.
If the data is without a command number (like "quit" and "view-managers"), returns just it.
"""
def extract_details_from_data(data):
    # Commands 1-5
    name_length = int(data[:len(str(MAX_NAME_LENGTH))])
    data = data[len(str(MAX_NAME_LENGTH)):]
    user_name = data[:name_length]
    data = data[name_length:]
    command = int(data[0])
    data = data[1:]

    if command == CHAT_MESSAGE:  # Command 1 - chat message
        message_length = int(data[:len(str(MAX_MESSAGE_LENGTH))])
        data = data[len(str(MAX_MESSAGE_LENGTH)):]
        message = data[:message_length]
        return user_name, command, message

    # Commands 2,3,4,5 - in all of them there is a name of another user
    second_name_length = int(data[:len(str(MAX_NAME_LENGTH))])
    data = data[len(str(MAX_NAME_LENGTH)):]
    second_name = data[:second_name_length]
    data = data[second_name_length:]
    if command != PRIVATE_MESSAGE:  # For commands 2,3,4 - they don't contain a message.
        return user_name, command, second_name

    # Command 5 - private message between users
    message_length = int(data[:len(str(MAX_MESSAGE_LENGTH))])
    data = data[len(str(MAX_MESSAGE_LENGTH)):]
    message = data[:message_length]
    return user_name, command, second_name, message


"""
Handles situations in which a message is sent to client/s.
Receives a list of writable sockets and a message (Message object), and sends it to those who are recipients of the message.
Removes from the list of users and sockets those that received a remove message (have been removed by a manager).
"""
def send_and_remove(wlist, message):
    for current_socket in message.recv_sockets:
        if current_socket in wlist:
            try:
                current_socket.send(message.message.encode())
            except OSError:
                pass
            message.recv_sockets.remove(current_socket)
            if message.remove_recipient is True:
                current_socket.close()
                connected_client_sockets.remove(current_socket)
                user_to_remove = users_dict[id(current_socket)]
                del users_dict[id(current_socket)]
                if user_to_remove.name in managers_names:
                    managers_names.remove(user_to_remove.name)

    if len(message.recv_sockets) == 0:
        messages_to_send.remove(message)


# Returns a string of the time in format: hours:minuts, and a space after it.
def str_time():
    t = time.localtime()
    current_time = time.strftime("%H:%M", t)
    return current_time + " "

"""
Handles situations in which a certain type of data is received. It can be a connection request, a regular message 
or disconnection request.
Receives the socket of the client, executes the requested command, if needed (for example, adds a user to the managers).
According to the protocol, prepares the message to be sent to the recipients.
"""
def handle_incoming_data(send_socket):
    # Connection request, received by the server's socket.
    if send_socket is server_socket:
        handle_connection_request()
        return
    # Regular or Disconnection message, received with the client's socket.
    try:
        data = send_socket.recv(MAX_BYTES).decode()
    except ConnectionResetError:  # If the user closes the program of the client.
        handle_disconnection(send_socket)
        return
    # Basic messages, without name and other details.
    if data == "quit":
        handle_disconnection(send_socket)
        return
    if data == "view-managers":
        prepare_managers_message(send_socket)
        return

    # Commands 1-5 - data with more details.
    details = extract_details_from_data(data)
    send_name = details[0]
    command = details[1]
    # Adds the name of the user if it's the first time he's sending data.
    if users_dict[id(send_socket)].name is None:
        users_dict[id(send_socket)].name = send_name

    # Command 1 - a chat message (checks the message isn't empty. If it is - the users won't get any message)
    if command == CHAT_MESSAGE:
        handle_chat_message(send_socket, send_name, details[2])

    # Commands 2-5 - involves two sockets.
    target_name = details[2]
    target_socket = socket_by_name(send_socket, send_name, target_name)
    if command == APPOINT_MANAGER:  # Command 2 - appoint manager
        handle_appoint_manager(send_socket, send_name, target_socket, target_name)
        return
    if command == REMOVE_FROM_CHAT:  # Command 3 - remove (disconnect) a user from the chat
        handle_remove(send_socket, send_name, target_socket, target_name)
        return
    if command == SILENCE_USER:  # Command 4 - silence a user.
        handle_silence_user(send_socket, send_name, target_socket, target_name)
        return
    if command == PRIVATE_MESSAGE:  # Command 5 - a private message
        message = details[3]
        handle_private_message(send_socket, send_name, target_socket, target_name, message)


# Receives the sending socket and prepares a message of the list of managers for this socket.
# Adds it to the list of messages to send.
def prepare_managers_message(send_socket):
    if len(managers_names) == 0:
        to_send = str_time() + " No managers yet"
        prepare_message_for_sending(to_send, [send_socket])
        return

    to_send = str_time() + "The manager/s of the chat is/are: "
    for name in managers_names:
        # In case the user that sent view-managers is a manager.
        if users_dict[id(send_socket)].name == name:
            to_send = to_send + "\nYou"
        else:
            to_send += "\n" + name
    prepare_message_for_sending(to_send, [send_socket])


"""
Receives the message to send, a list of sockets that should receive the message, and a boolean argument - 
whether or not the message is a removal message, and the recipient should be removed after the message has sent 
(optional, by default False). Prepares the message to the format it should be sent in according to the protocol, 
and adds it to the list of messages. 
"""
def prepare_message_for_sending(to_send, recv_sockets, remove_recipient=False):
    str_to_send_length = (len(str(MAX_BYTES)) - len(str(len(to_send)))) * "0" + str(len(to_send))
    to_send = str_to_send_length + to_send
    message = Message(to_send, recv_sockets, remove_recipient)
    messages_to_send.append(message)


"""
Handles situations in which the incoming data is a connection request.
Accepts the new socket, adds the user to the dictionary, creates the message to send to all the other users and
adds it to the list of messages to send.
"""
def handle_connection_request():
    print("Accepting a client.")
    (new_socket, address) = server_socket.accept()
    connected_client_sockets.append(new_socket)
    users_dict[id(new_socket)] = User()
    recv_sockets = connected_client_sockets.copy()
    recv_sockets.remove(new_socket)
    to_send = str_time() + "Someone joined the chat"
    print(to_send)
    prepare_message_for_sending(to_send, recv_sockets)


"""
Handles situations in which the incoming data is a disconnection request, or when the clients socket forcibly closed.
Receives the sending socke. Disconnects it and removes it.
Creates the message to send to all the other users and adds it to the list of messages to send.
"""
def handle_disconnection(send_socket):
    user_name = users_dict[id(send_socket)].name
    to_send = ""
    if user_name is None:
        to_send = str_time() + "Someone left the chat"
        print(to_send)
    else:
        if users_dict[id(send_socket)].is_manager is True:
            managers_names.remove(user_name)
            to_send = str_time() + MANAGER_SYMBOL + user_name + " left the chat"
            print(to_send)
        else:
            to_send = str_time() + user_name + " left the chat"
            print(to_send)
    send_socket.close()
    connected_client_sockets.remove(send_socket)
    recv_sockets = connected_client_sockets.copy()
    prepare_message_for_sending(to_send, recv_sockets)
    del users_dict[id(send_socket)]


"""
Receives the socket and the name of the sending user, and the name of the target user and returns his socket.
If there is a user with that name, returns his socket, if not returns None.
***If the target user and the sending user has the same name, compares between the sockets and if they'r not the same,
returns the socket. If there is only one socket related to the common name, returns that socket (the socket of the 
sending user). 
"""
def socket_by_name(send_socket, send_name, target_name):
    if send_name == target_name:
        for socket_id in users_dict.keys():
            if users_dict[socket_id].name == target_name:
                curr_socket = ctypes.cast(socket_id, ctypes.py_object).value  # Get the socket by its id
                if curr_socket is not send_socket:
                    return curr_socket
        return send_socket

    for socket_id in users_dict.keys():
        if users_dict[socket_id].name == target_name:
            return ctypes.cast(socket_id, ctypes.py_object).value  # Get the socket by its id
    return None


"""In case there are no managers (if the chat just opened or if the manager quit the chat), a new manager will
will automatically be appointed. Appoints as a manager the user related to the first socket in the list of connected
sockets, that has a name.
"""
def automatic_manager_appointment():
    for curr_socket in connected_client_sockets:
        curr_user = users_dict[id(curr_socket)]
        if curr_user.name is not None:
            curr_user.is_manager = True
            managers_names.append(curr_user.name)
            # Send manager appointment message.
            to_send1 = str_time() + "You've been appointed  as a manager now!"
            prepare_message_for_sending(to_send1, [curr_socket])
            to_send2 = str_time() + curr_user.name + " has been appointed as a manager."
            recv_sockets = connected_client_sockets.copy()
            recv_sockets.remove(curr_socket)
            prepare_message_for_sending(to_send2, recv_sockets)
            print(str_time() + curr_user.name + " has been automatically apointed as a manager")
            break


# A function that receives the socket and the name of the sending user. If the user related to the socket is silenced,
# returns true, sends him a suitable message, and prints a description in the console.
def notify_silenced(send_socket, send_name):
    if users_dict[id(send_socket)].is_silenced is True:
        to_send = "You cannot speak here!"
        prepare_message_for_sending(to_send, [send_socket])
        print(str_time() + send_name + " tried to send something but he's silenced.")
        return True
    return False


"""A function that receives the socket and name of the sending user and the socket and name of the user the message is
sent to him, or that a command is activated on him.
If the target socket is None, or if the target socket is the same as the sending socket,
the function returns true, sends the user a suitable message, and prints a description in the console.
"""
def notify_ivalid_name(send_socket, send_name, target_socket, target_name):
    if target_socket is None:
        to_send = "Invalid user name. No user with name '" + target_name + "' in the chat."
        print(str_time() + send_name + " entered an invalid name (" + target_name + ")")
        prepare_message_for_sending(to_send, [send_socket])
        return True
    if target_socket is send_socket:
        to_send1 = "You cannot use this command on yourself."
        prepare_message_for_sending(to_send1, [send_socket])
        print(str_time() + send_name + " tried to use a command on himself.")
        return True
    return False


"""Called in case a user wants to use a command for managers only.
The function receives the socket and name of the sending user. If he's not a manager, returns true,
sends him a suitable message and prints a description in the console.
"""
def notify_not_manager(send_socket, send_name):
    if users_dict[id(send_socket)].is_manager is False:
        to_send = "You'r not allowed to use this command because you'r not a manager."
        prepare_message_for_sending(to_send, [send_socket])
        print(str_time() + users_dict[id(send_socket)].name + " tried to use a command available only for managers, "
        "although he's not a manager")
        return True
    return False


# Handles cases in which the data sent from the user is a chat message.
# Receives the sending socket, the name of the sending user and the message.
def handle_chat_message(send_socket, send_name, message):
    if notify_silenced(send_socket, send_name) is False:
        to_send1 = str_time() + "You: " + message
        prepare_message_for_sending(to_send1, [send_socket])
        to_send2 = ""
        if users_dict[id(send_socket)].is_manager is True:
            to_send2 = str_time() + MANAGER_SYMBOL + send_name + ": " + message
        else:
            to_send2 = str_time() + send_name + ": " + message
        recv_sockets = connected_client_sockets.copy()
        recv_sockets.remove(send_socket)
        prepare_message_for_sending(to_send2, recv_sockets)
        print(to_send2)


# Handles situations in which the data sent from the user is an appointment of a user as a manager.
# Receives the socket and the name of the sending user, the socket and the name of the target (the potential receiving
# socket).
def handle_appoint_manager(send_socket, send_name, target_socket, target_name):
    if notify_not_manager(send_socket, send_name) is False:
        if notify_ivalid_name(send_socket, send_name, target_socket, target_name) is False:
            if users_dict[id(target_socket)].is_manager is True:  # If the other user is already a manager
                to_send = target_name + " is already a manager."
                prepare_message_for_sending(to_send, [send_socket])
                print(str_time() + send_name + "tried to appoint " + target_name + " as a manager but he's already a manager.")
            else:
                users_dict[id(target_socket)].is_manager = True
                managers_names.append(target_name)
                to_send1 = str_time() + MANAGER_SYMBOL + send_name + " appointed you as a manager!"
                prepare_message_for_sending(to_send1, [target_socket])
                to_send2 = str_time() + "You appointed " + target_name + " as a manager."
                prepare_message_for_sending(to_send2, [send_socket])
                to_send3 = str_time() + MANAGER_SYMBOL + send_name + " appointed " + target_name + " as a manager. "
                recv_sockets = connected_client_sockets.copy()
                recv_sockets.remove(target_socket)
                recv_sockets.remove(send_socket)
                prepare_message_for_sending(to_send3, recv_sockets)
                print(to_send3)


# Handles situations in which the data sent from the user is a command to remove one of the users.
# Receives the socket and the name of the sending user, the socket and the name of the target (the potential receiving
# socket).
def handle_remove(send_socket, send_name, target_socket, target_name):
    if notify_not_manager(send_socket, send_name) is False:
        if notify_ivalid_name(send_socket, send_name, target_socket, target_name) is False:
            to_send1 = str_time() + MANAGER_SYMBOL + send_name + " removed you from the chat."
            prepare_message_for_sending(to_send1, [target_socket], True)
            to_send2 = str_time() + "You removed " + target_name + " from the chat."
            prepare_message_for_sending(to_send2, [send_socket])
            to_send3 = str_time() + MANAGER_SYMBOL + send_name + " removed " + target_name + " from the chat."
            recv_sockets = connected_client_sockets.copy()
            recv_sockets.remove(target_socket)
            recv_sockets.remove(send_socket)
            prepare_message_for_sending(to_send3, recv_sockets)
            print(to_send3)


# Handles situations in which the data sent from the user is a command to silence one of the users.
# Receives the socket and the name of the sending user, the socket and the name of the target (the potential receiving
# socket).
def handle_silence_user(send_socket, send_name, target_socket, target_name):
    if notify_not_manager(send_socket, send_name) is False:
        if notify_ivalid_name(send_socket, send_name, target_socket, target_name) is False:
            if users_dict[id(target_socket)].is_silenced is True:
                to_send = target_name + " is already silenced"
                prepare_message_for_sending(to_send, [send_socket])
                print(str_time() + send_name + "tried to silence " + target_name + " although he's already silenced.")
            else:
                users_dict[id(target_socket)].is_silenced = True
                to_send1 = str_time() + MANAGER_SYMBOL + send_name + " silenced you. You can't send messages any more."
                prepare_message_for_sending(to_send1, [target_socket])
                to_send2 = str_time() + "You silenced " + target_name
                prepare_message_for_sending(to_send2, [send_socket])
                to_send3 = str_time() + MANAGER_SYMBOL + send_name + " silenced " + target_name
                recv_sockets = connected_client_sockets.copy()
                recv_sockets.remove(target_socket)
                recv_sockets.remove(send_socket)
                prepare_message_for_sending(to_send3, recv_sockets)
                print(to_send3)


# Handles cases in which the data sent from the user is a private message.
# Receives the socket and the name of the sending user, the socket and the name of the target (the potential receiving
# socket), and the message itself.
def handle_private_message(send_socket, send_name, target_socket, target_name, message):
    if notify_silenced(send_socket, send_name) is False:
        if notify_ivalid_name(send_socket, send_name, target_socket, target_name) is False:
            to_send1 = ""
            if users_dict[id(send_socket)].is_manager is True:
                to_send1 = str_time() + "!" + MANAGER_SYMBOL + send_name + ": " + message
                print(str_time() + MANAGER_SYMBOL + send_name + " sent a private message to " + target_name + ".")
            else:
                to_send1 = str_time() + "!" + send_name + ": " + message
                print(str_time() + send_name + " sent a private message to " + target_name + ".")
            prepare_message_for_sending(to_send1, [target_socket])
            to_send2 = str_time() + "You (private message to " + target_name + "): " + message
            prepare_message_for_sending(to_send2, [send_socket])


if __name__ == '__main__':
    main()