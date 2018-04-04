# class encapsulating a music queue

from .MusicPlugin import *
import asyncio, random, traceback

class MusicQueueManager:

    def __init__(self, loop, _get_plugin_func, mqueue_shelf=None, idlequeue_shelf=None):
        # the basis is a list because we need random access to shuffle and potentially delete
        self.q = []
        # TODO: idle queue??
        # self.idleq = []
        self.loop = loop
        self.lock = asyncio.Event(loop=loop)
        # from Music.py, to lookup the actual plugin object because shelved songs/plists only contain the plugin name
        self._get_plugin_func = _get_plugin_func

        self._last_popped_song = None
        if mqueue_shelf is not None:
            pass

    async def get_lock_async(self):
        if self.isEmpty():
            self.lock.clear()
        else:
            self.lock.set()

        return self.lock

    def get_lock(self):
        if self.isEmpty():
            self.lock.clear()
        else:
            self.lock.set()
        return self.lock

    def peek_next_song(self):
        pass

    def peek_next_item(self):
        if not self.q:
            return None
        return self.q[0]

    def _get_random_song(self, pop=False) -> Song:
        try:
            # random.randint is inclusive
            random_idx = random.randint(0, len(self.q)-1)
            print(random_idx)
            if type(self.q[random_idx]) is Song:
                if not pop:
                    self._last_popped_song = self.q[random_idx]
                    return self._last_popped_song
                song = self.q[random_idx]
                del self.q[random_idx]
                self._last_popped_song = song
                return song

            # must be a playlist or album
            elif type(self.q[random_idx]) is Playlist:

                pl = self.q[random_idx]
                pl_songs = pl.get_song_list(self._get_plugin_func(pl.plugin))
                assert len(pl_songs) >= 1
                if not pop:
                    self._last_popped_song = random.choice(pl_songs)
                    return self._last_popped_song
                # else, get a random song and remove it.
                random_song_idx = random.randint(0, len(pl_songs)-1)
                song = pl_songs[random_song_idx]
                del pl_songs[random_song_idx]
                if len(pl_songs) == 0:
                    del self.q[random_idx]
                self._last_popped_song = song
                return song

            elif type(self.q[random_idx]) is Album:
                pass
        except Exception:
            print(traceback.format_exc())

    # need to handle songs, and {playlists, albums} differently
    def _get_first_song(self, pop=False) -> Song:
        if not self.q:
            return None
        item = self.q[0]
        if type(item) is Song:
            if not pop:
                self._last_popped_song = item
                return self._last_popped_song
            self._last_popped_song = self.q.pop(0)
            return self._last_popped_song

        elif type(item) is Playlist:
            pl_songs = item.get_song_list(self._get_plugin_func(item.plugin))
            assert len(pl_songs) >= 1
            if not pop:
                self._last_popped_song = pl_songs[0]
                return self._last_popped_song
            song = pl_songs.pop(0)
            self._last_popped_song = song
            if len(pl_songs) == 0:
                self.q.pop(0)
            return song

    def get_next_song(self, play_mode):
        from .MusicPlayer import MusicPlayer
        if play_mode == MusicPlayer.PlayMode.REGULAR:
            return self._get_first_song(pop=True)
        elif play_mode == MusicPlayer.PlayMode.REPEAT_SINGLE:
            if self._last_popped_song is not None:
                return self._last_popped_song
            else:
                # repeat the first song in the queue by default
                return self._get_first_song(pop=False)
        elif play_mode == MusicPlayer.PlayMode.SHUFFLE_REPEAT:
            return self._get_random_song(pop=False)
        elif play_mode == MusicPlayer.PlayMode.SHUFFLE_ALL:
            return self._get_random_song(pop=True)

        elif play_mode == MusicPlayer.PlayMode.REPEAT_ALL:
            # TODO: implement repeat_all
            pass

    def remove_top_n_songs(self, songs_to_remove=0):
        for i in range(songs_to_remove):
            if self.q == []:
                break
            elif isinstance(self.q[0], Song):
                del self.q[0]
            #     inefficient, but will do
            elif isinstance(self.q[0], Playlist):
                pl = self.q[0]
                plugin_instance = self._get_plugin_func(pl.plugin)
                if self.q[0].get_song_list(plugin_instance) == []:
                    del self.q[0]
                else:
                    del self.q[0].get_song_list(plugin_instance)[0]


    def remove_top_n_items(self, items_to_remove=0):
        self.q = self.q[items_to_remove:]

    def get_random_item(self):
        pass

    def clear_q(self):
        self.q.clear()

    def get_q(self):
        return self.q


    def remove_q_item(self, idx: int) -> bool:
        if not idx >= len(self.q) and idx >= 0:
            del self.q[idx]
            return True
        return False

    def isEmpty(self):
        return len(self.q) == 0

    async def _add_to_queue(self, item):
        self.q.append(item)
        self.lock.set()

    def add_to_queue(self, item):
        asyncio.run_coroutine_threadsafe(self._add_to_queue(item), self.loop)
