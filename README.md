# durararobot
Python 3 modular bot framework for [http://drrr.com](http://drrr.com), still extremely rudimentary.

A diagram of everything so far:

![durararobot block diagram](https://i.imgur.com/yWZhGxI.png)

Get up and running: 

```
pip3 install -r requirements.txt
python3 config_mgr.py
mv sample_config.ini config.ini
```

Edit `config.ini`; change the `username_incl_tripcode` and `avatar` and `gods` fields to your liking.

Run the bot with `python3 main.py`. It should create a `cookies` folder, used to cache cookies so the bot can resume even if it is completely interrupted (e.g. if network disconnects or `Ctrl-C`).

Type `login default`. It should print some debug messages to the channel. `rooms default` should print the list of public rooms in the lounge.

Type `join default [10 char. room ID]`, and the bot should show up in the room; it works with private rooms too. Currently there are only two sample modules in the `modules` folder; `TimeReporter` and `Admin`. Try `!time now`, the bot should print the time out.

[![durararobot dev](https://discordapp.com/api/guilds/92059364239630336/widget.png?style=banner2)](https://discord.gg/aSEB2Fd)