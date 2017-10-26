from modules.module import Module
from popyo import *

# TODO: allow drrr admins to do whatever they want
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

    def _process_kick(self, conn_name, message):
        pass

    def _process_give_host(self, conn_name, message):
        # todo: expose a neater interface; e.g. get_conn().is_host()
        if self.bot.conn[conn_name].room.host_id != self.bot.conn[conn_name].own_user.id:
            s = "I'm not the host!"
            if message.type == Message_Type.message:
                self.bot.send(conn_name, s)
            else:
                self.bot.dm(conn_name, message.sender.id, s)
        else:
            if message.sender.tripcode is not None and self.perms_mgr.is_admin(message.sender):
                self.bot.handover_host(conn_name, message.sender.id)
            else:
                s = "You are not an admin!"
                if message.type == Message_Type.message:
                    self.bot.send(conn_name, s)
                else:
                    self.bot.dm(conn_name, message.sender.id, s)

    # admins can make the bot part, enforce rejoin if kicked... kick/ban others..
    def handler(self, conn_name, message):
        if message.type == Message_Type.message or message.type == Message_Type.dm:
            if message.message == "!admin givemehost":
                self._process_give_host(conn_name, message)
            if message.message.startswith("!admin kick"):
                self._process_kick(conn_name, message)


    def __init__(self, config_mgr, perms_mgr, bot):
        super(Admin, self).__init__(config_mgr, perms_mgr, bot)
        if 'rejoin' not in self.conf:
            self.conf['rejoin'] = True
            # channels to avoid rejoining when kicked
            self.conf['avoid_rejoining'] = []
            self.save_config()


