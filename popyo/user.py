
# tripcode may be None.
CLI_USER_ID = 1001
DISC_USER_ID = 1002

class User:
    def __init__(self, id, name, icon, tripcode, device, drrr_admin=False):
        self.id = id
        self.name = name
        self.icon = icon
        self.tripcode = tripcode
        self.device = device
        self.drrr_admin = drrr_admin

    def __str__(self):
        return "id: %s name: %s icon: %s tc: %s" % (self.id, self.name, self.icon, self.tripcode)

class BannedUserInfo(User):
    def __init__(self, id, name, tripcode, icon):
        super(BannedUserInfo, self).__init__(id, name, icon, tripcode, None, False)

class CLIUser:
    def __init__(self):
        self.id = CLI_USER_ID

class DiscordUser:
    def __init__(self, discord_user_obj, bot_admin=False, bot_god=False):
        self.id = DISC_USER_ID
        self.discord_user_obj = discord_user_obj
        self.bot_admin = bot_admin
        self.bot_god = bot_god


# class DiscordAdminUser(DiscordUser):
#     def __init__(self):
#         self.id = DISC_ADMIN_USER_ID
#
# class DiscordNormalUser(DiscordUser):
#     def __init__(self):
#         self.id = DISC_NORMAL_USER_ID