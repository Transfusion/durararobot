"""The motivation behind this bot"""

# TODO: rejoining a connection but the room is now in DJ mode or otherwise
# TODO: room changes to DJ mode in the middle of a song and bot is not the DJ
# TODO: check if DJ mode or music simply not enabled.

from modules.module import Module

from popyo import *
import asyncio
import threading
import re
import os

import traceback
import shelve

from decorators import *


from .NetEase import NetEasePlugin
# from .YouTube import YouTubePlugin
from .SoundCloud import SoundCloudPlugin

from .MusicPlugin import *

from .MusicPlayer import *


class Music(Module):

    @staticmethod
    def name():
        return "Music"

    CONF_RESUME_AFTER_INTERRUPTED_KEY = "resume_after_interrupted"
    CONF_SEARCH_RESULTS_LIMIT = "res_limit"
    CONF_PLAYLIST_CACHE_FILE_KEY = "playlist_cache"
    CONF_RESPOND_IN_ROOM = "public_respond"
    CONF_IDLE_SHUFFLE_KEY = "idle_shuffle"

    # loop that plays the music and sleeps for the calculated time, and http
    KEY_EVT_LOOP = "loop"

    circled_numbers_array = ['⓪','①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩',
                             '⑪','⑫','⑬','⑭','⑮','⑯','⑰','⑱','⑲','⑳']


    def unload(self):
        pass

    def onjoin(self, conn_name, scrollback):
        music_loop = self.get_event_loop(Music.KEY_EVT_LOOP)
        self.music_players[conn_name] = MusicPlayer(music_loop, conn_name,
                                                    self, MusicQueueManager(music_loop, self._get_plugin))
        self.query_state[conn_name] = {}

    def onleave(self, conn_name):
        del self.query_state[conn_name]
        # that's why you modularize your code kids
        self._get_music_player(conn_name).stop_play_loop()


    # command format: !neq [s,p,a] song name [-p 1]
    # just use regex, it's easier...
    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_search(self, wrapper, message, provider, conn_name, dm):
        if provider == NetEasePlugin.name() or provider == SoundCloudPlugin.name():
            begin_idx = 5
            # available_methods = ['s', 'p']
            pagination_regex = re.compile(r"-p \d+")

        elif provider == YouTubePlugin.name():
            begin_idx = 5
            # available_methods = ['s', 'p']
            # disable pagination/match nothing
            pagination_regex = re.compile(r"a^")

        stripped_msg = message.message[begin_idx:]

        method = stripped_msg[0]
        stripped_msg = stripped_msg[2:]
        pagi = pagination_regex.search(stripped_msg)

        if pagi is not None:
            page = int(stripped_msg[pagi.span()[0]: pagi.span()[1]].split()[1])
            stripped_msg = stripped_msg[:pagi.span()[0]]
        else:
            page = 1

        if method == 's':
            results = self.plugins[provider].search(stripped_msg, page,
                                                    self.conf[Music.CONF_SEARCH_RESULTS_LIMIT])
            if results is not None:
                self.query_state[conn_name][message.sender.id] = results

                s = '\n'.join(
                    [Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in
                     enumerate(results.entries)])
                s += '\n' + str(results.page) + "/" + str(results.pages)

                wrapper.reply(s)
                return

        elif method == 'p':
            results = self.plugins[provider].search_playlist(stripped_msg, page,
                                                             self.conf[Music.CONF_SEARCH_RESULTS_LIMIT])
            if results is not None:

                self.query_state[conn_name][message.sender.id] = results

                s = '\n'.join(
                    [Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in
                     enumerate(results.entries)])
                s += '\n' + str(results.page) + "/" + str(results.pages)
                wrapper.reply(s)
            else:
                wrapper.reply("No search results.")

    # TODO: populate the query state dict in onjoin
    # TODO: merge next and prev page into one method lol
    # There are known bugs with certain music APIs so we don't bother if the user requests a page no beyond total pages
    # e.g. angela aki this love in NetEase song
    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_next_page(self, wrapper, message, conn_name, dm):
        if conn_name in self.query_state and message.sender.id in self.query_state[conn_name]:
            qs = self.query_state[conn_name][message.sender.id]
            if qs.type == Query_Type.song:
                if qs.plugin == NetEasePlugin.name():
                    qs_new = self.plugins[qs.plugin].search(qs.kwd, qs.page + 1, qs.limit)

                elif qs.plugin == YouTubePlugin.name() and qs.next_pg_token is not None:
                    qs_new = self.plugins[qs.plugin].search(qs.kwd, qs.next_pg_token, qs.limit)
                    qs_new.cur_pg_token = qs_new.page
                    qs_new.page = qs.page + 1

                elif qs.plugin == SoundCloudPlugin.name():
                    qs_new = self.plugins[qs.plugin].search(qs.kwd, qs.page + 1, qs.limit)

            elif qs.type == Query_Type.playlist:
                if qs.plugin == NetEasePlugin.name() or SoundCloudPlugin.name():
                    qs_new = self.plugins[qs.plugin].search_playlist(qs.kwd, qs.page + 1, qs.limit)

                elif qs.plugin == YouTubePlugin.name() and qs.next_pg_token is not None:
                    qs_new = self.plugins[qs.plugin].search_playlist(qs.kwd, qs.next_pg_token, qs.limit)
                    qs_new.cur_pg_token = qs_new.page
                    qs_new.page = qs.page + 1

            self.logger.debug(type(qs.plugin))
            if qs_new is not None:
                self.query_state[conn_name][message.sender.id] = qs_new
                s = '\n'.join([Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in
                               enumerate(qs_new.entries)])
                s += '\n' + str(qs_new.page) + "/" + str(qs_new.pages)
                wrapper.reply(s)

        else:
            wrapper.reply("Search for some music first.")

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_prev_page(self, wrapper, message, conn_name, dm):
        if conn_name in self.query_state and message.sender.id in self.query_state[conn_name]:
            qs = self.query_state[conn_name][message.sender.id]
            if qs.page == 1:
                qs_new = qs
            else:
                if qs.type == Query_Type.song:
                    if qs.plugin == NetEasePlugin.name():
                        qs_new = self.plugins[qs.plugin].search(qs.kwd, qs.page - 1, qs.limit)


                    elif qs.plugin == YouTubePlugin.name() and qs.prev_pg_token is not None:
                        qs_new = self.plugins[qs.plugin].search(qs.kwd, qs.prev_pg_token, qs.limit)
                        qs_new.cur_pg_token = qs_new.page
                        qs_new.page = qs.page - 1

                    elif qs.plugin == SoundCloudPlugin.name():
                        qs_new = self.plugins[qs.plugin].search(qs.kwd, qs.page - 1, qs.limit)

                elif qs.type == Query_Type.playlist:
                    if qs.plugin == NetEasePlugin.name() or SoundCloudPlugin.name():
                        qs_new = self.plugins[qs.plugin].search_playlist(qs.kwd, qs.page - 1, qs.limit)

                    elif qs.plugin == YouTubePlugin.name() and qs.prev_pg_token is not None:
                        qs_new = self.plugins[qs.plugin].search_playlist(qs.kwd, qs.prev_pg_token, qs.limit)
                        qs_new.cur_pg_token = qs_new.page
                        qs_new.page = qs.page - 1

                if qs_new is not None:
                    self.query_state[conn_name][message.sender.id] = qs_new
                    s = '\n'.join([Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in
                                   enumerate(qs_new.entries)])
                    s += '\n' + str(qs_new.page) + "/" + str(qs_new.pages)
                    wrapper.reply(s)

        else:
            wrapper.reply("Search for some music first.")

    def _start_music_loop(self, wrapper, message, conn_name):
        if self._get_music_player(conn_name).player_state == MusicPlayer.PlayerState.STOPPED:
            self._get_music_player(conn_name).start_play_loop()
        else:
            wrapper.reply("Music is already playing.")

    def _stop_music_loop(self, wrapper, message, conn_name):
        if self._get_music_player(conn_name).player_state != MusicPlayer.PlayerState.STOPPED:
            self._get_music_player(conn_name).stop_play_loop()
            wrapper.reply("Stopped.")
            self.logger.debug(self._get_music_player(conn_name).player_state)
        else:
            wrapper.reply("Music is not playing.")

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_play(self, wrapper, message, conn_name, dm):
        # try:
        if conn_name in self.query_state and message.sender.id in self.query_state[conn_name]:
            qs = self.query_state[conn_name][message.sender.id]
            stripped_msg = message.message[6:]

            if stripped_msg.isdigit() and int(stripped_msg) < qs.limit:
                if qs.type == Query_Type.playlist:
                    # preload the songs list so muqueue works
                    qs.entries[int(stripped_msg)].get_song_list(self.plugins[qs.plugin])
                self._get_music_player(conn_name).add_to_queue(qs.entries[int(stripped_msg)])
                wrapper.dm("Added " + qs.entries[int(stripped_msg)].name + " to queue.")
        else:
            wrapper.reply("Search for some music first.")
        # except Exception:
        #     self.logger.error(traceback.format_exc())

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_remove(self, wrapper, message, conn_name, dm):
        mplayer = self._get_music_player(conn_name)
        split = message.message.split()
        idx = split[-1]
        if idx.isdigit() and int(idx) < len(mplayer.music_queue_mgr.get_q()):
            if mplayer.music_queue_mgr.remove_q_item(int(idx)):
                self.bot.action(conn_name, "Removed item " + str(idx) + " from queue.")


    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_now_playing(self, wrapper, message, conn_name, dm):
        mplayer = self._get_music_player(conn_name)
        if mplayer.player_state != MusicPlayer.PlayerState.PLAYING_WAIT:
            wrapper.reply("No song is playing.")
        else:
            m, sec = divmod(mplayer.now_playing_song.progress, 60)
            d_m, d_sec = divmod( float(mplayer.now_playing_song.duration)/1000, 60)
            s = ""
            s += mplayer.now_playing_song.plugin + " "
            s += mplayer.now_playing_song.artist + "-" + mplayer.now_playing_song.name + "\n"
            prog = "%d:%d/%d:%d" % (m,sec,d_m,d_sec)
            s += prog
            url = self._get_plugin(mplayer.now_playing_song.plugin).get_item_info_url(mplayer.now_playing_song)
            wrapper.reply_url(s, url)

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_queue_info(self, wrapper, message, conn_name, dm):
        mplayer = self._get_music_player(conn_name)
        if mplayer.music_queue_mgr.isEmpty():
            s = "Queue is empty."
        else:
            s = ""
            for idx, item in enumerate(mplayer.music_queue_mgr.get_q()):
                if type(item) is Playlist:
                    plugin = self.plugins[item.plugin]

                    s += str(idx) +": 🅟 " + item.name + str(len(item.get_song_list(plugin))) + "/" + str(item.song_count)
                elif type(item) is Song:
                    s += str(idx)+": 🅢 " + item.name
                s += "\n"

        # The queue could be very long, and we want users to be able to remove.
        wrapper.dm(s)

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_item_info(self, wrapper, message, conn_name, dm):

        try:
            queue = self._get_music_player(conn_name).music_queue_mgr.get_q()
            split = message.message.split()
            idx = split[-1]
            s = ""
            if idx.isdigit() and int(idx) < len(queue):
                item = queue[int(idx)]
                if type(item) is Song:
                    url = self._get_plugin(item.plugin).get_item_info_url(item)
                    s += ("%s-%s" % (item.artist, item.name))
                    minutes, seconds = divmod( float(item.duration)/1000, 60)
                    s += " %d:%d" % (minutes, seconds)
                    wrapper.reply_url(s, url)

                elif type(item) is Playlist:
                    url = self._get_plugin(item.plugin).get_item_info_url(item)
                    s += "%s %d" % (item.name, item.song_count)
                    wrapper.reply_url(s, url)

        except Exception:
            self.logger.error(traceback.format_exc())


    def _process_clear(self, wrapper, message, conn_name):
        self._get_music_player(conn_name).music_queue_mgr.clear_q()
        wrapper.reply('Queue cleared.')

    # !muskip 10 -p
    def _process_skip(self, wrapper, message, conn_name):
        number_regex = re.compile(r"\d+")
        skip_amt = number_regex.search(message.message)
        # if there is a number...
        if skip_amt is not None:
            skip_amt = int(skip_amt.group())
        else:
            skip_amt = 0

        mplayer = self._get_music_player(conn_name)
        if mplayer.player_state == MusicPlayer.PlayerState.PLAYING_WAIT:
            if "-p" in message.message:
                mplayer.skip_items(items_to_skip=skip_amt)
            else:
                mplayer.skip_song(songs_to_skip=skip_amt)
        else:
            wrapper.reply("Not currently playing a song.")

    def _process_shuffle(self, wrapper, message, conn_name):
        if message.message == "!shuffle all":
            self._get_music_player(conn_name).play_mode = MusicPlayer.PlayMode.SHUFFLE_ALL
            self.bot.action(conn_name, "Shuffling.")
        elif message.message == "!shuffle repeat":
            self._get_music_player(conn_name).play_mode = MusicPlayer.PlayMode.SHUFFLE_REPEAT
            self.bot.action(conn_name, "Shuffling in repeat.")

    def _process_repeat(self, wrapper, message, conn_name):
        mplayer = self._get_music_player(conn_name)
        if message.message == "!repeat single":
            if mplayer.player_state != MusicPlayer.PlayerState.PLAYING_WAIT:
                wrapper.reply("Not currently playing a song")
            else:
            #     add the currently playing song back into the queue if in one of the popping play modes
                if mplayer.play_mode == MusicPlayer.PlayMode.SHUFFLE_ALL or mplayer.play_mode == MusicPlayer.PlayMode.REGULAR:
                    mplayer.add_to_queue(mplayer.now_playing_song)
                mplayer.play_mode = MusicPlayer.PlayMode.REPEAT_SINGLE
                self.bot.action(conn_name, "Repeating this song.")

        elif message.message == "!repeat all":
            # TODO: handle repeat all cmd
            pass

    def _process_regular(self, wrapper, message, conn_name):
        self._get_music_player(conn_name).play_mode = MusicPlayer.PlayMode.REGULAR
        self.bot.action(conn_name, "Playing normally.")

    @staticmethod
    def check_cmd(cmd_string):
        return Module.CMD_VALID

    def handler(self, conn_name, message):
        if message.message.startswith("!neq "):
                # self._process_search(conn_name, message, NetEasePlugin.name())
            self._process_search(self.bot.get_wrapper(conn_name, message), message, NetEasePlugin.name(),
                                 conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])
        # if message.message.startswith("!ytq "):
        #     self._process_search(self.bot.get_wrapper(conn_name, message), message, YouTubePlugin.name(),
        #                          conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])

        if message.message.startswith("!scq "):
            self._process_search(self.bot.get_wrapper(conn_name, message), message, SoundCloudPlugin.name(),
                                 conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])

        if message.message == "!munext":
            self._process_next_page(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message == "!muprev":
            self._process_prev_page(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])

        if message.message.startswith("!play "):
            self._process_play(self.bot.get_wrapper(conn_name, message), message, conn_name,
                                    not self.conf[Music.CONF_RESPOND_IN_ROOM])

        # now playing
        if message.message == "!np":
            self._process_now_playing(self.bot.get_wrapper(conn_name, message), message, conn_name,
                                    not self.conf[Music.CONF_RESPOND_IN_ROOM])

        if message.message.startswith("!shuffle"):
            self._process_shuffle(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message.startswith("!regular"):
            self._process_regular(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message.startswith("!repeat"):
            self._process_repeat(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message.startswith("!remove"):
            self._process_remove(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])

        if message.message == "!mustart":
            self._start_music_loop(self.bot.get_wrapper(conn_name, message), message, conn_name)
        if message.message == "!mustop":
            self._stop_music_loop(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message == "!muqueue" or message.message == "!muq":
            self._process_queue_info(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])

        if message.message.startswith("!muskip"):
            self._process_skip(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message == "!muclear":
            self._process_clear(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message.startswith("!muinfo"):
            self._process_item_info(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])



    def _get_music_player(self, conn) -> MusicPlayer:
        return self.music_players[conn]

    def _get_plugin(self, plugin_name) -> MusicPlugin:
        return self.plugins[plugin_name]

    def __init__(self, config_mgr, perms_mgr, bot):
        super(Music, self).__init__(config_mgr, perms_mgr, bot)
        self.logger = logging.getLogger(__name__)

        if Music.CONF_RESUME_AFTER_INTERRUPTED_KEY not in self.conf:
            self.conf[Music.CONF_RESUME_AFTER_INTERRUPTED_KEY] = True

        if Music.CONF_SEARCH_RESULTS_LIMIT not in self.conf:
            self.conf[Music.CONF_SEARCH_RESULTS_LIMIT] = 10

        if Music.CONF_PLAYLIST_CACHE_FILE_KEY not in self.conf:
            self.conf[Music.CONF_PLAYLIST_CACHE_FILE_KEY] = "idle_cache.fs"

        if Music.CONF_RESPOND_IN_ROOM not in self.conf:
            self.conf[Music.CONF_RESPOND_IN_ROOM] = True

        if Music.CONF_IDLE_SHUFFLE_KEY not in self.conf:
            self.conf[Music.CONF_IDLE_SHUFFLE_KEY] = True

        self.save_config()

        self.get_new_event_loop(Music.KEY_EVT_LOOP)

        # map of music source name to the music plugin
        self.plugins = {}
        self.plugins[NetEasePlugin.name()] = NetEasePlugin(self.get_event_loop(Music.KEY_EVT_LOOP), self.conf,
                                                           self.save_config)
        # self.plugins[YouTubePlugin.name()] = YouTubePlugin(self.get_event_loop(Music.KEY_EVT_LOOP), self.conf,
        #                                                    self.save_config)

        self.plugins[SoundCloudPlugin.name()] = SoundCloudPlugin(self.get_event_loop(Music.KEY_EVT_LOOP), self.conf,
                                                                 self.save_config)
        # map of conn name to the music player
        self.music_players = {}

        # dict of conn_name to user id to last search progress, so people can navigate through menus easily
        # could be problematic, someone with the same user and tripcode in different channels searching for the same song..
        self.query_state = {}

