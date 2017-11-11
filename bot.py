from cmd import Cmd
import networking

import importlib
import json
import os
import threading
import functools
import queue
import datetime
import logging
import module_mgr
import perms_mgr
import traceback

import asyncio
import concurrent.futures

# There is only one instance of bot at any time.

# todo: error checking like attempting to join room in the middle of a resume
class bot:

    '''dict of conn name to networking.connection object'''
    conn = None
    config_mgr = None
    module_mgr = None

    executor = None

### callbacks when in a room loop begin here
# for simplicity just call these directly from the connection loop INSIDE ITS THREAD
# if this were a large scale IRC bot would probably use the consumer-producer design pattern
# we can gracefully

    # todo, not called yet (supposed to only be called once), add scrollback?
    async def onjoin(self, loop, conn_name, scrollback):
        pass

    async def onleave(self, loop, conn_name):
        # asyncio.Task.current_task().name = "cleanup"
        for k, v in self.module_mgr.get_modules().items():
            loop.run_in_executor(self.executor, v.onleave, conn_name)

    # allow the plugin to access the room from the bot
    async def handler(self, loop, conn_name, message):
        for k, v in self.module_mgr.get_modules().items():
            # asyncio.ensure_future(loop.run_in_executor(self.executor,v.handler, conn_name, message))
            loop.run_in_executor(self.executor, v.handler, conn_name, message)
### callbacks end here

### sending begins here, meant to be called by plugins only
    def send(self, conn, msg):
        self.conn[conn].send(msg)

    def send_url(self, conn, msg, url):
        pass

    def dm(self, conn, uid, msg):
        self.conn[conn].dm(uid, msg)

    def dm_url(self, conn, uid, msg, url):
        pass

    def play_music(self, conn, name, url):
        pass

    def handover_host(self, conn, uid):
        self.conn[conn].handover_host(uid)

    def kick(self, conn, uid):
        pass

    def ban(self, conn, uid):
        pass

    def report_ban(self, conn, uid):
        pass

    def set_room_name(self, conn, name):
        pass

    def set_room_topic(self, conn, desc):
        pass

### sending ends here

    def reset(self, conn):
        self.conn[conn].reset()

    def terminate(self):
        # todo: gracefully disconnect etc.
        for _, v in self.conn.items():
            v.close()

    # def _get_rooms(self, event, queue, stat, resp):
    #     if stat == 200:
    #         resp_parsed = json.loads(resp)
    #         # should be a list
    #         queue.put(resp_parsed['rooms'])
    #     else:
    #         queue.put([])
    #     event.set()

    def leave(self, conn_name):
        if self.conn[conn_name].room is not None:
            self.conn[conn_name].leave_room()
        pass

    # similar to login/resume just print errors from within this function
    # don't need to be blocking/callback for now?? (perhaps turn it into a proper library and make exceptions later
    def join(self, conn_name, room_id):
        if self.conn[conn_name].room is None:
            self.conn[conn_name].join_room(room_id)
        else:
            self.logger.warning("already in room, logout first")

    # let's just make this blocking
    # queue is inherently thread safe so let's use that
    # def get_rooms(self, conn_name):
    #     event = threading.Event()
    #     q = queue.Queue()
    #     cb_with_event = functools.partial(self._get_rooms, event, q)
    #
    #     self.conn[conn_name].get_lounge(lambda stat, resp:
    #                                         cb_with_event(stat, resp))
    #     event.wait()
    #     return q.get()

    def get_rooms(self, conn_name):
        stat, resp = self.conn[conn_name].get_lounge_blocking()
        if stat == 200:
            resp_parsed = json.loads(resp)
            # should be a list
            return resp_parsed['rooms']
        else:
            return []

    def login(self, conn_name):
        stat, resp = self.conn[conn_name].get_login_token()
        self.logger.debug('status: %d, resp: %s' % (stat, resp))

        if stat == 200:
            resp_parsed = json.loads(resp)
            token = resp_parsed['token']
            self.logger.debug("token value " + token)
            (stat, resp, cookie_jar) = self.conn[conn_name].login()

            # logged in and received the drrr-session-1 cookie
            self.logger.debug('status: %d, resp: %s' % (stat, resp))
            if stat == 200:
                resp_parsed = json.loads(resp)
                if resp_parsed['message'] == 'ok':
                    cookie_path = os.path.join(os.path.abspath(self.config_mgr.cookies_dir())
                                               , self.conn[conn_name].id + ".cookie")
                    self.logger.debug(cookie_path)
                    cookie_jar.save(cookie_path)
                    self.logger.debug("successfully logged in and cached cookies!")
                else:
                    self.logger.warning("not ok???")
            else:
                self.logger.warning("unable to perform login")

            self.logger.error("unable to obtain login token")



    """
    Resume the room loop if the saved cookies happens to be in a room
    """
    def resume(self, conn_name):
        cookies_file = os.path.join(os.path.abspath(self.config_mgr.cookies_dir())
                                           , self.conn[conn_name].id+".cookie")
        if os.path.isfile(cookies_file):
            self.conn[conn_name].resume(cookies_file)
        else:
            self.logger.debug("no saved cookies for conn "+ str(conn_name))

    def __init__(self, config_mgr):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)

        # todo: check for cache.pkl

        if not os.path.isdir(config_mgr.cookies_dir()):
            os.mkdir(config_mgr.cookies_dir())

        self.config_mgr = config_mgr
        self.perms_mgr = perms_mgr.perms_mgr(config_mgr)


        self.module_mgr = module_mgr.module_mgr(config_mgr, 'modules')
        self.module_mgr.load_module("TimeReporter", self)
        self.module_mgr.load_module("Admin", self)

        # time_reporter = getattr(importlib.import_module('modules.TimeReporter'), "TimeReporter")
        # print(time_reporter)
        # self.modules[time_reporter.name()] = time_reporter(bot=self)


        self.conn = {}

        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=8)

        # todo: or else resume
        for key, value in config_mgr.get_conns().items():
            self.conn[key] = networking.connection(key, value['username_incl_tripcode'],
                                              value['avatar'],
                                                   self.onjoin, self.onleave, self.handler, config_mgr.get_networking_block())


        # for i, x in enumerate(json_config['connections']):
        #     self.conn.append(networking.connection(i, x['username_incl_tripcode'],
        #                                       x['avatar'],
        #                                     "https://" if json_config['use_https'] else "http://" + json_config['drrr_domain']))

        # todo: autoconnect?
        self.logger.debug("attempting to resume connections")
        # todo: pass the global message callback in here?
        for key in self.conn:
            self.resume(key)
        # self.cli_instance = _BotCLI(self)
        # self.cli_instance.prompt = "> "


