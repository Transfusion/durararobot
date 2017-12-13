
# tripcode may be None.
CLI_USER_ID = 1001
DISC_ADMIN_USER_ID = 1002
DISC_NORMAL_USER_ID = 1003

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

class CLIUser:
    def __init__(self):
        self.id = CLI_USER_ID

class DiscordAdminUser:
    def __init__(self):
        self.id = DISC_ADMIN_USER_ID

class DiscordNormalUser:
    def __init__(self):
        self.id = DISC_NORMAL_USER_ID