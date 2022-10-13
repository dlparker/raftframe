import copy
import asyncio
import errno
import logging
import traceback

from ..states.timer import Timer
from ..utils import task_logger
from ..app_api.app import App

class Server:

    def __init__(self, name, state_map, log, other_nodes, endpoint, comms, app):
        self.name = name
        self.log = log
        self.endpoint = endpoint
        self.other_nodes = other_nodes
        self.total_nodes = len(self.other_nodes) + 1
        self.logger = logging.getLogger(__name__)
        self.comms = comms
        self.timer_class = None
        self.state_map = state_map
        self.state = None # needed because activate will call set_state
        self.app = app
        self.comms_task = None
        self.running = False
        task_logger.create_task(self.start(),
                                logger=self.logger,
                                message="server start task")

    async def start(self):
        self.app.set_server(self)
        self.state = await self.state_map.activate(self)
        self.comms_task = task_logger.create_task(
            self.comms.start(self, self.endpoint),
            logger=self.logger,
            message="server comms listener task"
        )
        self.logger.info('Server on %s', self.endpoint)
        self.running = True
        
    async def stop(self):
        self.comms_task.cancel()
        await self.state.stop()
        self.running = False
        
    def get_log(self):
        return self.log

    def get_app(self):
        return self.app

    def get_endpoint(self):
        return self.endpoint

    def get_state_map(self):
        return self.state_map
    
    def get_timer(self, name, term, interval, callback):
        self.logger.info("creating timer %s", name)
        if not self.timer_class:
            return Timer(name, term, interval, callback)
        return self.timer_class(name, term, interval, callback)

    def set_timer_class(self, cls):
        self.timer_class = cls

    def set_state(self, state):
        if self.state != state:
            self.state = state

    def get_state(self):
        return self.state

    async def on_message(self, message, recursed=False):
        try:
            pre_state = self.state
            handled = await self.state.on_message(message)
            if not handled:
                self.logger.info("on_message handler of state %s rejected"\
                                 " message %s", pre_state, message.code)
                if pre_state != self.state:
                    self.logger.info("changed state from %s to %s, recursing",
                                 pre_state, self.state)
                    if recursed:
                        raise Exception("already recursed, not doing it again" \
                                        " to avoid loop")
                    await self.on_message(message, recursed=True)
        except Exception as e:  # pragma: no cover error
            self.logger.error(traceback.format_exc())
            self.logger.error("State %s got exception %s on message %s",
                              self.state, e, message)

    async def post_message(self, message):
        await self.comms.post_message(message)

    async def send_message_response(self, message):
        n = [n for n in self.other_nodes if n == message.receiver]
        if len(n) > 0:
            await self.comms.post_message(message)
        
    async def broadcast(self, message):
        for n in self.other_nodes:
            # Have to create a deep copy of message to have different receivers
            send_message = copy.deepcopy(message)
            send_message._receiver = n
            self.logger.debug("%s sending message %s to %s", self.state,
                   send_message, n)
            task_logger.create_task(self.comms.post_message(send_message),
                                    logger=self.logger,
                                    message="post messsage")
