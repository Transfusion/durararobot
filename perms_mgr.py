"""Simple permissions system per plugin based on tripcodes; each plugin should have access to this class
Consider making it more fine-grained in the future (e.g. user/pass system)"""

# obviously not secure because it stores everything in plaintext in the config.ini file
# also a bit redundant since we already have access to config_mgr... but might want to store auth separately in future
# https://pypkg.com/pypi/limnoria/f/plugins/User/plugin.py

import logging
import popyo

class perms_mgr():
    def __init__(self, config_mgr):
        self.logger = logging.getLogger(__name__)

        self.config_mgr = config_mgr
        self.load_perms_block()

    def load_perms_block(self):
        self.perms_block = self.config_mgr.get_perms_block()

    def get_perms_block(self, plugin_name):
        if plugin_name not in self.perms_block.keys():
            self.perms_block[plugin_name] = {}
            self.config_mgr.write()

        return self.perms_block[plugin_name]

    def allow(self, plugin_name, cmd_name, username, tripcode):
        if cmd_name not in self.perms_block[plugin_name]:
            self.perms_block[plugin_name][cmd_name] = []

        self.perms_block[plugin_name][cmd_name].append((username, tripcode))
        self.config_mgr.write()

    def allow_admin(self, username, tripcode):
        self.perms_block['admins'].append((username, tripcode))
        self.config_mgr.write()

    # user is a user object
    def is_admin(self, user):
        if isinstance(user, popyo.DiscordUser):
            return user.bot_admin or self.is_god(user)

        return self.is_god(user) or (user.name, user.tripcode) in self.perms_block['admins']

    def is_god(self, user):
        if isinstance(user, popyo.DiscordUser):
            return user.bot_god

        return isinstance(user, popyo.CLIUser) or (user.name, user.tripcode) in self.perms_block['gods'] or user.drrr_admin

    def is_allowed(self, plugin_name, cmd_name, username, tripcode):
        return (username, tripcode) in self.perms_block[plugin_name][cmd_name]

    """remember that admin block is a list of tuples"""
    def get_admin_block(self):
        return self.perms_block['admins']

    def get_gods_block(self):
        return self.perms_block['gods']

    # do not use lightly!!
    def remove_admin(self, username, tripcode):
        pass

    def remove_allowed(self, plugin_name, cmd_name, username, tripcode):
        if (username, tripcode) in self.perms_block[plugin_name][cmd_name]:
            self.perms_block[plugin_name][cmd_name].remove((username, tripcode))
            return True
        else:
            self.logger.error(str((username, tripcode)) + " is not in " + plugin_name + "."
                              + cmd_name + "'s allowed list")
            return False