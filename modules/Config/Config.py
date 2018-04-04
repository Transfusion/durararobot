from modules.module import Module
import json

from popyo import *
import traceback
from decorators import *

# Purpose of this module is to list and edit the config_mgr

class Config(Module):
    def argparser(self):
        pass

    @staticmethod
    def name():
        return "Config"

    def unload(self):
        pass

    # handle the scrollback, which should be a list of Messages (Logger plugin)
    def onjoin(self, conn_name, scrollback):
        pass

    # may need to stop tasks or event loops for particular channels!!!
    def onleave(self, conn_name):
        pass

    def check_cmd(cmd_string):
        return Module.CMD_VALID

    @require_admin("You are not an admin!!")
    def _handle_conf(self, wrapper, message):
        args_split = message.message.split()
        if len(args_split) == 1:
            s = "Keys:\n"
            s += ", ".join(self._config_mgr.cfg.keys())
            wrapper.reply(s)

        elif len(args_split) == 2 or len(args_split) == 3:
            dict_split = args_split[1].split(".")

            base_dict = self._config_mgr.cfg
            for key in dict_split:
                if key in base_dict.keys():
                    base_dict = base_dict[key]
                else:
                    wrapper.reply("%s is an invalid key!" % key)
                    return

            if len(args_split) == 2:
                if isinstance(base_dict, dict):
                    s = "Keys:\n"
                    s += ", ".join(base_dict.keys())
                    wrapper.reply(s)
                else:
                    wrapper.reply(str(base_dict))

            # setting a config key e.g. !conf plugin_spec.TimeReporter.time_format /me %Y-%m-%d %H:%M:%S

            if len(args_split) > 2:
                if isinstance(base_dict, dict):
                    pass
                else:
                    base_dict = self._config_mgr.cfg
                    for key in dict_split[:-1]:
                        base_dict = base_dict[key]

                    base_dict[dict_split[-1]] = " ".join( args_split[2:] )
                    self.save_config()
                    wrapper.reply("Written Config.")

    def handler(self, conn_name, message):
       if message.message.startswith("!conf"):
           self._handle_conf(self.bot.get_wrapper(conn_name, message), message)



    def __init__(self, config_mgr, perms_mgr, bot):
        super(Config, self).__init__(config_mgr, perms_mgr, bot)
