"""Reports the time at a predefined interval"""

import asyncio
from modules.module import Module
from popyo import *
from datetime import datetime
from decorators import *
import traceback

# also an example of how I would write a non blocking loop that does something at certain intervals
# todo: refactor to support multiple rooms, likely broken

class TimeReporter(Module):

    CONF_REPORT_INTERVAL_KEY = 'interval'
    CONF_TIME_FORMAT_KEY = 'time_format'

    KEY_EVT_LOOP = "loop"

    # set of connnection names which have active time loops
    repeating_tasks = None

    def unload(self):
        # self.stop_loop()
        for task in list(self.repeating_tasks):
            self.stop_repeating_task(task)

    def onjoin(self, conn_name, scrollback):
        pass

    def onleave(self, conn_name):
        self.stop_repeating_task(conn_name)

    @staticmethod
    def name():
        return "TimeReporter"

    # don't even need this anymore actually
    # def stop_loop(self):
    #     l = self.get_event_loop(TimeReporter.KEY_EVT_LOOP)
    #     l.call_soon_threadsafe(l.stop)
    #     for task in asyncio.Task.all_tasks(loop=l):
    #         task.cancel()

    def stop_repeating_task(self, conn_name):
        if conn_name in self.repeating_tasks: self.repeating_tasks.remove(conn_name)
        for task in asyncio.Task.all_tasks(loop=self.get_event_loop(TimeReporter.KEY_EVT_LOOP)):
            if task.name == conn_name:
                task.cancel()

    async def _broadcast_time_loop(self, conn_name):
        # keep track of the current task for this loop.
        asyncio.Task.current_task().name = conn_name
        while conn_name in self.repeating_tasks:
            self.bot.send(conn=conn_name, msg=datetime.utcnow().strftime(self.conf['time_format']))
            await asyncio.sleep(self.conf.as_float(TimeReporter.CONF_REPORT_INTERVAL_KEY), loop=self.get_event_loop(TimeReporter.KEY_EVT_LOOP))

    # need to start in another thread so that don't exhaust one of the threads of the ThreadPoolExecutor
    def start_loop(self, conn_name):
        if conn_name in self.repeating_tasks:
            self.bot.send(conn=conn_name, msg="A time loop is already running. Call !time report stop first")
        else:
            self.repeating_tasks.add(conn_name)
            asyncio.run_coroutine_threadsafe(self._broadcast_time_loop(conn_name), self.get_event_loop(TimeReporter.KEY_EVT_LOOP))

    @require_dm("Can only be called by an admin in DM.")
    @require_admin("You are not an admin!!")
    def _time_interval(self, wrapper, message):
        split = message.message.split()
        args = len(split) - 2
        if args == 0:
            wrapper.dm(str(self.conf[TimeReporter.CONF_REPORT_INTERVAL_KEY]) + " seconds")
        elif args == 1 and split[-1].isdigit():
            self.conf[TimeReporter.CONF_REPORT_INTERVAL_KEY] = int(split[-1])
            self._config_mgr.write()


    def check_cmd(cmd_string):
        arg_split = cmd_string.split()

        if arg_split[0] == "!time":
            i = len(arg_split)
            if i == 2:
                return Module.CMD_VALID if arg_split[1] in ['report', 'now'] else Module.CMD_PARTIALLY_VALID
            elif i == 3:
                return Module.CMD_VALID if \
                    arg_split[1] == 'report' and arg_split[2] == 'stop' else Module.CMD_PARTIALLY_VALID
            else: return Module.CMD_PARTIALLY_VALID
        return Module.CMD_INVALID

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

        # interval in seconds
        if TimeReporter.CONF_REPORT_INTERVAL_KEY not in self.conf:
            self.conf[TimeReporter.CONF_REPORT_INTERVAL_KEY] = 5
            self.save_config()
        if TimeReporter.CONF_TIME_FORMAT_KEY not in self.conf:
            self.conf[TimeReporter.CONF_TIME_FORMAT_KEY] = '%Y-%m-%d %H:%M:%S'
            self.save_config()

        self.get_new_event_loop(TimeReporter.KEY_EVT_LOOP)

        self.repeating_tasks = set()