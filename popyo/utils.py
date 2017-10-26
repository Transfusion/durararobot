# utility class for constructing messages arriving in JSON format
import json
import logging

from .message import *
from .user import *

"""Converts the talks list into a list of messages, room is the room object"""
def talks_to_msgs(messages, room):
    return [talk_to_msg(m, room) for m in messages]


"""msg is one individual json object representing a talk"""
def talk_to_msg(msg, room):
    # self, id, time, type, sender, message):

    if msg['type'] == 'message':
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
        m = MeMessage(msg['id'], msg['time'], room.users[msg['from']['id']], msg['message'])

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

    return m