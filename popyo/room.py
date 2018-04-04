
# todo: investigate how werewolf games work and perhaps subclass this???
class Room:

    # users is a dict of user id to user object (because the api associates user ids with msgs)
    def __init__(self, name, desc, limit, users, host_id, lang, room_id, update, music=False, dj_mode=False, music_np=None, game=False):
        self.name = name
        self.desc = desc
        self.limit = limit
        self.users = users

        # self.banned_users
        self.banned_ids = set()

        self.lang = lang
        self.room_id = room_id
        self.music = music

        self.dj_mode = music and dj_mode

        # simply the 'np' dict e.g.
        # {"musicName": "8", "musicURL": "http:\/\/srv8.youtubemp3.to\/download.php?output=MTI3NjIzMjIvMTUxMzE1MjY3OQ==",
        #  "url": "http:\/\/srv8.youtubemp3.to\/download.php?output=MTI3NjIzMjIvMTUxMzE1MjY3OQ==", "name": "8",
        #  "playURL": "http:\/\/srv8.youtubemp3.to\/download.php?output=MTI3NjIzMjIvMTUxMzE1MjY3OQ==",
        #  "time": 1513150922.2785,
        #  "shareURL": "http:\/\/srv8.youtubemp3.to\/download.php?output=MTI3NjIzMjIvMTUxMzE1MjY3OQ=="}

        self.music_np = music_np

        self.game = game
        self.host_id = host_id

        self.update = update

    def __str__(self):
        return self.room_id + " " + self.name + " " + self.desc + " " + "users: " + str(len(self.users))
