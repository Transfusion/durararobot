# utility class for constructing messages arriving in JSON format
import json
import logging

from .message import *
from .user import *
import time

def create_cli_message_chan(text):
    return Message('a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1', str(round(time.time(), 3)), Message_Type.message, CLIUser(), text)

def create_cli_message_dm(text):
    return DirectMessage('a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1a1', str(round(time.time(), 3)),
                         Message_Type.dm, CLIUser(), CLIUser(), text)



def talks_to_msgs(messages, room):
    """Converts the talks list into a list of messages, room is the room object"""
    return [talk_to_msg(m, room) for m in messages]



def talk_to_msg(msg, room):
    """msg is one individual json object representing a talk"""

    # self, id, time, type, sender, message):

    if 'error' in msg:
        if 'reload' in msg:
            m = ErrorMessage(msg['error'], msg['reload'])
        else:
            m = ErrorMessage(msg['error'])

    elif msg['type'] == 'message':
        if 'url' in msg:
            if 'to' in msg:
                # (self, id, time, type, sender, receiver, message, url)
                m = DirectURLMessage(msg['id'], msg['time'], Message_Type.dm_url, room.users[msg['from']['id']],
                                     room.users[msg['to']['id']], msg['message'], msg['url'])
            else:
                # (self, id, time, type, sender, message, url):
                m = URLMessage(msg['id'], msg['time'], Message_Type.url, room.users[msg['from']['id']], msg['message'],
                               msg['url'])
        else:
            if 'to' in msg:
                m = DirectMessage(msg['id'], msg['time'], Message_Type.dm, room.users[msg['from']['id']], room.users[msg['to']['id']],
                                  msg['message'])

            else:
                m = Message(msg['id'], msg['time'], Message_Type.message, room.users[msg['from']['id']], msg['message'])

    elif msg['type'] == 'music':
        # self, id, time, sender, music_name, music_url, url, play_url, share_url
        m = MusicMessage(msg['id'], msg['time'], room.users[msg['from']['id']], msg['music']['musicName'],
                    msg['music']['musicURL'], msg['music']['url'], msg['music']['playURL'], msg['music']['shareURL'])

    elif msg['type'] == 'me':
        # id, time, sender, content):
        m = MeMessage(msg['id'], msg['time'], room.users[msg['from']['id']], msg['content'])

    elif msg['type'] == 'new-host':
        m = NewHostMessage(msg['id'], msg['time'], room.users[msg['user']['id']])

    elif msg['type'] == 'leave':
        m = LeaveMessage(msg['id'], msg['time'], room.users[msg['user']['id']])

    elif msg['type'] == 'join':
        m = JoinMessage(msg['id'], msg['time'], User(msg['user']['id'],
                                                     msg['user']['name'], msg['user']['icon'], msg['user']['tripcode'] if 'tripcode' in msg['user'] else None,
                                                     True if 'admin' in msg['user'].keys() and msg['user']['admin'] else False))

    elif msg['type'] == 'async-response':
        # id, time, secret, to, message, title, level, stop_fetching)
        m = AsyncResponse(msg['id'], msg['time'], msg['secret'], room.users[msg['to']['id']], msg['message'],
                          msg['title'], msg['level'], msg['stop-fetching'])

    elif msg['type'] == 'kick':
        m = KickMessage(msg['id'], msg['time'], room.users[msg['to']['id']], msg['message'])

    elif msg['type'] == 'ban':
        m = BanMessage(msg['id'], msg['time'], room.users[msg['to']['id']], msg['message'])

    elif msg['type'] == 'unban':
        m = UnbanMessage(msg['id'], msg['time'], room.banned_users[msg['to']['id']], msg['message'])


    elif msg['type'] == 'system':
        m = SystemMessage(msg['id'], msg['time'], msg)

    return m