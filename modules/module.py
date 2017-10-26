# "abstract class" for what methods a module should implement
# each module should have its own configurable storage.
# todo: Admin module so that can manage the bot from within drrr

from abc import ABCMeta, abstractmethod, abstractproperty

# TODO: rewrite admin check, throttling, and other features using decorators
# http://scottlobdell.me/2015/04/decorators-arguments-python/
class Module(metaclass=ABCMeta):

    @abstractproperty
    def argparser(self):
        pass

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

    @abstractmethod
    def handler(self, conn_name, message):
        pass

    def save_config(self):
        self._config_mgr.write()

    # need bot to send, rather messy because of circular referencing..
    # remember to call perms_mgr.allow before is_allowed..
    def __init__(self, config_mgr, perms_mgr, bot):
        self._config_mgr = config_mgr
        self.conf = config_mgr.get_plugin_spec(self.__class__.name())
        self.perms_mgr = perms_mgr
        self.bot = bot
