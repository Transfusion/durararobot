# class encapsulating the asyncio loop playing the music

# from .Music import Music
from .MusicQueueManager import MusicQueueManager
from .MusicPlugin import *
from enum import Enum

import asyncio, logging, traceback

class MusicPlayer:

    # class RepeatMode(Enum):
    #     OFF = 1
    #     SINGLE = 2
    #     # TODO: repeat all deterministically
    #     ALL = 3
    #
    #
    # class ShuffleMode(Enum):
    #     OFF = 1
    #     SHUFFLE = 2

    class PlayMode(Enum):
        REGULAR = 0

        REPEAT_ALL = 1
        REPEAT_SINGLE = 2

        SHUFFLE_ALL = 3
        SHUFFLE_REPEAT = 4

    class PlayerState(Enum):
        # playing a song, waiting on the semaphore to release
        PLAYING_WAIT = 1
        # task is not running
        STOPPED = 2
        # not playing a song, waiting on the semaphore to release
        EMPTY_WAIT = 3

    def __init__(self, loop, conn_name, music_py, music_queue_mgr=None):

        self.logger = logging.getLogger(__name__)
        self.loop = loop
        self.conn_name = conn_name
        # we use _get_plugin and play_music from music.py
        self.music_py = music_py
        if music_queue_mgr is not None:
            self.music_queue_mgr = music_queue_mgr
        else:
            self.music_queue_mgr = MusicQueueManager(loop, music_py._get_plugin)

        self.player_state = MusicPlayer.PlayerState.STOPPED

        # Song that is playing now
        self.now_playing_song = None
        self.get_next_future = None
        self.playing_future = None

        self.play_mode = MusicPlayer.PlayMode.REGULAR

        # self.current_lock = asyncio.Event(loop=self.loop)

    async def _wait_song_finish(self, duration_ms):
        duration_s = float(duration_ms)/1000
        # m, s = divmod(duration_ms, 60)
        while self.now_playing_song.progress < duration_s:
            await asyncio.sleep(1)
            self.now_playing_song.progress += 1

    # def _get_next_song(self) -> Song:
    #     if self.ShuffleMode == MusicPlayer.ShuffleMode.SHUFFLE:
    #         if self.RepeatMode == MusicPlayer.RepeatMode.ALL
    #
    #     pass

    async def _get_next_and_play(self):
        while True:
            self.player_state = MusicPlayer.PlayerState.EMPTY_WAIT
            # do this to ensure thread safety...
            lock = await self.music_queue_mgr.get_lock_async()
            # blocks until internally is true, and is a COROUTINE, SO MUST AWAIT!
            self.logger.debug("waiting on empty " + self.conn_name)
            await lock.wait()

            song = self.music_queue_mgr.get_next_song(self.play_mode)

            try:
                plugin = self.music_py._get_plugin(song.plugin)

                url_dict = await plugin._get_song_urls_async([song.id])
            except Exception:
                self.logger.debug(traceback.format_exc())

            if url_dict[song.id] is None:
                self.music_py.bot.send(self.conn_name, "Unable to play " + song.name)
            else:
                self.now_playing_song = song

                # in seconds!
                self.now_playing_song.progress = 0
                self.music_py.bot.play_music(self.conn_name, song.name + "-" + song.artist, url_dict[song.id])
                self.logger.debug("playing " + url_dict[song.id] + " in " + self.conn_name)
                # here we set self.playing_future

                # self.playing_future = asyncio.ensure_future(asyncio.sleep(float(song.duration)/1000))
                self.playing_future = asyncio.ensure_future(self._wait_song_finish(song.duration))
                self.player_state = MusicPlayer.PlayerState.PLAYING_WAIT
                try:
                    await self.playing_future
                except asyncio.CancelledError:
                    self.now_playing_song = None
                    # self.playing_future = None
                    if self.player_state == MusicPlayer.PlayerState.STOPPED:
                        self.logger.debug("stopped while waiting")
                        return
                    else:
                        self.music_py.bot.action(self.conn_name, "Skipping.")
                # self.player_state = MusicPlayer.PlayerState.EMPTY_WAIT
                self.logger.debug("finished playing " + song.name + " in " + self.conn_name)
                # at this point, the playing future is done.
                assert self.playing_future.done()
                self.playing_future = None
                self.now_playing_song = None

            self.player_state = MusicPlayer.PlayerState.EMPTY_WAIT
            try:
                assert self.get_next_future is not None
                assert self.playing_future is None
                assert self.now_playing_song is None
            except Exception:
                self.logger.debug(traceback.format_exc())
            # can't do the below, because we already are in an async function!!
            # self.get_next_future = asyncio.run_coroutine_threadsafe(self._get_next_and_play(), self.loop)



    def start_play_loop(self):
        if self.player_state == MusicPlayer.PlayerState.STOPPED:
            # here we set self.get_next_future
            self.get_next_future = asyncio.run_coroutine_threadsafe(self._get_next_and_play(), self.loop)
        else:
            self.logger.debug("already started " + self.conn_name)

    def skip_song(self, songs_to_skip=0):
        assert self.playing_future is not None and not self.playing_future.done()
        assert self.player_state == MusicPlayer.PlayerState.PLAYING_WAIT
        self.music_queue_mgr.remove_top_n_songs(songs_to_skip)
        asyncio.run_coroutine_threadsafe(self._cancel_playing_future(), loop=self.loop)

    def skip_items(self, items_to_skip=0):
        assert self.playing_future is not None and not self.playing_future.done()
        assert self.player_state == MusicPlayer.PlayerState.PLAYING_WAIT
        self.music_queue_mgr.remove_top_n_items(items_to_skip)
        asyncio.run_coroutine_threadsafe(self._cancel_playing_future(), loop=self.loop)


    async def _cancel_playing_future(self):
        assert self.playing_future is not None
        self.playing_future.cancel()

    async def _cancel_get_next_future(self):
        assert self.get_next_future is not None
        self.get_next_future.cancel()

    def stop_play_loop(self):
        if self.player_state == MusicPlayer.PlayerState.PLAYING_WAIT:
            assert self.playing_future is not None
            assert self.get_next_future is not None
            # have to stop two futures, must strictly be in this order???
            try:
                # no idea how to do it properly, might cause a race condition...
                self.player_state = MusicPlayer.PlayerState.STOPPED
                future2 = asyncio.run_coroutine_threadsafe(self._cancel_playing_future(), loop=self.loop)
                # future2.set_result("test")
                # future2.add_done_callback(lambda x: asyncio.run_coroutine_threadsafe(self._cancel_get_next_future(), loop=self.loop))
                # if you do this alone during playing, the *inner* except asyncio.CancelledError will catch it!!
                # future1 = asyncio.run_coroutine_threadsafe(self._cancel_get_next_future(), loop=self.loop)
                # block
                # future1.result()
                future2.result()
                # self.player_state = MusicPlayer.PlayerState.STOPPED
            except Exception:
                self.logger.debug(traceback.format_exc())

        elif self.player_state == MusicPlayer.PlayerState.EMPTY_WAIT:
            assert self.playing_future is None
            future = asyncio.run_coroutine_threadsafe(self._cancel_get_next_future(), loop=self.loop)
            future.result()
            self.player_state = MusicPlayer.PlayerState.STOPPED

        elif self.player_state == MusicPlayer.PlayerState.STOPPED:
            assert self.playing_future is None
            assert self.get_next_future is None
            self.logger.debug("already stopped " + self.conn_name)

    # item may be a song, playlist, or album
    def add_to_queue(self, item):
        self.music_queue_mgr.add_to_queue(item)
