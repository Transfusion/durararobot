"""Reports the time at a predefined interval"""

import logging
import asyncio
import threading
from modules.module import Module
from popyo import *
from datetime import datetime
from decorators import *

# also an example of how I would write a non blocking loop that does something at certain intervals
# todo: refactor to support multiple rooms, likely broken

class TimeReporter(Module):

    CONF_REPORT_INTERVAL_KEY = 'interval'
    CONF_TIME_FORMAT_KEY = 'time_format'

    # set of connnection names which have active time loops
    repeating_tasks = None

    def unload(self):
        self.stop_loop()

    def onjoin(self, conn_name, scrollback):
        pass

    def onleave(self, conn_name):
        self.stop_repeating_task(conn_name)

    def argparser(self):
        pass

    @staticmethod
    def name():
        return "TimeReporter"

    def stop_loop(self):
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        for task in asyncio.Task.all_tasks(loop=self.event_loop):
            task.cancel()

    def stop_repeating_task(self, conn_name):
        if conn_name in self.repeating_tasks: self.repeating_tasks.remove(conn_name)
        for task in asyncio.Task.all_tasks(loop=self.event_loop):
            if task.name == conn_name:
                task.cancel()

    def start_event_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()


    async def _broadcast_time_loop(self, conn_name):
        # keep track of the current task for this loop.
        asyncio.Task.current_task().name = conn_name
        while conn_name in self.repeating_tasks:
            self.bot.send(conn=conn_name, msg=datetime.utcnow().strftime(self.conf['time_format']))
            await asyncio.sleep(self.conf['interval'])

    # need to start in another thread so that don't exhaust one of the threads of the ThreadPoolExecutor
    def start_loop(self, conn_name):
        if conn_name in self.repeating_tasks:
            self.bot.send(conn=conn_name, msg="A time loop is already running. Call !time report stop first")
        else:
            self.repeating_tasks.add(conn_name)
            asyncio.run_coroutine_threadsafe(self._broadcast_time_loop(conn_name), self.event_loop)

    @require_dm("Can only be called by an admin in DM.")
    @require_admin("You are not an admin!!")
    def _time_interval(self, wrapper, message):
        split = message.message.split()
        args = len(split) - 2
        if args == 0:
            wrapper.dm(str(self.conf['interval']) + " seconds")
        elif args == 1 and split[-1].isdigit():
            self.conf['interval'] = int(split[-1])
            self._config_mgr.write()



    def handler(self, conn_name, message):
        if message.type == Message_Type.message:
            if message.message == "!time report":
                self.start_loop(conn_name)
            elif message.message == "!time report stop":
                if conn_name in self.repeating_tasks:
                    self.stop_repeating_task(conn_name)
                    self.bot.send(conn_name, "time reporting stopped")
                else:
                    self.bot.send(conn_name, "not in time loop")
            elif message.message == "!time now":
                self.bot.send(conn=conn_name, msg=datetime.utcnow().strftime(self.conf['time_format'] ))

        # if message.type == Message_Type.dm:
        if message.message.startswith("!time interval"):
            self._time_interval(self.bot.get_wrapper(conn_name, message), message)
                # split = message.message.split()
                # args = len(split) - 2
                # if args == 0:
                #     self.bot.dm(conn_name, message.sender.id, str(self.conf['interval']) + " seconds")
                # elif args == 1 and split[-1].isdigit():
                #     if self.perms_mgr.is_admin(message.sender):
                #         self.conf['interval'] = int(split[-1])
                #         self._config_mgr.write()
                #     else:
                #         self.bot.dm(conn_name, message.sender.id, "Error: You are not an admin")

    def __init__(self, config_mgr, perms_mgr, bot):
        super(TimeReporter, self).__init__(config_mgr, perms_mgr, bot)

        self.logger = logging.getLogger(__name__)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        self.logger.setLevel(logging.DEBUG)
        self.logger.addHandler(ch)

        # interval in seconds
        if TimeReporter.CONF_REPORT_INTERVAL_KEY not in self.conf:
            self.conf[TimeReporter.CONF_REPORT_INTERVAL_KEY] = 5
            self._config_mgr.write()
        if TimeReporter.CONF_TIME_FORMAT_KEY not in self.conf:
            self.conf[TimeReporter.CONF_TIME_FORMAT_KEY] = '%Y-%m-%d %H:%M:%S'
            self._config_mgr.write()

        self.event_loop = asyncio.new_event_loop()
        self.event_loop_thread = threading.Thread(target=self.start_event_loop, args=(self.event_loop,))
        self.event_loop_thread.start()

        self.repeating_tasks = set()