from modules.module import Module
from popyo import *
from decorators import *

# DONE: allow drrr admins to do whatever they want
class Admin(Module):

    def unload(self):
        pass
    def onjoin(self, conn_name, scrollback):
        pass
    def onleave(self, conn_name):
        pass

    def argparser(self):
        pass

    @staticmethod
    def name():
        return "Admin"

    # @require_admin("You are not an admin!!")
    # @require_host("I'm not the host!!")
    # def _process_kick(self, wrapper, message):
    #     self.bot.kick()

    # todo: expose a neater interface; e.g. get_conn().is_host()

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _givemehost(self, wrapper, message):
        self.bot.handover_host(wrapper._conn, message.sender.id)


    # admins can make the bot part, enforce rejoin if kicked... kick/ban others..
    def handler(self, conn_name, message):
        if message.message == "!admin givemehost":
            # self._process_give_host(conn_name, message)
            self._givemehost(self.bot.get_wrapper(conn_name, message), message)
        # if message.message.startswith("!admin kick"):
        #     self._process_kick(conn_name, message)


    def __init__(self, config_mgr, perms_mgr, bot):
        super(Admin, self).__init__(config_mgr, perms_mgr, bot)
        if 'rejoin' not in self.conf:
            self.conf['rejoin'] = True
            # channels to avoid rejoining when kicked
            self.conf['avoid_rejoining'] = []
            self.save_config()


