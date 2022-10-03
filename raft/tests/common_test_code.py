import unittest
import asyncio
import time
import logging
import traceback
import os
from dataclasses import dataclass

from raft.tests.setup_utils import Cluster
from raft.tests.bt_client import UDPBankTellerClient, MemoryBankTellerClient

async def do_wait(seconds):
    start_time = time.time()
    while time.time() - start_time < seconds:
        await asyncio.sleep(0.01)

@dataclass
class RunData:
    leader: dict
    leader_addr: tuple
    first_follower: dict
    second_follower: dict
    
class BaseCase:

    class TestThreeServers(unittest.TestCase):
        
        @classmethod
        def setUpClass(cls):
            cls.logger = None
            pass
    
        @classmethod
        def tearDownClass(cls):
            pass
    
        def setUp(self):
            self.cluster = Cluster(server_count=3,
                                   use_processes=self.get_process_flag(),
                                   logging_type=self.get_logging_type(),
                                   base_port=5000)
            if self.logger is None:
                self.logger = logging.getLogger(__name__)
            self.cluster.start_all_servers()
            try:
                self.loop = asyncio.get_running_loop()
            except RuntimeError:
                self.loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self.loop)

        def tearDown(self):
            self.cluster.stop_all_servers()
            time.sleep(0.5)
            self.cluster.stop_logging_server()

        def test_non_leader_stop(self):
            self.logger.info("starting test_non_leader_stop")
            self.inner_test_non_leader_stop()

        def test_non_leader_restart(self):
            self.logger.info("starting test_non_leader_restart")
            self.inner_test_non_leader_stop(restart=True)
            
        def test_leader_stop(self):
            self.logger.info("starting test_leader_stop")
            self.inner_test_leader_stop()
            
        def test_leader_restart(self):
            self.logger.info("starting test_leader_restart")
            self.inner_test_leader_stop(restart=True)

        def run_data_from_status(self, status):
            run_data = {}
            leader_addr = status.data['leader']
            leader = None
            first_follower = None
            second_follower = None
            for name,sdef in self.cluster.server_recs.items():
                if sdef['port'] == leader_addr[1]:
                    sdef['role'] = "leader"
                    leader = sdef
                else:
                    if not first_follower:
                        first_follower = sdef
                    else:
                        second_follower = sdef
                    sdef['role'] = "follower"
            self.logger.info("found leader %s", leader_addr)
            run_data = RunData(leader, leader_addr, first_follower, second_follower)
            return run_data
            
        def wait_for_election_done(self, client, old_leader=None, timeout=3):
            self.logger.info("waiting for election results")
            start_time = time.time()
            while time.time() - start_time < timeout:
                time.sleep(0.25)
                status = client.get_status()
                if status and status.data['leader']:
                    new_leader_addr = status.data['leader']
                    if old_leader:
                        if old_leader != new_leader_addr:
                            break
                    else:
                        break
                status = None
            
            self.assertIsNotNone(status)
            self.assertIsNotNone(status.data['leader'])
            return self.run_data_from_status(status)

        def do_op_seq_1(self, client1, client2):
            self.logger.info("doing credit at %s", client1)
            client1.do_credit(10)
            self.logger.info("doing query of %s", client1)
            result = client1.do_query()
            self.assertEqual(result['balance'], 10)
            self.logger.info("initial call via %s worked", client1)
            # get a client for the first follower
            self.logger.info("doing query of %s", client2)
            result = client2.do_query()
            self.assertEqual(result['balance'], 10)
            self.logger.info("initial call via %s worked", client2)
            
        def do_op_seq_2(self, client):
            self.logger.info("doing query of %s", client)
            result = client.do_query()
            self.assertEqual(result['balance'], 10)
            self.logger.info("doing credit at %s", client)
            client.do_credit(10)
            self.logger.info("doing query of %s", client)
            result2 = client.do_query()
            self.assertEqual(result2['balance'], 20)
            self.logger.info("all operations working pass 2")
            
        def do_op_seq_3(self, client):
            self.logger.info("doing query of %s", client)
            result = client.do_query()
            self.assertEqual(result['balance'], 20)
            self.logger.info("doing credit at %s", client)
            client.do_credit(10)
            self.logger.info("doing query of %s", client)
            result = client.do_query()
            self.assertEqual(result['balance'], 30)
            self.logger.info("all operations working pass 3")
            
        def do_restart(self, server_def):
            self.logger.info("restarting server %s", server_def['name'])
            self.cluster.start_one_server(server_def['name'], vote_at_start=False)

            self.logger.info("restarted server, waiting for startup")
            status_exc = None
            start_time = time.time()
            while time.time() - start_time < 4:
                self.loop.run_until_complete(do_wait(0.25))
                try:
                    restart_client = self.get_client(server_def['port'])
                    status = restart_client.get_status()
                    if status:
                        break
                except Exception as e:
                    status_exc = e
            self.assertIsNone(status_exc, msg="Restart Failed!")
            return restart_client
            
        def inner_test_leader_stop(self, restart=False):
            client1 =  self.get_client(5000)
            run_data = self.wait_for_election_done(client1)
            client2 = self.get_client(run_data.first_follower['port'])
            self.do_op_seq_1(client1, client2)

            self.logger.info("stopping leader server %s", run_data.leader['name'])
            self.cluster.stop_server(run_data.leader['name']) 
            self.logger.info("server %s stopped", run_data.leader['name'])

            if run_data.leader['port'] == 5000:
                new_client = client2
            else:
                new_client = client1
            # wait for election to happen
            re_run_data = self.wait_for_election_done(new_client, run_data.leader_addr, 7)
            new_leader_addr = re_run_data.leader_addr
            self.assertNotEqual(new_leader_addr[0], -1,
                                msg="Leader election started but did not complete")
            self.assertNotEqual(new_leader_addr[1], run_data.leader['port'],
                                msg="Leader election never happend")
            self.logger.info("new leader found %s", new_leader_addr)

            self.do_op_seq_2(new_client)
            
            if not restart:
                return
            self.do_restart(run_data.leader)
            self.do_op_seq_3(new_client)
            
        def inner_test_non_leader_stop(self, restart=False):
            client1 =  self.get_client(5000)
            run_data = self.wait_for_election_done(client1)
            client2 = self.get_client(run_data.first_follower['port'])
            self.do_op_seq_1(client1, client2)

            self.logger.info("stopping non_leader server %s", run_data.second_follower['name'])
            self.cluster.stop_server(run_data.second_follower['name']) 
            self.logger.info("server %s stopped", run_data.second_follower['name'])

            self.do_op_seq_2(client1)
            
            if not restart:
                return
            self.do_restart(run_data.second_follower)
            self.do_op_seq_3(client1)
