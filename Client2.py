# Client for 12.6 chat project from "Gvahim" book.
# Auther: Gilad Moyal.

import socket
import select
import msvcrt
import time

MAX_BYTES = 100000  # The maximal size of every "chunk" of bytes sent threw the socket (6 digits)
MAX_NAME_LENGTH = 99  # The maximal length of the user's name (2 digits).
MAX_MESSAGE_LENGTH = 9999  # The maximal length of a message the user sends (4 digits).
MANAGER_SYMBOL = "@"  # The character that will be printed at the beginning of the manager's name

# The commands and the strings the user has to enter to use them:
CHAT_MESSAGE = "chat"
PRIVATE_MESSAGE = "private"
VIEW_MANAGERS = "view-managers"
QUIT_CHAT = "quit"  # The same string which will be sent to the server
APPOINT_MANAGER = "appoint-manager"  # The same string which will be sent to the server
REMOVE_FROM_CHAT = "remove"
SILENCE_USER = "silence"
# A dictionary of the commands. the key is the command the user will type and the value is the number of the command
# sent to the server according to the protocol.
# If the command number in the dictionary is 0 (zero), the command itself will be sent ("quit" for example).
COMMAND_DICT = {CHAT_MESSAGE: 1, PRIVATE_MESSAGE: 5, VIEW_MANAGERS: 0, QUIT_CHAT: 0, APPOINT_MANAGER: 2,
                REMOVE_FROM_CHAT: 3, SILENCE_USER: 4}
my_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # AF_INET refers to ipv4, SOCK_STREAM refers to TCP
list_to_send = []  # A list that contains the message when its ready to be sent (of type string).


def main():
    user_name = receive_valid_name()
    my_socket.connect(('127.0.0.1', 1111))  # Connects to the server (127.0.0.1 is on this machine)
    print_opening_message()
    message = ""  # the message is of type bytes-string
    in_chat = True
    # Messages will be sent only if the last piece of data has been recieved by the server, and a message was sent back,
    # If not, messages that are sent together, might arrive together, and the message received will be different.
    can_send_data = True

    while in_chat:
        rlist, wlist, xlist = select.select([my_socket], [my_socket], [])
        # In case the socket is readable
        if my_socket in rlist:
            in_chat = handle_incoming_data(message)
            can_send_data = True
        # If the user types something
        if msvcrt.kbhit():
            message = when_key_pressed(message)

        # In case the socket is writeable
        if my_socket in wlist and len(list_to_send) != 0 and can_send_data:
            data_to_send = prepare_message_to_send(user_name, list_to_send[0])
            if data_to_send is not None:
                my_socket.send(data_to_send.encode())
                can_send_data = False
            if list_to_send[0] == "quit":
                msvcrt.putwch("\r")
                print(time.strftime("%H:%M", time.localtime()) + " You left the chat")
                in_chat = False
            list_to_send.remove(list_to_send[0])

    my_socket.close()


# Receives a name from input until received a valid name (which doesn't start with '@') .Finally, returns the name.
def receive_valid_name():
    user_name = input("To join the chat, enter your name: ")
    while user_name == "":
        user_name = input("Your name has to contain characters.\n")
    while user_name[0] == MANAGER_SYMBOL or len(user_name) > MAX_NAME_LENGTH or " " in user_name:
        if user_name[0] == MANAGER_SYMBOL:
            user_name = input("The name shouldn't start with '" + MANAGER_SYMBOL + "' because this symbol indicates "
            "the manager. Please enter a different name.\n")
        if len(user_name) > MAX_NAME_LENGTH:
            user_name = input("The name shouldn't exceed " + str(MAX_NAME_LENGTH) + " characters. "
                        "Please enter a different name.\n")
        if " " in user_name:
            user_name = input("The name shouldn't contain spaces.\n")
    return user_name


# Prints the opening message when the user is connected. Prints the commands and how to use them.
def print_opening_message():
    print("Welcome to the chat! You can use the following commands: "
        "\nTo send a chat message type: " + CHAT_MESSAGE + " <YOUR MESSAGE>"
        "\nTo send a private message to a user type: " + PRIVATE_MESSAGE + " <USER NAME> <YOUR MESSAGE>"
        "\n(A received private message starts with the symbol '!')."
        "\nTo view the list of managers type: " + VIEW_MANAGERS +
        "\nTo leave the chat type: " + QUIT_CHAT +
        "\nFor managers (the '" + MANAGER_SYMBOL + "' symbol will appear before their name): "
        "\nTo appoint a manager type: " + APPOINT_MANAGER + " <USER NAME>"
        "\nTo remove a user from the chat type: " + REMOVE_FROM_CHAT + " <USER NAME>"
        "\nTo silence a user type: " + SILENCE_USER + " <USER NAME>")


