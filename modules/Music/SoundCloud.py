
from .MusicPlugin import MusicPlugin, QueryState, Query_Type, Song, Playlist, Album

import soundcloud,logging, traceback, asyncio


class SoundCloudPlugin(MusicPlugin):
    CONF_API_KEY = "sc_api_key"
    CONF_USE_SSL = "endpoint_use_ssl"


    @staticmethod
    def name():
        return "SoundCloud"

    # unable to get total search results count as of 13 dec 2017
    # let's just use the legacy offset pagination for now
    def search(self, kwd, page, limit):
        """Returns individual songs, blocking"""
        tracks = self.sc_client.get('/tracks', q=kwd, sharing='public', limit=limit, offset=limit*(page-1),
                                    linked_partitioning=1)

        entries = []

        for track in tracks.collection:
            # def __init__(self, name, artist, duration, id, plugin):
            entries.append(Song(name=track.title, artist=track.user['username'], duration=track.duration, id=track.id,
                                plugin=SoundCloudPlugin.name()))

        return QueryState(kwd, Query_Type.song, limit, entries, page, -1, SoundCloudPlugin.name())

    def search_playlist(self, kwd, page, limit):
        """Returns playlists, blocking"""
        playlists = self.sc_client.get('/playlists', q=kwd, sharing='public', limit=limit, offset=limit*(page-1),
                                    linked_partitioning=1)

        entries = []

        for playlist in playlists.collection:
            # def __init__(self, name, creator_id, id, song_count, plugin):
            entries.append(Playlist(name=playlist.title, creator_id=playlist.user['id'], id=playlist.id,
                                    song_count=playlist.track_count, plugin=SoundCloudPlugin.name()))

        return QueryState(kwd, Query_Type.playlist, limit, entries, page, -1, SoundCloudPlugin.name())


    async def _get_song_urls_async(self, ids):
        # print(ids)
        urls = {}

        for id in ids:
            try:
                stream_info = self.sc_client.get('/tracks/%s/streams' % id )
                # print(stream_info)
                if hasattr(stream_info, 'http_mp3_128_url'):
                    urls[id] = stream_info.http_mp3_128_url
                else:
                    urls[id] = None
            except Exception:
                self.logger.error(traceback.format_exc())
                urls[id] = None

        return urls

    def get_song_url(self, id):
        pass


    def _get_song_urls(self, ids):
        """ids is a list of song ids for this particular plugin. returns a list of urls in the same order"""
        pass

    def get_album_songs(self, album_id):
        pass

    async def _get_playlist_songs_async(self, id):
        # get the total number of songs in the playlist first
        pl_info = self.sc_client.get('/playlists/%s' % id)
        track_count = pl_info.track_count

        offset_list =[i*200 for i in range( int( track_count/200 )+ 1)]
        songs = []

        for offset in offset_list:
            tracks = self.sc_client.get('/playlists/%s/tracks' % id, offset=offset, limit=200)
            for track in tracks:
                songs.append(Song(name=track.title, artist=track.user['username'], duration=track.duration, id=track.id,
                            plugin=SoundCloudPlugin.name()))

        return songs


    # tracks = client.get('https://api.soundcloud.com/playlists/215576834/tracks', sharing='any', offset=200, limit=10000)
    # undocumented, but the tracks api only returns 200 items at once, so need to calculate accordingly
    def get_playlist_songs(self, playlist_id):
        future = asyncio.run_coroutine_threadsafe(self._get_playlist_songs_async(playlist_id), self.loop)
        return future.result()

    def get_item_info_url(self, item):
        if type(item) is Song:
            track_obj = self.sc_client.get('/tracks/%s' % item.id)
            return track_obj.permalink_url
        elif type(item) is Playlist:
            playlist_obj = self.sc_client.get('/playlists/%s' % item.id)
            return playlist_obj.permalink_url
        elif type(item) is Album:
            pass

    def __init__(self, loop, conf, save_config):
        self.logger = logging.getLogger(__name__)

        self.loop = loop
        self.save_config = save_config
        self.conf = conf

        if SoundCloudPlugin.CONF_API_KEY not in self.conf:
            self.conf[SoundCloudPlugin.CONF_API_KEY] = 'cnSYjxmeQCWsxjhf07BNwv5EUDe1jlNB'
            self.save_config()

        if SoundCloudPlugin.CONF_USE_SSL not in self.conf:
            self.conf[SoundCloudPlugin.CONF_USE_SSL] = False
            self.save_config()

        self.sc_client = soundcloud.Client(client_id=self.conf[SoundCloudPlugin.CONF_API_KEY],
                                           use_ssl=self.conf[SoundCloudPlugin.CONF_USE_SSL])