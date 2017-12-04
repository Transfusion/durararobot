from enum import Enum

class Outgoing_Message_Type(Enum):
    message = 0
    dm = 1
    handover_host = 2
    music = 3
    url = 4
    dm_url = 5
    kick = 6
    action = 7
    direct_action = 8

class OutgoingMessage:
    def __init__(self, msg):
        self.type = Outgoing_Message_Type.message
        self.msg = msg

class OutgoingDirectMessage:
    # user id of the recipient in the room
    def __init__(self, msg, receiver):
        self.type = Outgoing_Message_Type.dm
        self.msg = msg
        self.receiver = receiver

class OutgoingUrlMessage:
    def __init__(self, msg, url):
        self.type = Outgoing_Message_Type.url
        self.msg = msg
        self.url = url