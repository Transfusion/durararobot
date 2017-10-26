from asyncio import *
from threading import Thread
import aiohttp
import threading
import functools
import logging
import queue
import traceback
import popyo
import urllib.parse

# WRAP ALL HTTP STUFF WITH TRY - EXCEPT!!!!! OR ELSE IT BECOMES IMPOSSIBLE TO DEBUG!!
class connection:
    # the callback functions
    msg_cb = None

    onjoin_cb = None
    # string representing room id
    # done: need to cache the state of the room as fast updates don't transmit the entire user list at once
    # design decision is that room should be a property of conn.
    room = None

    cookie_jar = None
    http_client_session = None
    event_loop = None
    event_loop_thread = None
    # populate this during room loop start
    room_connected = None
    # populate this with the bot's user details in a User object upon room loop start
    own_user = None
    # logging.Logger instance
    logger = None


    # The word “coroutine”, like the word “generator”, is used for two different (though related) concepts:

    # The function that defines a coroutine (a function definition using async def or decorated with @asyncio.coroutine).
    # If disambiguation is needed we will call this a coroutine function (iscoroutinefunction() returns True).

    # this is a coroutine so must wrap it with a future
    async def _get_login_token(self, endpoint, cb):
        async with self.http_client_session.get(endpoint + "/?api=json") as resp:
            cb(resp.status, await resp.text())


    # public method, cb returns the login token
    def get_login_token(self,  cb):
        run_coroutine_threadsafe(self._get_login_token( self.endpoint, cb), self.event_loop)


    async def _login(self, endpoint, token, cb):
        async with self.http_client_session.post(endpoint + "/?api=json", data={'name' : self.username,
                                      'login' : 'ENTER',
                                      'token' : token,
                                      'language' : 'en-US',
                                      'icon' : self.avatar}) as resp:
            cb(resp.status, await resp.text(), self.http_client_session.cookie_jar)

    # only the token appears to be required for http post login, not even cookies, not sure what the authorization does
    # cb accepts the stat, the response, and the cookiejar instance to do the saving
    def login(self, token, cb):
        run_coroutine_threadsafe(self._login(self.endpoint, token, cb), self.event_loop)

    def start_event_loop(self, loop):
        set_event_loop(loop)
        loop.run_forever()

    # to manually kill the event loop
    def reset(self):
        gather(*Task.all_tasks(self.event_loop)).cancel()
        # for task in Task.all_tasks(self.event_loop):
        #     if hasattr(task, 'name') and task.name == 'cleanup':
        #         pass
        #     else:
        #         task.cancel()
        self.room_connected = False
        self.room = None
        self.own_user = None

    # thread should automatically end once the loop inside it has stopped
    def close(self):
        gather(*Task.all_tasks()).cancel()
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        self.http_client_session.close()

    # todo: do we need to modify any parameters of this
    def __init__(self, id, username, avatar, endpoint, onjoin_cb, onleave_cb, msg_cb, http_retries):
        self.logger = logging.getLogger(__name__ + "." + id)
        self.logger.setLevel(logging.DEBUG)
        logging.getLogger('asyncio').setLevel(logging.DEBUG)

        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logging.getLogger('asyncio').addHandler(ch)

        self.logger.addHandler(ch)

        self.id = id
        self.username = username
        self.avatar = avatar
        self.endpoint = endpoint

        self.room_connected = False
        self.onjoin_cb = onjoin_cb
        self.onleave_cb = onleave_cb
        self.msg_cb = msg_cb
        self.http_retries = http_retries

        self.event_loop = new_event_loop()
        self.event_loop_thread = Thread(target=self.start_event_loop, args=(self.event_loop,))
        self.event_loop_thread.start()

        # The cookie jar implementation is provided by aiohttp, don't confuse it with http.cookiejar
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.http_client_session = aiohttp.ClientSession(loop=self.event_loop, cookie_jar=self.cookie_jar)
        # self.event_loop.run_coroutine(self.get_login_token, self.event_loop, endpoint, lambda x: print(x))

    # not needed, section name is unique in configobj anyways
    # def get_unq_hash(self):
    #     return hashlib.md5(self.username.encode() + self.avatar.encode()).hexdigest()


    async def _get_lounge(self, endpoint, cb):
        async with self.http_client_session.get(endpoint + "/lounge?api=json") as resp:
            cb(resp.status, await resp.text())

    def get_lounge(self, cb):
        run_coroutine_threadsafe(self._get_lounge(self.endpoint, cb), self.event_loop)

    def _get_lounge_blocking(self, event, queue, stat, resp):
        queue.put(stat)
        queue.put(resp)
        event.set()

    def get_lounge_blocking(self):
        event = threading.Event()
        q = queue.Queue()
        cb_with_event = functools.partial(self._get_lounge_blocking, event, q)
        cb = lambda stat, resp: cb_with_event(stat, resp)
        run_coroutine_threadsafe(self._get_lounge(self.endpoint, cb), self.event_loop)
        event.wait()
        return (q.get(), q.get())


    # Note: timeout appears to only be triggered upon someone else joining the room... leaving the room and messages
    # don't trigger it...?
    async def _join_room(self, endpoint, room_id):

        for i in range(0, self.http_retries):
            try:
                # {"redirect":"room","message":"ok","authorization":"a9rc4le6b1m513j09tis2k3801"}
                async with self.http_client_session.get(endpoint + "/room/?id=" + room_id + "&api=json") as resp:
                    stat = resp.status
                    resp_json = await resp.json()
                    if stat == 200 and resp_json["message"] == "ok" and resp_json["redirect"] == "room":
                        # run_coroutine_threadsafe(self._update_room_state(self.endpoint, self._continue_room_loop),
                        #                          self.event_loop)
                        # event = threading.Event()
                        # run_coroutine_threadsafe(self._update_room_state(self.endpoint, event), self.event_loop)
                        # event.wait()
                        await self._update_room_state(self.endpoint, None)
                        if self.room is not None:
                            run_coroutine_threadsafe(self._room_loop(), self.event_loop)
                        else:
                            print("unable to obtain the room state...")
                    else:
                        print("either room doesn't exist or not logged in")
                    return
            except aiohttp.client_exceptions.ContentTypeError:
                self.logger.error(await resp.text())
                raise()
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)


    # only thing to worry about is if the room doesn't exist; {"error":"Room not found.","url":"\/\/drrr.com\/lounge\/?api=json"}
    def join_room(self, room_id):
        run_coroutine_threadsafe(self._join_room(self.endpoint, room_id), self.event_loop)

    async def _leave_room(self, endpoint):
        posted = False
        while not posted:
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                         data={'leave': 'leave'}) as resp:
                    if resp.status == 200:
                        self.logger.debug("leave posted")
                        await resp.text()
                        posted = True
                    else:
                        self.logger.error("leave room failed " + str(resp.status) + await resp.text())
                        # return

            except Exception:
                await sleep(1)
                self.logger.error(traceback.format_exc())


    def leave_room(self):
        if (self.room_connected):
            # gather(*Task.all_tasks(self.event_loop)).cancel()
            run_coroutine_threadsafe(self._leave_room(self.endpoint), self.event_loop)

    # this function should instantiate the self.room variable with the room popyo.
    # perhaps make it varargs so we can make it blocking if we want to???
    # todo: figure out exception catching in the event loop's thread... hard to debug
    # need to check for edge cases such as if we have just been kicked
    async def _update_room_state(self, endpoint, event):
        for i in range(0, self.http_retries):
            try:
                async with self.http_client_session.get(endpoint + "/json.php?fast=1") as resp:
                    # todo: log whether kicked or not...
                    await resp.text()

                async with self.http_client_session.get(endpoint + "/json.php?fast=1") as resp:
                    if resp.status == 200:
                        resp_parsed = await resp.json()

                        users = {}

                        if 'roomId' in resp_parsed:
                            for user in resp_parsed['users']:
                                users[user['id']] = popyo.User(user['id'], user['name'], user['icon'],
                                                               user['tripcode'] if "tripcode" in user.keys() else None,
                                                               True if 'admin' in user.keys() and user['admin'] else False)
                            # (self, name, desc, limit, users, lang, room_id, music, game, host_id):
                            self.room = popyo.Room(resp_parsed['name'], resp_parsed['description'], resp_parsed['limit'], users, resp_parsed['language'],
                                                   resp_parsed['roomId'], resp_parsed['music'], resp_parsed['gameRoom'],
                                                   resp_parsed['host'], resp_parsed['update'])
                    if event is not None:
                        event.set()
                    return
            except Exception:
                self.logger.error(traceback.format_exc())

    def _resume_update_room(self, stat, resp):
        if stat == 200:
            self.logger.debug("saved cookie is valid")
            event = threading.Event()
            # check whether in room, update the room state and begin the room loop if so
            run_coroutine_threadsafe(self._update_room_state(self.endpoint, event), self.event_loop)
            # print(len([task for task in Task.all_tasks(self.event_loop) if not task.done()]))
            # print(Task.current_task())
            event.wait()
            if self.room is not None:
                run_coroutine_threadsafe(self._room_loop(), self.event_loop)
            else:
                print("unable to obtain the room state...")
        elif stat == 401:
            print("invalid cookie, login again: " + str(self.id))
        else:
            print("some error occurred when trying to resume room update")

    def resume(self, cookies_file):
        self.cookie_jar.load(cookies_file)
    #     check whether cookie is still valid
        self._resume_update_room(*self.get_lounge_blocking())



    async def _room_loop(self):
        self.logger.debug("entering the room loop!")
        self.room_connected = True
        # obtain the user ID and call the onJoin callback

        # GETting http://drrr.com/room/?api=json; the 'profile' key gives info about yourself
        async with self.http_client_session.get(self.endpoint + "/room/?api=json") as resp:
            resp_parsed = await resp.json()
            if resp.status == 200 and 'error' not in resp_parsed:
                self.own_user = self.room.users[resp_parsed['profile']['uid']]

        while self.room_connected:
            # todo: do more exhaustive testing and refactor
            try:
                # with async_timeout.timeout(30):
                async with self.http_client_session.get(self.endpoint + "/json.php?update=" + str(self.room.update), timeout=30) as resp:

                    resp_parsed = await resp.json()
                    stat = resp.status

                    self.logger.debug(resp_parsed)
                    if stat == 200 and 'error' not in resp_parsed and 'roomId' in resp_parsed:
                        if 'talks' in resp_parsed:
                            try:
                                msgs = popyo.talks_to_msgs(resp_parsed['talks'], self.room)
                                for msg in msgs:
                                    if msg.type == popyo.Message_Type.join:
                                        self.room.users[msg.sender.id] = msg.sender
                                    elif msg.type == popyo.Message_Type.leave:
                                        if msg.sender.id == self.own_user.id:
                                            # self.room_connected = False
                                            # self.room = None
                                            # self.own_user = None
                                            break
                                        else:
                                    #         update the room state
                                            del self.room.users[msg.sender.id]
                                    if msg.type == popyo.Message_Type.new_host:
                                        self.room.host_id = msg.sender.id
                                    elif msg.type == popyo.Message_Type.async_response:
                                        if msg.stop_fetching:
                                            break
                                    elif msg.type != popyo.Message_Type.kick and \
                                                    msg.type != popyo.Message_Type.async_response and \
                                                    msg.sender.id != self.own_user.id:
                                        await self.msg_cb(self.event_loop, self.id, msg)

                            except Exception as e:
                                self.logger.error("deserializing failed!!!")
                                self.logger.error(traceback.format_exc())
                            self.room.update = resp_parsed['update']

                        else:
                            self.logger.debug("idled successfully")
                    else:
                        self.logger.debug("malformed message!")
                        break

            # encountered once before when admin did something and resp started returning text/html MIME?
            # except aiohttp.client_exceptions.ClientResponseError:
            #     self.logger.debug(traceback.format_exc())
            #     break
            except Exception:
                self.logger.debug(traceback.format_exc())
                sleep(1)
        await self.onleave_cb(self.event_loop, self.id)
        self.reset()

    # todo: retry sending.... sometimes messages don't show up, sometimes connection dropped etc
    # sometimes sending fails with error 500 for no good reason
    # todo: throttle, easy to 403
    # todo: proper backoff algorithm, didn't figure out how to pass the event loop to libraries like riprova

    async def _send(self, endpoint, msg):
        for i in range(0, self.http_retries):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                         data={'message': msg}) as resp:
                    # self.logger.debug("post response " + await resp.text())
                    if resp.status == 200:
                        self.logger.debug("sent " + msg + " successfully")
                    else:
                        self.logger.debug("sending " + msg + "failed with err " + str(resp.status))
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def send(self, msg):
        if self.room_connected:
            run_coroutine_threadsafe(self._send(self.endpoint, msg), self.event_loop)
        else:
            self.logger.warning("Not Connected!")

    async def _dm(self, endpoint, uid, msg):
        for i in range(0, self.http_retries):

            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'message': msg,
                                                                   'to': uid}) as resp:
                    if resp.status == 200:
                        self.logger.debug("sent " + msg + " successfully")
                    else:
                        self.logger.debug("sending " + msg + "failed with err " + str(resp.status))
                    return

            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def dm(self, uid, msg):
        if self.room_connected:
            run_coroutine_threadsafe(self._dm(self.endpoint,uid, msg), self.event_loop)
        else:
            self.logger.warning("Not Connected!")

    async def _handover_host(self, endpoint, uid):
        for i in range(0, self.http_retries):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'new_host': uid}) as resp:
                    if resp.status == 200:
                        self.logger.debug("successfully handed over host to " + self.room.users[uid].name)
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def handover_host(self, uid):
        if self.room_connected:
            run_coroutine_threadsafe(self._handover_host(self.endpoint, uid), self.event_loop)
        else:
            self.logger.warning("Not Connected!")
    # get available rooms
    # def get_rooms(self):