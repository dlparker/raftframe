import unittest
import asyncio
import time
import logging
import traceback
import os
from pathlib import Path


from raft.messages.heartbeat import HeartbeatMessage
from raft.messages.heartbeat import HeartbeatResponseMessage
from raft.messages.append_entries import AppendResponseMessage
from raft.messages.append_entries import AppendEntriesMessage
from raft.states.base_state import StateCode
from raft.dev_tools.ps_cluster import PausingServerCluster
from raft.dev_tools.pausing_app import InterceptorMode, TriggerType
from raft.dev_tools.pausing_app import PausingMonitor, PLeader, PFollower

LOGGING_TYPE=os.environ.get("TEST_LOGGING", "silent")
if LOGGING_TYPE != "silent":
    LOGGING_TYPE = "devel_one_proc"

from raft.dev_tools.pausing_app import TriggerType

class Pauser:
    
    def __init__(self, spec, tcase):
        self.spec = spec
        self.tcase = tcase
        self.am_leader = False
        self.paused = False
        self.broadcasting = False
        self.sent_count = 0
        
    def reset(self):
        self.am_leader = False
        self.paused = False
        self.broadcasting = False
        self.sent_count = 0
        
    async def leader_pause(self, mode, code, message):
        self.am_leader = True
        self.tcase.leader = self.spec
        
        limit = self.tcase.expected_followers
        if self.broadcasting or code == "heartbeat":
            # we are sending one to each follower, whether
            # it is running or not
            limit = len(self.tcase.servers) - 1
        elif code == "append_entries":
            if len(message.data['entries']) > 0:
                first = message.data['entries'][0]
                if first["code"] == "NO_OP":
                    limit = len(self.tcase.servers) - 1
                    self.tcase.logger.info("limit logic for interceptor" \
                                            " sending NO_OP, so %d",
                                            limit)
                else:
                    self.tcase.logger.info("limit logic for interceptor" \
                                            " not NO_OP, so %d",
                                            limit)
        # make sure our copy of the server spec is up to date
        self.spec = self.tcase.servers[self.spec.name]
        if self.spec.running:
            self.sent_count += 1
            if self.sent_count < limit:
                self.tcase.logger.info("not pausing on %s, sent count" \
                                        " %d not yet %d", code,
                                        self.sent_count, limit)
                return True
        else:
            self.tcase.logger.info("server %s not running, not counting" \
                                    " message %s, %d not yet %d",
                                    self.spec.name, code,
                                    self.sent_count, limit)
            return True
            

        self.tcase.logger.info("got sent for %s followers, pausing",
                               limit)
        await self.spec.pbt_server.pause_all(TriggerType.interceptor,
                                             dict(mode=mode,
                                                  code=code))
        return True
    
    async def follower_pause(self, mode, code, message):
        self.am_leader = False
        self.tcase.non_leaders.append(self.spec)
        self.paused = True
        await self.spec.pbt_server.pause_all(TriggerType.interceptor,
                                             dict(mode=mode,
                                                  code=code))
        return True

