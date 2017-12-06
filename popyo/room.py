
# todo: investigate how werewolf games work and perhaps subclass this???
class Room:
    # users is a dict of user id to user object (because the api associates user ids with msgs)
    def __init__(self, name, desc, limit, users, lang, room_id, music, dj_mode, game, host_id, update):
        self.name = name
        self.desc = desc
        self.limit = limit
        self.users = users

        self.banned_users = {}

        self.lang = lang
        self.room_id = room_id
        self.music = music

        self.dj_mode = music and dj_mode

        self.game = game
        self.host_id = host_id

        self.update = update

    def __str__(self):
        return self.room_id + " " + self.name + " " + self.desc + " " + "users: " + str(len(self.users))
