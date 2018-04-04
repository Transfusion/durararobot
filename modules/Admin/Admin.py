from modules.module import Module
from decorators import *
import functools
import time
import traceback

# DONE: allow drrr admins to do whatever they want

# !die for drrr_admins and gods to leave and hardkill the bot
# !givemehost for admins and gods
# !admin add username tripcode for admins and gods
# !admin remove username tripcode for admins (will not work on gods ofc)
# !givehost username
# !listadmins
# !leave
# !fjoin [roomid] (leaves and joins another room)
# !ban username
# !kick username
# !reportban username
# !unban username
# !asay [text]
# !toggledj
# !roomname [text]
# !roomdesc [text]


class Admin(Module):

    def unload(self):
        pass
    def onjoin(self, conn_name, scrollback):
        pass

    def onleave(self, conn_name):
        for i in self.onleave_single_callback_set:
            i()
        self.onleave_single_callback_set.clear()

    @staticmethod
    def name():
        return "Admin"

    # @require_admin("You are not an admin!!")
    # @require_host("I'm not the host!!")
    # def _process_kick(self, wrapper, message):
    #     self.bot.kick()

    # todo: expose a neater interface; e.g. get_conn().is_host()

    @not_cli("How am I supposed to give you the host? :P")
    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _givemehost(self, wrapper, message):
        self.bot.handover_host(wrapper._conn, message.sender.id)

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _givehost(self, wrapper, message):
        gave = False
        s = message.message.split()[-1]
        for key, user in wrapper.get_conn().room.users.items():
            if user.name == s:
                self.bot.handover_host(wrapper._conn, key)
                gave = True
                break
        if not gave:
            wrapper.reply("No one with that name is in the room.")

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_kick(self, wrapper, message):
        kicked = False
        s = message.message.split()[-1]
        for key, user in wrapper.get_conn().room.users.items():
            if user.name == s:
                self.bot.kick(wrapper._conn, key)
                kicked = True
                break
        if not kicked:
            wrapper.reply("No one with that name is in the room.")

    # certain functions will be called twice because sometimes the json.php polling returns duplicate messages:
    # https://pastebin.com/0TrgyX2n
    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_ban(self, wrapper, message):
        banned = False
        s = message.message.split()[-1]
        for key, user in wrapper.get_conn().room.users.items():
            if user.name == s:
                self.bot.ban(wrapper._conn, key)
                banned = True
                break

        # if not banned:
        #     wrapper.reply("No one with that name is in the room.")

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_report_and_ban(self, wrapper, message):
        banned = False
        s = message.message.split()[-1]
        for key, user in wrapper.get_conn().room.users.items():
            if user.name == s:
                self.bot.report_and_ban(wrapper._conn, key)
                banned = True
                break
        if not banned:
            wrapper.reply("No one with that name is in the room.")

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_unban(self, wrapper, message):
        id = message.message.split()[-1]
        if id in wrapper.get_conn().room.banned_ids:
            self.bot.unban(wrapper._conn, id)
        else:
            wrapper.reply("Do !listbans to see a list of banned uids")

    @require_admin("You are not an admin!!")
    def _process_leave(self, wrapper, message):
        self.bot.leave(wrapper._conn)

    @require_admin("You are not an admin!!")
    def _process_reloadcfg(self, wrapper, message):
        self.bot.reload_cfg()
        wrapper.reply("Reloaded config.")

    @require_admin("You are not an admin!!")
    def _process_asay(self, wrapper, message):
        self.bot.send(wrapper._conn, message.message[6: ])

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_toggledj(self, wrapper, message):
        self.bot.set_dj_mode(wrapper._conn, not wrapper.get_conn().room.dj_mode)

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_roomname(self, wrapper, message):
        self.bot.set_room_name(wrapper._conn, message.message[10:])

    @require_admin("You are not an admin!!")
    @require_host("I'm not the host!!")
    def _process_roomdesc(self, wrapper, message):
        self.bot.set_room_desc(wrapper._conn, message.message[10:])


    @require_admin("You are not an admin!")
    def _process_admin_add(self, wrapper, message):
        (username, tripcode) = message.message[11:].split()
        self.bot.perms_mgr.allow_admin(username, tripcode)
        wrapper.reply("Added " + username + "#" + tripcode + " into the admins list.")

    @require_dm(";) Admins are everywhere")
    @require_admin("You are not an admin!")
    def _process_listadmins(self, wrapper, message):
        blk = wrapper.get_perms_mgr().get_admin_block()
        if blk == []:
            wrapper.reply("No admins added.")
        else:
            s = "\n".join([n + "#" + tc for (n, tc) in blk])
            wrapper.reply(s)

    @require_dm(";) Gods are everywhere")
    @require_god("You are not an god!")
    def _process_listgods(self, wrapper, message):
        blk = wrapper.get_perms_mgr().get_gods_block()
        if blk == []:
            wrapper.reply("No gods added.")
        else:
            s = "\n".join([n + "#" + tc for (n, tc) in blk])
            wrapper.reply(s)

    @require_admin("You are not an admin!!")
    def _process_fjoin(self, wrapper, message):
        # first, check if the room ID actually exists. (Only works with public rooms for now!)
        r = self.bot.get_rooms(wrapper._conn)
        rooms = {}

        for x in r:
            rooms[x['id']] = x

        desired_room = message.message.split()[1]

        if desired_room not in rooms.keys():
            wrapper.reply("This room ID isn't in the list of public rooms")
        elif rooms[desired_room]['limit'] == len(rooms[desired_room]['users']):
            wrapper.reply("This room is full!!")
        else:
            self.bot.leave(wrapper._conn)
            # need to wait until the room status has really been updated, so can't just call join

            self.onleave_single_callback_set.add(functools.partial(self._wait_onleave, wrapper._conn, desired_room))

    def _process_listusers(self, wrapper, message):
        s = ""
        room = wrapper.get_conn().room
        for key, user in room.users.items():
            s += "%s#%s %s" % (user.name, user.tripcode if user.tripcode is not None else "", user.device)
            s += '\n'

        wrapper.reply(s)

    def _process_banned(self, wrapper, message):
        room = wrapper.get_conn().room
        if room.banned_ids == set():
            wrapper.reply("No banned users.")

        else:
            s = ""
            for id in room.banned_ids:
                s += "%s" % (id)
                s += '\n'
            wrapper.reply(s)


    def _wait_onleave(self, conn, desired_room):
        time.sleep(1)
        self.bot.join(conn, desired_room)

    @staticmethod
    def check_cmd(cmd_string):
        # arg_split = cmd_string.split()
        # if arg_split[0] not in ['!die', '!givemehost', '!givehost', '!admin', '!leave',
        #                         '!join', '!ban', '!reportban', '!unban', '!asay', '!toggledj', '!roomname', '!roomdesc']:
        #     return Module.CMD_INVALID
        #
        # if arg_split[0] == "!admin ":
        #     i = len(arg_split)
        #     if i == 2:
        #         return Module.CMD_VALID if arg_split[1] in ['givemehost'] else Module.CMD_PARTIALLY_VALID
        #
        # return Module.CMD_INVALID
        return Module.CMD_VALID


    # admins can make the bot part, enforce rejoin if kicked... kick/ban others..
    def handler(self, conn_name, message):
        if message.message == "!admin givemehost":
            self._givemehost(self.bot.get_wrapper(conn_name, message), message)
        elif message.message.startswith("!givehost "):
            self._givehost(self.bot.get_wrapper(conn_name, message), message)

        elif message.message.startswith("!kick "):
            self._process_kick(self.bot.get_wrapper(conn_name, message), message)
        elif message.message.startswith("!ban "):
            self._process_ban(self.bot.get_wrapper(conn_name, message), message)
        elif message.message.startswith("!reportban "):
            self._process_report_and_ban(self.bot.get_wrapper(conn_name, message), message)

        elif message.message.startswith("!unban"):
            self._process_unban(self.bot.get_wrapper(conn_name, message), message)

        elif message.message == "!leave":
            self._process_leave(self.bot.get_wrapper(conn_name, message), message)
        elif message.message == "!reloadcfg":
            self._process_reloadcfg(self.bot.get_wrapper(conn_name, message), message)

        elif message.message == "!toggledj":
            self._process_toggledj(self.bot.get_wrapper(conn_name, message), message)

        elif message.message == "!listadmins":
            self._process_listadmins(self.bot.get_wrapper(conn_name, message), message)

        elif message.message == "!listgods":
            self._process_listgods(self.bot.get_wrapper(conn_name, message), message)


        elif message.message == "!listusers":
            self._process_listusers(self.bot.get_wrapper(conn_name, message), message)

        elif message.message == "!listbanned":
            self._process_banned(self.bot.get_wrapper(conn_name, message), message)

        elif message.message.startswith("!asay "):
            self._process_asay(self.bot.get_wrapper(conn_name, message), message)
        elif message.message.startswith("!roomname "):
            self._process_roomname(self.bot.get_wrapper(conn_name, message), message)

        elif message.message.startswith("!roomdesc "):
            self._process_roomdesc(self.bot.get_wrapper(conn_name, message), message)

        elif message.message.startswith("!admin add "):
            self._process_kick(self.bot.get_wrapper(conn_name, message), message)

        elif message.message.startswith("!fjoin "):
            self._process_fjoin(self.bot.get_wrapper(conn_name, message), message)


    def __init__(self, config_mgr, perms_mgr, bot):
        super(Admin, self).__init__(config_mgr, perms_mgr, bot)
        if 'rejoin' not in self.conf:
            self.conf['rejoin'] = True
            # channels to avoid rejoining when kicked
            self.conf['avoid_rejoining'] = []
            self.save_config()

        self.onleave_single_callback_set = set()