class TestCaseCommon(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.total_nodes = 3
        cls.timeout_basis = 0.1
        cls.logger_name = __name__
        
    @classmethod
    def tearDownClass(cls):
        pass
    
    def setUp(self):
        self.cluster = PausingServerCluster(server_count=self.total_nodes,
                                            logging_type=LOGGING_TYPE,
                                            base_port=5000,
                                            timeout_basis=self.timeout_basis)
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        self.logger = logging.getLogger(self.logger_name)
                
    def tearDown(self):
        self.cluster.stop_all_servers()
        time.sleep(0.1)
        self.loop.close()

    def pause_waiter(self, label, expected=None, timeout=2):
        if expected is None:
            expected = self.total_nodes
        self.logger.info("waiting for %s", label)
        self.leader = None
        self.non_leaders = []
        start_time = time.time()
        while time.time() - start_time < timeout:
            # servers are in their own threads, so
            # blocking this one is fine
            time.sleep(0.01)
            pause_count = 0
            self.non_leaders = []
            for spec in self.servers.values():
                if spec.pbt_server.paused:
                    pause_count += 1
                    if spec.monitor.state.get_code() == StateCode.leader:
                        self.leader = spec
                    else:
                       self.non_leaders.append(spec)
            if pause_count >= expected:
                break
        self.assertIsNotNone(self.leader)
        self.assertEqual(len(self.non_leaders) + 1, expected)
        return 

    def resume_waiter(self):
        start_time = time.time()
        while time.time() - start_time < 5:
            # servers are in their own threads, so
            # blocking this one is fine
            time.sleep(0.01)
            pause_count = 0
            for spec in self.servers.values():
                if spec.running:
                    if spec.pbt_server.paused:
                        pause_count += 1
            if pause_count == 0:
                break
        self.assertEqual(pause_count, 0)

    def reset_pausers(self):
        for name in self.servers.keys():
            self.pausers[name].reset()

    def reset_roles(self):
        self.leader = None
        self.non_leaders = []
        
    def preamble(self, num_to_start=None, slow=False, pre_start_callback=None):
        if slow:
            tb = 1.0
        else:
            tb = self.timeout_basis
        self.servers = self.cluster.prepare(timeout_basis=tb)
        if num_to_start is None:
            num_to_start = len(self.servers)
        self.pausers = {}
        self.leader = None
        self.non_leaders = []
        for spec in self.servers.values():
            self.pausers[spec.name] = Pauser(spec, self)
        self.expected_followers = num_to_start - 1
        self.set_term_start_intercept()

        if pre_start_callback:
            pre_start_callback()
        started_count = 0
        for spec in self.cluster.get_servers().values():
            self.cluster.start_one_server(spec.name)
            started_count += 1
            if started_count == num_to_start:
                break

        self.pause_waiter("waiting for pause first election done (append)",
                          expected = started_count)

    def update_pauser(self, spec):
        # call when you restart a server, old pauser will not work
        pauser = Pauser(spec, self)
        self.pausers[spec.name] = pauser
        return pauser

    def set_term_start_intercept(self, clear=True):
        for spec in self.servers.values():
            if clear:
                spec.interceptor.clear_triggers()
            spec.interceptor.add_trigger(InterceptorMode.out_after, 
                                         AppendEntriesMessage._code,
                                         self.pausers[spec.name].leader_pause)
            spec.interceptor.add_trigger(InterceptorMode.in_before, 
                                         AppendEntriesMessage._code,
                                         self.pausers[spec.name].follower_pause)

    def set_hb_intercept(self, clear=True):

        for spec in self.servers.values():
            if clear:
                spec.interceptor.clear_triggers()
            spec.interceptor.add_trigger(InterceptorMode.out_after, 
                                         HeartbeatMessage._code,
                                         self.pausers[spec.name].leader_pause)
            spec.interceptor.add_trigger(InterceptorMode.in_before, 
                                         HeartbeatMessage._code,
                                         self.pausers[spec.name].follower_pause)
    def clear_intercepts(self):
        for spec in self.servers.values():
            spec.interceptor.clear_triggers()
        
    def postamble(self):
    
        for spec in self.servers.values():
            spec.interceptor.clear_triggers()

        self.cluster.resume_all_paused_servers()
        
    def pause_and_break(self, go_after=True):
        # call this to get a breakpoint that has
        # everyone stopped
        time.sleep(1)
        self.reset_pausers()
        self.set_hb_intercept()
        breakpoint()
        if go_after:
            self.clear_intercepts()
            self.cluster.resume_all_paused_servers()

    def go_after_break(self):
        self.clear_intercepts()
        self.cluster.resume_all_paused_servers()
        
    def a_test_check_setup(self):
        # rename this to remove the a_ in order to
        # check the basic control flow if you think
        # it might be brokens
        self.preamble(num_to_start=3)
        self.clear_intercepts()
        self.cluster.resume_all_paused_servers()
        self.logger.debug("\n\n\tCredit 10 \n\n")
        client = self.leader.get_client()
        client.do_credit(10)
        self.logger.debug("\n\n\tQuery to %s \n\n", self.leader.name)
        res = client.do_query()
        self.assertEqual(res['balance'], 10)
        self.postamble()
