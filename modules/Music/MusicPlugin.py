# interface so we can add more music plugins in the future

from abc import ABCMeta, abstractmethod, abstractproperty
from enum import Enum

import time

# perhaps subclass these (e.g. NetEaseSong..)
class Song:
    def __init__(self, name, artist, duration, id, plugin):
        self.name = name
        self.artist = artist
        # in ms
        self.duration = duration
        self.id = id
        # should be a string so we can lookup the plugin instance
        self.plugin = plugin

    # def get_info_url(self):
    #     if type(self.plugin) ==

    def get_short_string(self):
        """For printing out in search queries"""
        # return self.artist + "-" + self.name + " " + time.strftime("%M:%S", time.gmtime(self.duration))
        return self.artist + "-" + self.name + " " + "%d:%02d" % (divmod(self.duration/1000, 60))

# should correspond to an album in the particular plugin's context; some plugins (e.g. youtube) might not have an analog
class Album:
    def __init__(self):
        pass

class Playlist:
    def __init__(self, name, creator_id, id, song_count, plugin):
        self.name = name
        self.creator_id = creator_id
        self.id = id
        # self.song_id_list = song_id_list
        # just make it a list of Song objects
        # self.song_list = song_list
        self.song_list = None
        self.song_count = song_count
        self.plugin = plugin

    async def get_song_list_async(self, plugin_instance):
        if self.song_list is None:
            self.song_list = await plugin_instance._get_playlist_songs_async(self.id)
        return self.song_list

    def get_song_list(self, plugin_instance):
        if self.song_list is None:
            self.song_list = plugin_instance.get_playlist_songs(self.id)
        return self.song_list


    def get_short_string(self):
        return self.name + "-" + str(self.song_count)



class Query_Type(Enum):
    song = 1
    album = 2
    playlist = 3

# entries should be a list of songs or playlists
class QueryState():
    def __init__(self, kwd, type, limit, entries, page, pages, plugin):
        self.kwd = kwd
        self.type = type
        self.limit = limit
        self.entries = entries
        self.page = page
        self.pages = pages
        # string
        self.plugin = plugin


class MusicPlugin(metaclass=ABCMeta):

    @staticmethod
    def name():
        pass

    @abstractmethod
    def search(self, kwd, page, limit):
        """Returns individual songs, blocking"""
        pass

    @abstractmethod
    def search_playlist(self, kwd, page, limit):
        """Returns playlists, blocking"""
        pass

    @abstractmethod
    async def _get_song_urls_async(self, ids):
        pass

    @abstractmethod
    def get_song_url(self, id):
        pass


    @abstractmethod
    def _get_song_urls(self, ids):
        """ids is a list of song ids for this particular plugin. returns a list of urls in the same order"""
        pass

    @abstractmethod
    def get_album_songs(self, album_id):
        pass

    @abstractmethod
    async def _get_playlist_songs_async(self, id):
        pass

    @abstractmethod
    def get_playlist_songs(self, playlist_id):
        pass

    @abstractmethod
    def get_item_info_url(self, item):
        pass
