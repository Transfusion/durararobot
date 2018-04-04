# class to dynamically load/unload modules
# todo: deeper error checking like invalid directory..
# todo: think about making plugins channel-specific.. for instance we may not need trivia plugin in all channels at once

import importlib
import logging
import traceback
from modules import module # must have modules directory and the basic module interface present
import sys

class module_mgr:

    # dict of module name to module object
    modules = None

    # assume that mods_dir is at the same level as this file
    def __init__(self, config_mgr, mods_dir):
        self.logger = logging.getLogger(__name__)

        self.config_mgr = config_mgr
        self.mods_dir = mods_dir
        self.modules = {}

    """returns a boolean depending on whether successfully loaded
    modules need to expose the same class as their name, and the class
     must be a subclass of Module
     startup param is used to prevent calling onjoin"""
    def load_module(self, name, bot, startup=False):
        importlib.invalidate_caches()
        if name in self.modules.keys():
            self.logger.error("module with same name already exists")
            return False
        try:
            mod = importlib.import_module(self.mods_dir + "." + name)
        except ModuleNotFoundError:
            self.logger.error("module " + name + " not found")
            return False

        try:
            cls = getattr(mod, name)
        except AttributeError:
            self.logger.error("module must have a top level class of the same name as itself")
            return False

        if not issubclass(cls, module.Module):
            self.logger.error("module's top level class must inherit from module.Module")
            return False

        self.modules[name] = cls(self.config_mgr, bot.perms_mgr, bot)
        # TODO: Really think about whether we should call onjoin here... also handle the scrollback
        if not startup:
            for conn in bot.conn:
                self.modules[name].onjoin(conn_name=conn, scrollback=None)
        # print(sys.modules)

    def unload_module(self, name):
        try:
            # each module should be responsible for stopping their own threads and cleaning up. This method should block
            # https://stackoverflow.com/questions/437589/how-do-i-unload-reload-a-python-module

            self.modules[name].unload()
            self.modules[name].cancel_all_event_loops()

            del self.modules[name]
            del sys.modules[self.mods_dir + '.' + name]
            del sys.modules[self.mods_dir + '.' + name + '.' + name]
            for mod in list(sys.modules.keys()):
                if mod.startswith(self.mods_dir + '.' + name ):
                    del sys.modules[mod]

        except KeyError:
            self.logger.error("module " + name + " not loaded")
        except Exception:
            self.logger.error(traceback.format_exc())

    # https://github.com/boj/gir/blob/master/gir.py
    # https://stackoverflow.com/questions/2918898/prevent-python-from-caching-the-imported-modules
    def reload_module(self, name, bot):
        if name in self.modules.keys():
            self.unload_module(name)
            self.load_module(name, bot)
            return True
        else:
            return False

    # defeats the purpose of encapsulation, refactor later
    def get_modules(self):
        return self.modules

    def is_loaded(self, module_name):
        return module_name in self.modules

    def gracefully_terminate(self):
        pass

    def reload_cfg(self):
        for _, v in self.modules.items():
            v.load_config()

#     todo: method to send method to specific module, for efficiency...


