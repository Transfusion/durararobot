import bot
import config_mgr

if __name__ == "__main__":
    b = bot.bot(config_mgr.config_mgr())
    bot_cli = bot.BotCLI(b)
    bot_cli.prompt  = "> "
    # bot_cli.cmdloop();
    bot_cli.cmdloop_with_keyboard_interrupt()