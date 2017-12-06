from asyncio import *
from threading import Thread
import aiohttp
import logging
import traceback
import popyo
import time

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
    async def _get_login_token(self, endpoint):
        async with self.http_client_session.get(endpoint + "/?api=json") as resp:
            # cb(resp.status, await resp.text())
            return (resp.status, await resp.text())

    # public method, returns the login token if 200, None otherwise
    def get_login_token(self):
        future = run_coroutine_threadsafe(self._get_login_token(self._get_endpoint()), self.event_loop)
        return future.result()


    async def _login(self, endpoint, token):
        async with self.http_client_session.post(endpoint + "/?api=json", data={'name' : self.username,
                                      'login' : 'ENTER',
                                      'token' : token,
                                      'language' : 'en-US',
                                      'icon' : self.avatar}) as resp:
            # cb(resp.status, await resp.text(), self.http_client_session.cookie_jar)
            return (resp.status, await resp.text(), self.http_client_session.cookie_jar)

    # only the token appears to be required for http post login, not even cookies, not sure what the authorization does
    # cb accepts the stat, the response, and the cookiejar instance to do the saving
    def login(self, token):
        future = run_coroutine_threadsafe(self._login(self._get_endpoint(), token), self.event_loop)
        return future.result()

    def start_event_loop(self, loop):
        set_event_loop(loop)
        loop.run_forever()

    # to manually kill the event loop, should terminate the await in the send loop too
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
        self.sendQ._queue.clear()

    # thread should automatically end once the loop inside it has stopped
    def close(self):
        gather(*Task.all_tasks()).cancel()
        self.event_loop.call_soon_threadsafe(self.event_loop.stop)
        self.http_client_session.close()

    def _get_endpoint(self):
        return ("https://" if self.networking_config['use_https'] else "http://") + self.networking_config['drrr_domain']

    # todo: do we need to modify any parameters of this, networking_config should be a section of the config mgr
    def __init__(self, id, username, avatar, onjoin_cb, onleave_cb, msg_cb, networking_config):
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
        self.networking_config = networking_config

        self.room_connected = False
        self.onjoin_cb = onjoin_cb
        self.onleave_cb = onleave_cb
        self.msg_cb = msg_cb

        self.event_loop = new_event_loop()
        self.event_loop_thread = Thread(target=self.start_event_loop, args=(self.event_loop,))
        self.event_loop_thread.start()

        # The cookie jar implementation is provided by aiohttp, don't confuse it with http.cookiejar
        self.cookie_jar = aiohttp.CookieJar(unsafe=True)
        self.http_client_session = aiohttp.ClientSession(loop=self.event_loop, cookie_jar=self.cookie_jar, headers={'User-Agent': 'Bot'})

        self.sendQ = Queue(loop=self.event_loop)
        # self.event_loop.run_coroutine(self.get_login_token, self.event_loop, endpoint, lambda x: print(x))

    # not needed, section name is unique in configobj anyways
    # def get_unq_hash(self):
    #     return hashlib.md5(self.username.encode() + self.avatar.encode()).hexdigest()


    async def _get_lounge(self, endpoint, cb):
        async with self.http_client_session.get(endpoint + "/lounge?api=json") as resp:
            stat = resp.status
            text = await resp.text()
            cb(stat, text)
            return(stat, text)

    def get_lounge(self, cb):
        run_coroutine_threadsafe(self._get_lounge(self._get_endpoint(), cb), self.event_loop)

    def get_lounge_blocking(self):
        future = run_coroutine_threadsafe(self._get_lounge(self._get_endpoint(),
                                                           lambda *args: None), self.event_loop)
        return future.result()

    # def _get_lounge_blocking(self, event, queue, stat, resp):
    #     queue.put(stat)
    #     queue.put(resp)
    #     event.set()
    #
    # def get_lounge_blocking(self):
    #     event = threading.Event()
    #     q = queue.Queue()
    #     cb_with_event = functools.partial(self._get_lounge_blocking, event, q)
    #     cb = lambda stat, resp: cb_with_event(stat, resp)
    #     run_coroutine_threadsafe(self._get_lounge(self._get_endpoint(), cb), self.event_loop)
    #     event.wait()
    #     return (q.get(), q.get())


    # Note: timeout appears to only be triggered upon someone else joining the room... leaving the room and messages
    # don't trigger it...?
    async def _join_room(self, endpoint, room_id):

        for i in range(0, self.networking_config['http_failure_retries']):
            try:
                # {"redirect":"room","message":"ok","authorization":"a9rc4le6b1m513j09tis2k3801"}
                async with self.http_client_session.get(endpoint + "/room/?id=" + room_id + "&api=json") as resp:
                    stat = resp.status
                    resp_json = await resp.json()
                    if stat == 200 and resp_json["message"] == "ok" and resp_json["redirect"] == "room":
                        # run_coroutine_threadsafe(self._update_room_state(self._get_endpoint(), self._continue_room_loop),
                        #                          self.event_loop)
                        # event = threading.Event()
                        # run_coroutine_threadsafe(self._update_room_state(self._get_endpoint(), event), self.event_loop)
                        # event.wait()
                        await self._update_room_state(self._get_endpoint())
                        if self.room is not None:
                            self.room_connected = True
                            run_coroutine_threadsafe(self._room_loop(), self.event_loop)
                            run_coroutine_threadsafe(self._send_loop(), self.event_loop)
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
        run_coroutine_threadsafe(self._join_room(self._get_endpoint(), room_id), self.event_loop)

    # music, conceal, adult, game are booleans
    def create_and_join_room(self, name, desc, limit, lang, music, conceal, adult, game):
        pass

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
            run_coroutine_threadsafe(self._leave_room(self._get_endpoint()), self.event_loop)

    # this function should instantiate the self.room variable with the room popyo.
    # perhaps make it varargs so we can make it blocking if we want to???
    # todo: figure out exception catching in the event loop's thread... hard to debug
    # need to check for edge cases such as if we have just been kicked
    async def _update_room_state(self, endpoint, preserve_banned=False):
        for i in range(0, self.networking_config['http_failure_retries']):
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

                            banned_users = self.room.banned_users if preserve_banned else {}
                            # (self, name, desc, limit, users, lang, room_id, music, game, host_id):
                            self.room = popyo.Room(resp_parsed['name'], resp_parsed['description'], resp_parsed['limit'], users, resp_parsed['language'],
                                                   resp_parsed['roomId'], resp_parsed['music'], resp_parsed['djMode'], resp_parsed['gameRoom'],
                                                   resp_parsed['host'], resp_parsed['update'])
                            self.room.banned_users = banned_users


                    return
            except Exception:
                self.logger.error(traceback.format_exc())

    def resume(self, cookies_file):
        self.cookie_jar.load(cookies_file)
    #     check whether cookie is still valid
        stat, resp = self.get_lounge_blocking()
        if stat == 200:
            self.logger.debug("saved cookie is valid")
            # check whether in room, update the room state and begin the room loop if so
            future = run_coroutine_threadsafe(self._update_room_state(self._get_endpoint()), self.event_loop)
            future.result()
            # print(len([task for task in Task.all_tasks(self.event_loop) if not task.done()]))
            # print(Task.current_task())
            if self.room is not None:
                self.room_connected = True
                run_coroutine_threadsafe(self._room_loop(), self.event_loop)
                run_coroutine_threadsafe(self._send_loop(), self.event_loop)
            else:
                print("unable to obtain the room state...")
        elif stat == 401:
            print("invalid cookie, login again: " + str(self.id))
        else:
            print("some error occurred when trying to resume room update")



    async def _room_loop(self):
        self.logger.debug("entering the room loop!")

        self.last_error = False
        self.exit_loop = False

        print(self.room_connected)
        # obtain the user ID and call the onJoin callback

        # GETting http://drrr.com/room/?api=json; the 'profile' key gives info about yourself
        async with self.http_client_session.get(self._get_endpoint() + "/room/?api=json") as resp:
            try:
                resp_parsed = await resp.json()
                if resp.status == 200 and 'error' not in resp_parsed:
                    self.own_user = self.room.users[resp_parsed['profile']['uid']]
                    # TODO: Fix this..
                # await self.onjoin_cb(self.event_loop, self.id, popyo.talks_to_msgs(resp_parsed['room']['talks'], self.room))
                await self.onjoin_cb(self.event_loop, self.id,
                                     None)

            except Exception:
                self.logger.debug(traceback.format_exc())

        while self.room_connected:
            # todo: do more exhaustive testing and refactor
            try:
                # with async_timeout.timeout(30):
                async with self.http_client_session.get(self._get_endpoint() + "/json.php?update=" + str(self.room.update), timeout=30) as resp:

                    resp_parsed = await resp.json()
                    stat = resp.status

                    self.logger.debug(resp_parsed)
                    # if stat == 200 and 'error' not in resp_parsed and 'roomId' in resp_parsed:
                    if stat == 200:
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
                                            self.exit_loop = True
                                            break
                                        else:
                                    #         update the room state
                                            del self.room.users[msg.sender.id]
                                    if msg.type == popyo.Message_Type.new_host:
                                        self.room.host_id = msg.sender.id

                                    elif msg.type == popyo.Message_Type.async_response:
                                        if msg.stop_fetching:
                                            self.exit_loop = True
                                            break

                                    elif msg.type == popyo.Message_Type.kick:
                                        if msg.to.id != self.own_user.id:
                                            del self.room.users[msg.to.id]
                                            await self.msg_cb(self.event_loop, self.id, msg)

                                    elif msg.type == popyo.Message_Type.ban:
                                        if msg.to.id != self.own_user.id:
                                            # update the ban list in case we need to unban in the future
                                            self.room.banned_users[msg.to.id] = self.room.users[msg.to.id]
                                            del self.room.users[msg.to.id]
                                            await self.msg_cb(self.event_loop, self.id, msg)

                                    elif msg.type == popyo.Message_Type.unban:
                                        del self.room.banned_users[msg.to.id]
                                        await self.msg_cb(self.event_loop, self.id, msg)

                                    elif msg.type == popyo.Message_Type.system:
                                        await self._update_room_state(self._get_endpoint(), preserve_banned=True)

                                    elif msg.type == popyo.Message_Type.error:
                                        # might be the spurious bug , fetch again and check if it isn't error
                                        if msg.reload and not self.last_error:
                                            self.last_error = True
                                            pass

                                        else:
                                            self.exit_loop = True
                                            break

                                    elif msg.type != popyo.Message_Type.kick and \
                                                    msg.type != popyo.Message_Type.async_response and \
                                                    msg.sender.id != self.own_user.id:
                                        await self.msg_cb(self.event_loop, self.id, msg)

                                    self.last_error = False

                                if self.exit_loop:
                                    break

                            except Exception as e:
                                self.logger.error("deserializing failed!!!")
                                self.logger.error(traceback.format_exc())

                        else:
                            self.logger.debug("idled successfully")
                        self.room.update = resp_parsed['update']
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

    async def _send_loop(self):
        t = time.time()
        while self.room_connected:
            try:
                outgoing_msg = await self.sendQ.get()
                t1 = time.time()

                if (t1 - t) < self.networking_config.as_float('throttle'):
                    await sleep(self.networking_config.as_float('throttle'))

                if self.room_connected:
                    if outgoing_msg.type == popyo.Outgoing_Message_Type.message:
                        await self._send(self._get_endpoint(), outgoing_msg.msg)
                    elif outgoing_msg.type == popyo.Outgoing_Message_Type.dm:
                        await self._dm(self._get_endpoint(), outgoing_msg.receiver, outgoing_msg.msg)
                    elif outgoing_msg.type == popyo.Outgoing_Message_Type.url:
                        await self._send_url(self._get_endpoint(), outgoing_msg.msg, outgoing_msg.url)

                    t = time.time()
            except Exception:
                self.logger.debug(traceback.format_exc())


    async def _send(self, endpoint, msg):
        for i in range(0, self.networking_config['http_failure_retries']):
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

    async def _add_sendQ_outgoing(self, items):
        for i in items:
            await self.sendQ.put(i)

    def send(self, msg):
        if self.room_connected:
        #     run_coroutine_threadsafe(self._send(self._get_endpoint(), msg), self.event_loop)
        # else:
        #     self.logger.warning("Not Connected!")
            chunked = [msg[i:i + self.networking_config.as_int('char_limit')]
                       for i in range(0, len(msg), self.networking_config.as_int('char_limit'))]
            msgs = [popyo.OutgoingMessage(chunk) for chunk in chunked]
            run_coroutine_threadsafe(self._add_sendQ_outgoing(msgs), self.event_loop)

    async def _send_url(self, endpoint, msg, url):
        for i in range(0, self.networking_config['http_failure_retries']):

            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'message': msg,
                                                                   'url': url}) as resp:
                    if resp.status == 200:
                        self.logger.debug("sent " + msg + " successfully" + " with url " + url)
                    else:
                        self.logger.debug("sending " + msg + "failed with err " + str(resp.status))
                    return

            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def send_url(self, msg, url):
        chunked = [msg[i:i + self.networking_config.as_int('char_limit')]
                   for i in range(0, len(msg), self.networking_config.as_int('char_limit'))]

        msgs = [popyo.OutgoingMessage(chunk) for chunk in chunked[:-1] ]
        msgs.append(popyo.OutgoingUrlMessage(chunked[-1], url))

        run_coroutine_threadsafe(self._add_sendQ_outgoing(msgs), self.event_loop)

    async def _dm(self, endpoint, uid, msg):
        for i in range(0, self.networking_config['http_failure_retries']):

            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'message': msg,
                                                                   'to': uid}) as resp:
                    if resp.status == 200:
                        self.logger.debug("sent " + msg + " successfully" + " to " +uid)
                    else:
                        self.logger.debug("sending " + msg + "failed with err " + str(resp.status))
                    return

            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def dm(self, uid, msg):
        chunked = [msg[i:i + self.networking_config.as_int('char_limit')]
                   for i in range(0, len(msg), self.networking_config.as_int('char_limit'))]
        msgs = [popyo.OutgoingDirectMessage(chunk, uid) for chunk in chunked]
        run_coroutine_threadsafe(self._add_sendQ_outgoing(msgs), self.event_loop)

    async def _handover_host(self, endpoint, uid):
        for i in range(0, self.networking_config['http_failure_retries']):
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
            run_coroutine_threadsafe(self._handover_host(self._get_endpoint(), uid), self.event_loop)
        else:
            self.logger.warning("Not Connected!")

    async def _kick(self, endpoint, uid):
        for i in range(0, self.networking_config['http_failure_retries']):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'kick': uid}) as resp:
                    if resp.status == 200:
                        self.logger.debug("successfully kicked " + self.room.users[uid].name)
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def kick(self, uid):
        if self.room_connected:
            run_coroutine_threadsafe(self._kick(self._get_endpoint(), uid), self.event_loop)
        else:
            self.logger.warning("Not Connected!")

    async def _ban(self, endpoint, uid):
        for i in range(0, self.networking_config['http_failure_retries']):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'ban': uid}) as resp:
                    if resp.status == 200:
                        self.logger.debug("successfully banned " + self.room.users[uid].name)
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def ban(self, uid):
        if self.room_connected:
            run_coroutine_threadsafe(self._ban(self._get_endpoint(), uid), self.event_loop)
        else:
            self.logger.warning("Not Connected!")

    async def _report_and_ban(self, endpoint, uid):
        for i in range(0, self.networking_config['http_failure_retries']):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'report_and_ban_user': uid}) as resp:
                    if resp.status == 200:
                        self.logger.debug("successfully reported and banned " + self.room.users[uid].name)
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def report_and_ban(self, uid):
        if self.room_connected:
            run_coroutine_threadsafe(self._report_and_ban(self._get_endpoint(), uid), self.event_loop)
        else:
            self.logger.warning("Not Connected!")


    async def _play_music(self, endpoint, name, url):
        for i in range(0, self.networking_config['http_failure_retries']):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'music': 'music',
                                                                   'name': name,
                                                                   'url': url}) as resp:
                    if resp.status == 200:
                        pass
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def play_music(self, name, url):
        if self.room_connected:
            run_coroutine_threadsafe(self._play_music(self._get_endpoint(), name, url), self.event_loop)
        else:
            self.logger.warning("Not Connected!")


    async def _set_dj_mode(self, endpoint, is_dj_mode):
        for i in range(0, self.networking_config['http_failure_retries']):
            try:
                async with self.http_client_session.post(endpoint + "/room/?ajax=1&api=json",
                                                             data={'dj_mode': str(is_dj_mode).lower()}) as resp:
                    if resp.status == 200:
                        pass
                    return
            except Exception as e:
                self.logger.error(traceback.format_exc())
                sleep(1)

    def set_dj_mode(self, is_dj_mode):
        if self.room_connected:
            run_coroutine_threadsafe(self._set_dj_mode(self._get_endpoint(), is_dj_mode), self.event_loop)
        else:
            self.logger.warning("Not Connected!")
    # get available rooms
    # def get_rooms(self):