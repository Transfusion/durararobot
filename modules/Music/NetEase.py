# Interfaces with https://binaryify.github.io/NeteaseCloudMusicApi/#/?id=neteasecloudmusicapi

import aiohttp
import asyncio
from .MusicPlugin import MusicPlugin, QueryState, Query_Type, Song, Playlist
from enum import Enum
import logging
import json
import traceback
import math
from urllib.parse import urlsplit
import dns.resolver
import random

class Search_Type(Enum):
    song = 1
    album = 10
    playlist = 1000


class NetEasePlugin(MusicPlugin):
    CONF_NETEASE_API_ENDPOINT_KEY = "ne_endpoint"

    @staticmethod
    def name():
        return "NetEase"

    async def _search(self, kwd, page, limit):
        try:
            async with self.http_client_session.get("http://" + self.conf[NetEasePlugin.CONF_NETEASE_API_ENDPOINT_KEY] + "/search",
                                                    params={'keywords': kwd,
                                                            'type': Search_Type.song.value,
                                                            'limit': limit,
                                                            'offset': (page-1)*limit}) as resp:
                text = await resp.text()
                parsed_json = json.loads(text)
                self.logger.debug(parsed_json)
                # self, kwd, type, limit, entries, page, pages):
                pages = math.ceil(parsed_json['result']['songCount']/ limit)
                entries = []
                if 'songs' in parsed_json['result']:
                    for song in parsed_json['result']['songs']:
                        # self, name, artist, duration, id, plugin
                        entries.append(Song(song['name'], song['artists'][0]['name'],
                                            song['duration'], song['id'], self))
                qs = QueryState(kwd, Query_Type.song, limit, entries, page, pages, self)

                return qs

        except Exception:
            self.logger.error(traceback.format_exc())
            return None

    def search(self, kwd, page, limit):
        """Returns a song """
        future = asyncio.run_coroutine_threadsafe(self._search(kwd, page, limit), self.loop)
        return future.result()

    async def _search_playlist(self, kwd, page, limit):
        try:
            async with self.http_client_session.get(
                                    "http://" + self.conf[NetEasePlugin.CONF_NETEASE_API_ENDPOINT_KEY] + "/search",
                                    params={'keywords': kwd,
                                            'type': Search_Type.playlist.value,
                                            'limit': limit,
                                            'offset': (page - 1) * limit}) as resp:
                text = await resp.text()
                parsed_json = json.loads(text)
                self.logger.debug(parsed_json)
                # self, kwd, type, limit, entries, page, pages):
                pages = math.ceil(parsed_json['result']['playlistCount'] / limit)
                entries = []
                if 'playlists' in parsed_json['result']:
                    for playlist in parsed_json['result']['playlists']:
                        # (self, name, creator_id, id, song_count, plugin)
                        entries.append(Playlist(playlist['name'], playlist['creator']['userId'],
                                                playlist['id'], playlist['trackCount'], self))
                qs = QueryState(kwd, Query_Type.playlist, limit, entries, page, pages, self)
                return qs

        except Exception:
            self.logger.error(traceback.format_exc())
            return None

    def search_playlist(self, kwd, page, limit):
        future = asyncio.run_coroutine_threadsafe(self._search_playlist(kwd, page, limit), self.loop)
        return future.result()

    # prepend IP address
    # sample url: http://m10.music.126.net/20171114231954/9f399d10f2d8bfcd185e2afd3f7132cb/ymusic/32ad/83a4/4790/c1dfcc6cbf3b613410655d4e4a96c1ef.mp3
    def _globalize_ne_url(self, url):
        domain = "{0.netloc}".format(urlsplit(url))
        scheme = "{0.scheme}".format(urlsplit(url))
        ips = [data.address for data in dns.resolver.query(domain, "A")]
        ip = random.choice(ips)
        return scheme + "://" + str(ip) + "/" + url[len(scheme)+3:]


    # should return a dict
    # TODO: sometimes DNS lookup fails
    async def _get_song_urls_async(self, ids):
        d = dict(zip(ids, [None]*len(ids)))
        try:
            async with self.http_client_session.get(
                                    "http://" + self.conf[NetEasePlugin.CONF_NETEASE_API_ENDPOINT_KEY] + "/music/url",
                                    params={'id': ",".join(map(str, ids))}) as resp:
                text = await resp.text()
                parsed_json = json.loads(text)
                self.logger.debug(parsed_json)
                if "data" in parsed_json:
                    for item in parsed_json['data']:
                        if 'url' in item and item['url'] is not None:
                            d[int(item['id'])] = self._globalize_ne_url(item['url'])

            return d
        except Exception:
            self.logger.error(traceback.format_exc())
            return []

    def get_song_url(self, id):
        future = asyncio.run_coroutine_threadsafe(self._get_song_urls_async([id]), self.loop)
        return future.result()[id]

    def _get_song_urls(self, ids):
        """ids is a list of song ids for this particular plugin. returns a list of urls in the same order"""
        pass

    def get_album_songs(self, album_id):
        pass

    async def _get_playlist_songs_async(self, id):
        try:
            async with self.http_client_session.get(
                                    "http://" + self.conf[NetEasePlugin.CONF_NETEASE_API_ENDPOINT_KEY] + "/playlist/detail",
                                    params={'id': str(id)}) as resp:
                text = await resp.text()
                parsed_json = json.loads(text)
                # self.logger.debug(parsed_json)
                entries = []
                if "tracks" in parsed_json['playlist']:
                    for item in parsed_json['playlist']['tracks']:
                        entries.append(Song(item["name"], item["ar"][0]["name"], item["dt"], item["id"], self))
                return entries

        except Exception:
            self.logger.error(traceback.format_exc())
            return []


    def get_playlist_songs(self, playlist_id):
        """returns a list of song objects, empty list otherwise"""
        future = asyncio.run_coroutine_threadsafe(self._get_playlist_songs_async(playlist_id), self.loop)
        return future.result()


    def __init__(self, loop, conf, save_config):
        self.logger = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(ch)


        # maintain a reference the function to write the config since we need it
        self.loop = loop
        self.save_config = save_config()
        self.conf = conf

        self.http_client_session = aiohttp.ClientSession(loop=self.loop)

        if NetEasePlugin.CONF_NETEASE_API_ENDPOINT_KEY not in self.conf:
            self.conf[NetEasePlugin.CONF_NETEASE_API_ENDPOINT_KEY] = "127.0.0.1:3000"

