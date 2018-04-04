# "abstract class" for what methods a module should implement
# each module should have its own configurable storage.
# done: Admin module so that can manage the bot from within drrr

from abc import ABCMeta, abstractmethod, abstractproperty

# done: rewrite admin check, throttling, and other features using decorators
# http://scottlobdell.me/2015/04/decorators-arguments-python/

import asyncio, threading, logging

class PendingWait:
    CHECK_PASSED = 0
    CHECK_FAILED = 1

    def __init__(self, future, check):
        self.future = future
        self.check = check

class Module(metaclass=ABCMeta):

    CMD_VALID = 0
    CMD_INVALID = 1
    CMD_PARTIALLY_VALID = 2


    @abstractproperty
    @staticmethod
    def name():
        pass

    @abstractmethod
    def unload(self):
        pass

    # handle the scrollback, which should be a list of Messages (Logger plugin)
    @abstractmethod
    def onjoin(self, conn_name, scrollback):
        pass

    # may need to stop tasks or event loops for particular channels!!!
    @abstractmethod
    def onleave(self, conn_name):
        pass

    @staticmethod
    def check_cmd(cmd_string):
        """Returns CMD_VALID, CMD_PARTIALLY_VALID, or CMD_INVALID"""
        pass

    @abstractmethod
    def handler(self, conn_name, message):
        pass

    # similar in spirit to https://github.com/Rapptz/discord.py/blob/09bd2f4de7cccbd5d33f61e5257e1d4dc96b5caa/discord/client.py
    # check should be a function that accepts a wrapper and a message
    async def wait_for_message(self, loop, check, timeout=10):
        f = asyncio.Future(loop=loop)
        p = PendingWait(f, check)
        self._waiting_message_futures.append(p)
        try:
            match_msg = await asyncio.wait_for(f, timeout, loop=loop)
        except asyncio.TimeoutError:
            match_msg = None

        self._waiting_message_futures.remove(p)
        return match_msg

    # event loop management methods below

    def stop_event_loop_safely(self, loop_name):
        if loop_name in self._event_loops:
            x = self._event_loops[loop_name]
            x.call_soon_threadsafe(x.stop)
            for task in asyncio.Task.all_tasks(loop=x):
                try:
                    task.cancel()
                except asyncio.CancelledError:
                    self._logger.debug("A running event task was cancelled in loop " + loop_name)
            del self._event_loops[loop_name]

    def cancel_all_event_loops(self):
        for loop_name in list(self.get_event_loops().keys()):
            self.stop_event_loop_safely(loop_name)


    # returns a dict of name to event loop
    def get_event_loops(self):
        return self._event_loops

    def get_event_loop(self, name):
        if name in self._event_loops:
            return self._event_loops[name]
        else:
            return None

    def _start_event_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def get_new_event_loop(self, name):
    # no need to keep a reference to the thread, not like we can forcefully stop it on its own anyways..
        if name not in self._event_loops:
            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=self._start_event_loop, args=(loop,))
            thread.start()
            self._event_loops[name] = loop
            return loop
        else:
            return None

    # event loop management methods end



    def save_config(self):
        self._config_mgr.write()

    def load_config(self):
        self.conf = self._config_mgr.get_plugin_spec(self.__class__.name())

    # need bot to send, rather messy because of circular referencing..
    # remember to call perms_mgr.allow before is_allowed..
    def __init__(self, config_mgr, perms_mgr, bot):
        self._event_loops = {}

        self._waiting_message_futures = []

        self._logger = logging.getLogger(self.__class__.name())
        # ch = logging.StreamHandler()
        # ch.setLevel(logging.DEBUG)
        # formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        # ch.setFormatter(formatter)
        # self._logger.setLevel(logging.DEBUG)
        # self._logger.addHandler(ch)

        self._config_mgr = config_mgr
        self.load_config()

        self.perms_mgr = perms_mgr
        self.bot = bot