# Idea of the CLI is that we first select a connection with "room 1/2/3"
# https://stackoverflow.com/questions/8813291/better-handling-of-keyboardinterrupt-in-cmd-cmd-command-line-interpreter
# todo: figure out how to do exception catching without messing up the cli loop
class BotCLI(Cmd):

    active_room = None

    def __init__(self, bot):
        self.bot = bot
        super(BotCLI,self).__init__()

    def do_quit(self, args):
        """Quits the program."""
        self.bot.terminate()
        print("Quitting.")
        raise SystemExit

    def do_login(self, args):
        """Perform the initial login """
        arg_split = args.split()
        if len(arg_split) != 1:
            print("provide a connection name")
        else:
            self.bot.login(arg_split[0])

    def do_status(self, args):
        """Gives an overview of connections and rooms."""
        # print (self.bot.conn)
        for k, v in self.bot.conn.items():
            print( '%s: connected: %s, room: %s' % (k, v.room_connected, v.room if v.room is not None else "None"))

    def do_reset(self, args):
        """reset the event loop, in case it gets stuck or an exception we haven't debugged is raised..."""
        arg_split = args.split()
        if len(arg_split) != 1:
            print("provide a connection name")
        else:
            self.bot.reset(arg_split[0]) if arg_split[0] in self.bot.conn.keys() else print("invalid arg")

    def do_resume(self, args):
        """Resumes a specific connection (typically used after a manual reset)"""
        arg_split = args.split()
        if len(arg_split) != 1:
            print("provide a connection name")
        else:
            self.bot.resume(arg_split[0]) if arg_split[0] in self.bot.conn.keys() else print("invalid arg")

    def do_join(self, args):
        """First arg is the connection. 2nd arg is the room ID"""
        arg_split = args.split()
        if len(arg_split) != 2:
            print("provide a conn name and a room ID")
        else:
            self.bot.join(arg_split[0], arg_split[1])

    def do_leave(self, args):
        """Leaves the room, first argument is the connection"""
        arg_split = args.split()
        if len(arg_split) != 1:
            print("provide a connection name")
        else:
            self.bot.leave(arg_split[0]) if arg_split[0] in self.bot.conn.keys() else print("invalid arg")


    # todo: add functionality like filtering by time, language, 18+ etc
    def do_rooms(self, args):
        """Lists all public rooms in the drrr.com lounge"""
        arg_split = args.split()
        if len(arg_split) != 1:
            print("provide a conn name")
        else:
            room_details = self.bot.get_rooms(arg_split[0])
            print (str(len(room_details)) + " rooms")
            print ("id | name | desc | lang | since | ppl ")
            for i in room_details:
                print("%s | %s | %s | %s | %s | %s" % (i['id'], i['name'],
                                    i['description'], i['language'],
                                                       datetime.datetime.fromtimestamp(int(i['since'])).strftime('%Y-%m-%d %H:%M:%S'),
                                                       str(i['total']) + "/" + str(i['limit'])))

    # todo: handle more specific types of non-fatal exceptions..
    def cmdloop_with_keyboard_interrupt(self):
        # doQuit = False
        # while doQuit != True:
        while True:
            try:
                self.cmdloop()
                # doQuit = True
            except Exception:
                print(traceback.format_exc())

    def do_list_modules(self, args):
        """Lists all loaded modules."""
        print(self.bot.module_mgr.get_modules().keys())

    def do_load_module(self, args):
        arg_split = args.split()
        if len(arg_split) != 1:
            print("single arg, plugin name")
            return
        self.bot.module_mgr.load_module(arg_split[0], self.bot)

    def do_unload_module(self, args):
        arg_split = args.split()
        if len(arg_split) != 1:
            print("single arg, plugin name")
            return
        self.bot.module_mgr.unload_module(arg_split[0])

    def do_reload_module(self, args):
        arg_split = args.split()
        if len(arg_split) != 1:
            print("single arg, plugin name")
            return
        if self.bot.module_mgr.reload_module(arg_split[0], self.bot):
            print("success")
        else:
            print("fail")

    def do_save_cfg(self, args):
        pass


    def do_cmd(self, args):
        """execute a command as if from within drrr"""
        pass


# admin plugin first, next!!! join other rooms, handover OP, say, etc.
#