# Handles cases in which a key press has been detected.
# Receives the current message (string), receives from the user the new char and adds it to the message.
# Returns the updated message (string)
def when_key_pressed(message):
    char = msvcrt.getwch()  # The key pressed on the keyboard
    if char == "\b":
        msvcrt.putwch(char)
        message = message[:-1]
        msvcrt.putwch(" ")
        msvcrt.putwch("\b")
        return message
    # When the user finished typing the message and pressed enter.
    # The curser is at the beginning of the line with the typed message
    if char == "\r":
        list_to_send.append(message)
        return ""
    msvcrt.putwch(char)
    message += char
    return message


# Receives a name and returns a string of the length of the name.
#If necessary, adds 0s at the beginning of the length of the name, to match the number of digits in MAX_NAME_LENGTH.
def string_name_length(name):
    return (len(str(MAX_NAME_LENGTH)) - len(str(len(name)))) * "0" + str(len(name))


# Receives a message and returns a string of the length of the message.
# If necessary, adds 0s at the beginning of the length of the message, to match number of digits in MAX_MESSAGE_LENGTH.
def string_message_length(message):
    return (len(str(MAX_MESSAGE_LENGTH)) - len(str(len(message)))) * "0" + str(len(message))


# Prints the message when one or more of the details the user entered doen't match the commands.
def invalid_command_message():
    print("\nInvalid command. Make sure everything is spelled correctly and there are spaces in the right places.")


# Receives the user's name and the text he typed to send, creates the data to sent to the server according to
# the protocol, and returns it.
# If the command wasn't written properly, there is an exception or the message is empty, returns None.
def prepare_message_to_send(user_name, to_send):
    command = to_send.split(" ")[0]
    if command not in COMMAND_DICT.keys():
        invalid_command_message()
        return None
    if COMMAND_DICT[command] == 0:
        return to_send

    command_num = COMMAND_DICT[command]
    str_name_length = string_name_length(user_name)
    try:
        details = to_send.split(" ", 1)
        if command == CHAT_MESSAGE:
            message = details[1]
            str_message_length = string_message_length(message)
            data_to_send = str_name_length + user_name + str(command_num) + str_message_length + message
            return data_to_send

        second_name = details[1]
        str_second_name_length = string_name_length(second_name)
        if command == APPOINT_MANAGER or command == REMOVE_FROM_CHAT or command == SILENCE_USER:
            data_to_send = str_name_length + user_name + str(command_num) + str_second_name_length + second_name
            return data_to_send

        details = to_send.split(" ", 2)
        second_name = details[1]
        str_second_name_length = string_name_length(second_name)
        if command == PRIVATE_MESSAGE:
            message = details[2]
            str_message_length = string_message_length(message)
            data_to_send = str_name_length + user_name + str(command_num) + str_second_name_length + second_name \
                           + str_message_length + message
            return data_to_send
    except IndexError:
        invalid_command_message()
        return None


# Receives the current message that the user has been typing.
# Receives from the server data, separates it from its length according to the protocol and prints it to the user.
# Returns whether or not the user should stay in the chat (boolean).
def handle_incoming_data(curr_message):
    data = my_socket.recv(len(str(MAX_BYTES))).decode()
    if data == "":   # When the socket is being closed, an "empty message" is sent.
        msvcrt.putwch("\r")
        print(" " * len(curr_message))
        return False
    message_from_data_length = int(data)
    message_from_data = my_socket.recv(message_from_data_length).decode()
    if len(curr_message) != 0:
        data_during_message_typing(curr_message, message_from_data)
        return True
    else:
        msvcrt.putwch("\r")
        print(message_from_data)
        return True


"""
Receives the current message (it hasn't been sent yet) and the data received from the server, in string.
If data has been sent, and the message had been partially typed, the function will print the data in the same row,
and allow the user to continue typing his message from the next line.
When the function is called and when it finishes, the curser is at the end of the message which is being typed.
"""
def data_during_message_typing(curr_message, str_data):
    msvcrt.putwch("\r")

    # The length difference between the current message and the data. If the message is longer than the data,
    # spaces are needed to be printed in order to completely "erase" the message in that line.
    num_spaces_left = 0

    if len(curr_message) > len(str_data):
        num_spaces_left = len(curr_message) - len(str_data)
    print(str_data + num_spaces_left*" ")
    # prints the current message
    for char in curr_message:
        msvcrt.putwch(char)


if __name__ == '__main__':
    main()