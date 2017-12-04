
# tripcode may be None.
class User:
    def __init__(self, id, name, icon, tripcode, drrr_admin=False):
        self.id = id
        self.name = name
        self.icon = icon
        self.tripcode = tripcode
        self.drrr_admin = drrr_admin

    def __str__(self):
        return "id: %s name: %s icon: %s tc: %s" % (self.id, self.name, self.icon, self.tripcode)

class CLIUser:
    pass