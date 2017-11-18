# modeled upon https://github.com/sopel-irc/sopel/blob/master/sopel/module.py
import functools
import popyo

def require_god(message=None):
    pass


def require_admin(message=None):
    def actual_decorator(function):
        @functools.wraps(function)
        def _nop(*args, **kwargs):
            wrapper, incoming_message = args[1], args[2]
            if wrapper.get_perms_mgr().is_admin(incoming_message.sender):
                return function(*args, **kwargs)
            else:
                wrapper.dm(message)

        return _nop

    if callable(message):
        return actual_decorator(message)

    return actual_decorator

def conditional_dm(message=None):
    def actual_decorator(function):
        @functools.wraps(function)
        def _nop(*args, **kwargs):
            wrapper, incoming_message, dm = args[1], args[2], args[-1]
            if dm and incoming_message.type != popyo.Message_Type.dm:
                wrapper.reply(message)
            else:
                return function(*args, **kwargs)

        return _nop

    if callable(message):
        return actual_decorator(message)

    return actual_decorator

# argument to this decorator is the error message which will be output to the chan
def require_dm(message=None):
    def actual_decorator(function):
        @functools.wraps(function)
        def _nop(*args, **kwargs):
            # message is the actual message
            wrapper, incoming_message = args[1], args[2]
            if incoming_message.type != popyo.Message_Type.dm:
                wrapper.reply(message)
            else:
                return function(*args, **kwargs)
        return _nop


    if callable(message):
        return actual_decorator(message)

    return actual_decorator

# def require_host_in_dj_room(message=None)

# own bot must be host in order to run this command
def require_host(message=None):
    def actual_decorator(function):
        @functools.wraps(function)
        def _nop(*args, **kwargs):
            # message is the actual message
            wrapper, incoming_message = args[1], args[2]
            if not wrapper.am_host():
                wrapper.reply(message)
            else:
                return function(*args, **kwargs)
        return _nop


    if callable(message):
        return actual_decorator(message)

    return actual_decorator


def require_tc(message=None):
    pass


def require_chan(message=None):
    pass