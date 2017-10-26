import configobj, validate

# should put all the writes in this class so that easier to keep track
class config_mgr:

    CONFIG_FILE_LOCATION = "config.ini"

    # create a new plugin config block
    # def add_plugin_spec(self, name):
    #     pass

    def write(self):
        self.cfg.write()

    """Creates the section if doesn't exist else returns the existing config"""
    def get_plugin_spec(self, name):
        if name not in self.cfg['plugin_spec'].keys():
            self.cfg['plugin_spec'][name] = {}
        return self.cfg['plugin_spec'][name]

    def cookies_dir(self):
        return self.cfg['cookies_dir']
    def drrr_domain(self):
        return self.cfg['drrr_domain']
    def use_https(self):
        return self.cfg.as_bool('use_https')
    def get_conns(self):
        return self.cfg['connections']
    def get_http_retries(self):
        return self.cfg['http_failure_retries']

    def get_perms_block(self):
        return self.cfg['permissions']

    def __init__(self):
        self.cfg = configobj.ConfigObj(config_mgr.CONFIG_FILE_LOCATION, unrepr=True)

    def reload_from_file(self):
        self.cfg.reload()

    @classmethod
    def sample_cfg_file(cls):
        cfg = configobj.ConfigObj("sample_" + config_mgr.CONFIG_FILE_LOCATION, unrepr=True)
        # cfg = configobj.ConfigObj("" + config_mgr.CONFIG_FILE_LOCATION, unrepr=True)
        cfg['use_https'] = False
        cfg['drrr_domain'] = 'drrr.com'
        cfg['http_failure_retries'] = 5
        cfg['connections'] = {}
        cfg['connections']['default'] = {}
        cfg['connections']['default']["username_incl_tripcode"] = "sample#tr1pc0de"
        cfg['connections']['default']["avatar"] = "kanra"
        cfg['cookies_dir'] = 'cookies'
        cfg['plugin_spec'] = {}
        cfg['permissions'] = {}

        # make sure to get your tripcode right
        # gods are people who have physical access to the bot
        cfg['permissions']['gods'] = [('sample', 'pnNad3aArk')]
        # admins are people who can grant/remove other permissions from others except gods
        cfg['permissions']['admins'] = []

        cfg.write()

if __name__ == '__main__':
    config_mgr.sample_cfg_file()
    c = config_mgr()