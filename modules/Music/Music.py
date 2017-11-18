"""The motivation behind this bot, also an example of how I plan to store persistent data"""

from modules.module import Module
from popyo import *
import asyncio
import threading
import argparse
import re
import shlex
import traceback
from decorators import *
import ZODB, ZODB.FileStorage

from .NetEase import NetEasePlugin
from .MusicPlugin import *

class Music(Module):
    CONF_RESUME_AFTER_INTERRUPTED_KEY = "resume_after_interrupted"
    CONF_SEARCH_RESULTS_LIMIT = "res_limit"
    CONF_PLAYLIST_CACHE_FILE_KEY = "playlist_cache"
    CONF_RESPOND_IN_ROOM = "public_respond"

    circled_numbers_array = ['⓪','①','②','③','④','⑤','⑥','⑦','⑧','⑨','⑩',
                             '⑪','⑫','⑬','⑭','⑮','⑯','⑰','⑱','⑲','⑳']

    # dict of conn_name to user id to last search progress, so people can navigate through menus easily
    # could be problematic, someone with the same user and tripcode in different channels searching for the same song..
    query_state = None

    # I did consider using a queue, but I want to do things like shuffling a list of objects and deleting randomly
    # Idea: instead of waiting on queue.get wait on a semaphore that reflects the number of items in the list
    # should be a dict of conn name to "semaphore", "list"
    music_queue = None

    # should be a dict of conn name to "now_playing", "music_loop_future"
    now_playing_info = None
    def unload(self):
        pass

    def onjoin(self, conn_name, scrollback):
        # self.music_queue[conn_name] = asyncio.Queue()
        # self.bot.send(conn_name, "i joined")
        self.music_queue[conn_name] = {}
        # self.music_queue[conn_name]['semaphore'] = asyncio.BoundedSemaphore(value=0,loop=self.event_loop)
        self.music_queue[conn_name]['semaphore'] = asyncio.Event(loop=self.event_loop)
        self.music_queue[conn_name]['q'] = []

        self.now_playing_info =  {}
        self.now_playing_info[conn_name] = {}
        self.now_playing_info[conn_name]['now_playing'] = None
        self.now_playing_info[conn_name]['music_loop_future'] = None
        self.now_playing_info[conn_name]['sleep_task'] = None

    # todo: fix this shit!for
    def onleave(self, conn_name):
        pass

    def argparser(self):
        pass

    @staticmethod
    def name():
        return "Music"


    # command format: !neq s some song name (netease query, search for songs, song name)
    # def _process_search(self, conn_name, message, provider):
    #     # strip !neq[space]
    #     args = message.message[5:]
    #     self.logger.debug(args)
    #     try:
    #         parsed_args = self.search_argparser.parse_args(shlex.split(args))
    #         if provider == NetEasePlugin.name():
    #             if parsed_args.type == 's':
    #                 results = self.ne_plugin.search(parsed_args.name, 1 if parsed_args.page is None else parsed_args.page,
    #                                       self.conf[Music.CONF_SEARCH_RESULTS_LIMIT])
    #                 if results is not None:
    #                     self.bot.send(conn_name, '\n'.join([str(idx) + ': ' + x.get_short_string() for idx, x in enumerate(results.entries)]))
    #
    #     except Exception as e:
    #         self.logger.error(traceback.format_exc())
    #         s = "Failed to parse arguments"
    #         if message.type == Message_Type.message:
    #             self.bot.send(conn_name, s)
    #         else:
    #             self.bot.dm(conn_name, message.sender.id, s)


    # command format: !neq [s,p,a] song name [-p 1]
    # just use regex, it's easier...
    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_search(self, wrapper, message, provider, conn_name, dm):
        if provider == NetEasePlugin.name():
            begin_idx = 5
            available_methods = ['s', 'p']
            pagination_regex = re.compile(r"-p \d+")

        stripped_msg = message.message[begin_idx:]
    #     do all the validation in one block
        if stripped_msg[0] in available_methods and stripped_msg[1] == ' ':
            method = stripped_msg[0]
            stripped_msg = stripped_msg[2:]
            pagi = pagination_regex.search(stripped_msg)
            if pagi is not None:
                page = int(stripped_msg[pagi.span()[0]: pagi.span()[1]].split()[1])
                stripped_msg = stripped_msg[:pagi.span()[0]]
            else: page = 1
            if method == 's':
                results = self.ne_plugin.search(stripped_msg, page,
                                                      self.conf[Music.CONF_SEARCH_RESULTS_LIMIT])
                s = '\n'.join(
                    [Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in enumerate(results.entries)])
            elif method == 'p':
                results = self.ne_plugin.search_playlist(stripped_msg, page,
                                                self.conf[Music.CONF_SEARCH_RESULTS_LIMIT])
                s = '\n'.join(
                    [Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in enumerate(results.entries)])
            # cache the results so people can do !munext
            if conn_name not in self.query_state:
                self.query_state[conn_name] = {}
            self.query_state[conn_name][message.sender.id] = results

            if results is not None:
                s += '\n' + str(results.page) + "/" + str(results.pages)
                wrapper.reply(s)


        else:
            wrapper.reply("Available Methods: " + str(available_methods))


    # TODO: populate the query state dict in onjoin
    # There are known bugs with certain music APIs so we don't bother if the user requests a page no beyond total pages
    # e.g. angela aki this love in NetEase song
    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_next_page(self, wrapper, message, conn_name, dm):
        if conn_name in self.query_state and message.sender.id in self.query_state[conn_name]:
            qs = self.query_state[conn_name][message.sender.id]
            if qs.type == Query_Type.song:
                if type(qs.plugin) is NetEasePlugin:
                    qs_new = self.ne_plugin.search(qs.kwd, qs.page + 1, qs.limit)
            elif qs.type == Query_Type.playlist:
                if type(qs.plugin) is NetEasePlugin:
                    qs_new = self.ne_plugin.search_playlist(qs.kwd, qs.page + 1, qs.limit)

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
                    if type(qs.plugin) is NetEasePlugin:
                        qs_new = self.ne_plugin.search(qs.kwd, qs.page - 1, qs.limit)
                elif qs.type == Query_Type.playlist:
                    if type(qs.plugin) is NetEasePlugin:
                        qs_new = self.ne_plugin.search_playlist(qs.kwd, qs.page - 1, qs.limit)

                if qs_new is not None:
                    self.query_state[conn_name][message.sender.id] = qs_new
                    s = '\n'.join([Music.circled_numbers_array[idx] + x.get_short_string() for idx, x in
                                   enumerate(qs_new.entries)])
                    s += '\n' + str(qs_new.page) + "/" + str(qs_new.pages)
                    wrapper.reply(s)

        else:
            wrapper.reply("Search for some music first.")

    async def _add_item_to_queue(self, item, conn_name):
        self.music_queue[conn_name]['q'].append(item)
        self.music_queue[conn_name]['semaphore'].set()

    # could play either songs or playlists..
    # !play [0-9]
    # TODO: debug race condition encountered here
    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_play(self, wrapper, message, conn_name, dm):
        try:
            if conn_name in self.query_state and message.sender.id in self.query_state[conn_name]:
                qs = self.query_state[conn_name][message.sender.id]
                stripped_msg = message.message[6:]
                if stripped_msg.isdigit() and int(stripped_msg) <= qs.limit:
                    asyncio.run_coroutine_threadsafe(self._add_item_to_queue(qs.entries[int(stripped_msg)], conn_name), self.event_loop)
                    wrapper.dm("Added " + qs.entries[int(stripped_msg)].name + " to queue.")

            else:
                wrapper.reply("Search for some music first.")
        except Exception:
            self.logger.error(traceback.format_exc())

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_queue_info(self, wrapper, message, conn_name, dm):
        # for item in self.music_queue[conn_name]['q']:

        if not self.music_queue[conn_name]['q']:
            s = "Queue is empty."
        else:
            s = ""
            for item in self.music_queue[conn_name]['q']:
                if type(item) is Playlist:
                    s += "🅟 " + item.name + str(len(item.get_song_list())) + "/" + str(item.song_count)
                elif type(item) is Song:
                    s += "🅢 " + item.name
                s += "\n"
            # s = '\n'.join([item.name for item in self.music_queue[conn_name]['q']])
        wrapper.reply(s)

    # https://quentin.pradet.me/blog/how-do-you-limit-memory-usage-with-asyncio.html
    # https://stackoverflow.com/questions/37209864/interrupt-all-asyncio-sleep-currently-executing
    async def _music_loop(self, conn_name):
        while conn_name in self.playing_music:
            try:
                self.now_playing_info[conn_name]['now_playing'] = None
                self.now_playing_info[conn_name]['sleep_task'] = None
                await self.music_queue[conn_name]['semaphore'].wait()

                item = self.music_queue[conn_name]['q'][0]
                if type(item) is Song:
                    item = self.music_queue[conn_name]['q'].pop(0)
                    url_dict = await item.plugin._get_song_urls_async([item.id])

                    if item.id not in url_dict:
                        self.bot.send(conn_name, "Unable to play " + item.name)
                    else:
                        self.now_playing_info[conn_name]['now_playing'] = item
                        self.bot.play_music(conn_name, item.name + "-" + item.artist, url_dict[item.id])
                        self.logger.debug("playing " + url_dict[item.id] + " in " + conn_name)
                        self.now_playing_info[conn_name]['sleep_task'] = asyncio.ensure_future(asyncio.sleep(float(item.duration)/1000))
                        try:
                            await self.now_playing_info[conn_name]['sleep_task']
                        except asyncio.CancelledError:
                            self.now_playing_info[conn_name]['sleep_task'] = None
                            self.bot.action(conn_name, "Skipping current song.")

                    # self.bot.play_music(conn_name, item.name + "-" + item.artist, item.plugin.get_song_url(item.id))
                elif type(item) is Playlist:
            #         pop only if there are no more songs left in playlist.get_songs_list
                    sg_list = await item.get_song_list_async()
                    self.logger.debug(sg_list)
                    if sg_list == []:
                        self.music_queue[conn_name]['q'].pop(0)

                    else:
                        song = sg_list.pop()

                        url_dict = await item.plugin._get_song_urls_async([song.id])
                        if song.id not in url_dict:
                            self.bot.send(conn_name, "Unable to play " + song.name)
                        else:
                            self.now_playing_info[conn_name]['now_playing'] = item
                            self.bot.play_music(conn_name, song.name + "-" + song.artist, url_dict[song.id])
                            self.now_playing_info[conn_name]['sleep_task'] = asyncio.ensure_future(
                                asyncio.sleep(float(song.duration) / 1000))
                            try:
                                await self.now_playing_info[conn_name]['sleep_task']
                            except asyncio.CancelledError:
                                self.now_playing_info[conn_name]['sleep_task'] = None
                                self.bot.action(conn_name, "Skipping current song.")
                if self.music_queue[conn_name]['q'] != []:
                    self.music_queue[conn_name]['semaphore'].set()
                else:
                    self.music_queue[conn_name]['semaphore'].clear()


            except asyncio.CancelledError:
                self.bot.action(conn_name, "Letting others take the stage. !mustart to resume")
                self.now_playing_info[conn_name]['music_loop_future'] = None
                self.now_playing_info[conn_name]['now_playing'] = None
                break
            except Exception:
                self.logger.error(traceback.format_exc())


    def _start_music_loop(self, wrapper, message, conn_name):
        if (conn_name in self.playing_music):
            wrapper.reply("Already DJing.")
        else:
            self.playing_music.add(conn_name)
            self.now_playing_info[conn_name]['music_loop_future'] = asyncio.run_coroutine_threadsafe(self._music_loop(conn_name), self.event_loop)
            self.bot.action(conn_name, "🎧💿 DJ in the house.")

    async def _cancel_music_loop_future(self, conn_name):
        self.logger.debug(self.now_playing_info[conn_name]['music_loop_future'])
        if self.now_playing_info[conn_name]['music_loop_future'] is not None:
            self.now_playing_info[conn_name]['music_loop_future'].cancel()
            return True
        return False

    def _stop_music_loop(self, wrapper, message, conn_name):
        future = asyncio.run_coroutine_threadsafe(self._cancel_music_loop_future(conn_name), self.event_loop)
        if not future.result():
            wrapper.reply("Not DJing.")

    @conditional_dm("Use this cmd in DM because it is noisy")
    def _process_now_playing(self, wrapper, message, conn_name, dm):
        if self.now_playing_info[conn_name] is not None:
            wrapper.reply(self.now_playing_info[conn_name].get_short_string())

    async def _cancel_sleep_task(self, conn_name):
        if self.now_playing_info[conn_name]['sleep_task'] is not None:
            self.now_playing_info[conn_name]['sleep_task'].cancel()
            return True
        else:
            return False

    def _process_skip(self, wrapper, message, conn_name):
        future = asyncio.run_coroutine_threadsafe(self._cancel_sleep_task(conn_name), self.event_loop)
        if not future.result():
            wrapper.reply("DJ is not playing any song.")


    def handler(self, conn_name, message):
        # self.bot.send(conn=conn_name, msg="Received a Message!")
        # if self.conf[Music.CONF_RESPOND_IN_ROOM] and message.type == Message_Type.message \
        #         or message.type == Message_Type.dm:
        if message.message.startswith("!neq "):
                # self._process_search(conn_name, message, NetEasePlugin.name())
            self._process_search(self.bot.get_wrapper(conn_name, message), message, NetEasePlugin.name(),
                                 conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message == "!munext":
            self._process_next_page(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message == "!muprev":
            self._process_prev_page(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message.startswith("!play "):
            self._process_play(self.bot.get_wrapper(conn_name, message), message, conn_name,
                                    not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message == "!mustart":
            self._start_music_loop(self.bot.get_wrapper(conn_name, message), message, conn_name)
        if message.message == "!mustop":
            self._stop_music_loop(self.bot.get_wrapper(conn_name, message), message, conn_name)
        # if message.message == "!nowplaying":
        #     self._process_now_playing(self.bot.get_wrapper(conn_name, message), message, conn_name,
        #                              not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message == "!muqueue":
            self._process_queue_info(self.bot.get_wrapper(conn_name, message), message, conn_name, not self.conf[Music.CONF_RESPOND_IN_ROOM])
        if message.message == "!muskip":
            self._process_skip(self.bot.get_wrapper(conn_name, message), message, conn_name)

        if message.message == "!muclear":
            self._process_clear(self.bot.get_wrapper(conn_name, message), message, conn_name)

    # https://stackoverflow.com/questions/8878478/how-can-use-pythons-argparse-with-a-predefined-argument-string
    # https://stackoverflow.com/questions/34256250/parsing-a-string-with-spaces-from-command-line-in-python/34256358#34256358
    # If we want to avoid having to double quote song names with spaces in them
    # quick and dirty method of parsing arguments...
    # def _init_search_argparser(self):
    #     self.search_argparser = argparse.ArgumentParser()
    #     self.search_argparser.add_argument('type', choices=['s', 'p'], type=str)
    #     self.search_argparser.add_argument('-n', '--name', type=str, required=True)
    #     self.search_argparser.add_argument('-p', '--page', type=int)

    # event loop to do all our http queries on and song playlist waiting
    def start_event_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def __init__(self, config_mgr, perms_mgr, bot):
        super(Music, self).__init__(config_mgr, perms_mgr, bot)
        self.logger = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(ch)

        self.query_state = {}

        if Music.CONF_RESUME_AFTER_INTERRUPTED_KEY not in self.conf:
            self.conf[Music.CONF_RESUME_AFTER_INTERRUPTED_KEY] = True

        if Music.CONF_SEARCH_RESULTS_LIMIT not in self.conf:
            self.conf[Music.CONF_SEARCH_RESULTS_LIMIT] = 10

        if Music.CONF_PLAYLIST_CACHE_FILE_KEY not in self.conf:
            self.conf[Music.CONF_PLAYLIST_CACHE_FILE_KEY] = "pl_cache.fs"

        if Music.CONF_RESPOND_IN_ROOM not in self.conf:
            self.conf[Music.CONF_RESPOND_IN_ROOM] = True

        self.save_config()

        # 1 event loop for all the searching and playing across different plugins, easier to manage
        self.event_loop = asyncio.new_event_loop()
        self.event_loop_thread = threading.Thread(target=self.start_event_loop, args=(self.event_loop,))
        self.event_loop_thread.start()

        self.ne_plugin = NetEasePlugin(self.event_loop, self.conf, self.save_config)

        # self._init_search_argparser()
        self.music_queue = {}
        self.playing_music = set()