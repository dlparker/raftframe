#!/usr/bin/env python
import asyncio
import logging
import pytest
import time
from raftframe.v2.messages.request_vote import RequestVoteMessage,RequestVoteResponseMessage
from raftframe.v2.messages.append_entries import AppendEntriesMessage, AppendResponseMessage

logging.basicConfig(level=logging.DEBUG)

from raftframe.v2.tests.servers import WhenElectionDone
from raftframe.v2.tests.servers import PausingCluster, cluster_maker

async def test_restart_during_heartbeat(cluster_maker):
    cluster = cluster_maker(3)
    config = cluster.build_cluster_config()
    cluster.set_configs(config)
    uri_1 = cluster.node_uris[0]
    uri_2 = cluster.node_uris[1]
    uri_3 = cluster.node_uris[2]

    ts_1 = cluster.nodes[uri_1]
    ts_2 = cluster.nodes[uri_2]
    ts_3 = cluster.nodes[uri_3]

    logger = logging.getLogger(__name__)
    await cluster.start()
    await ts_3.hull.start_campaign()
    ts_1.set_trigger(WhenElectionDone())
    ts_2.set_trigger(WhenElectionDone())
    ts_3.set_trigger(WhenElectionDone())
        
    await asyncio.gather(ts_1.run_till_triggers(),
                         ts_2.run_till_triggers(),
                         ts_3.run_till_triggers())
    
    ts_1.clear_triggers()
    ts_2.clear_triggers()
    ts_3.clear_triggers()
    assert ts_3.hull.get_state_code() == "LEADER"
    assert ts_1.hull.state.leader_uri == uri_3
    assert ts_2.hull.state.leader_uri == uri_3

    # Get the leader to send out heartbeats, but
    # don't allow receives to get them yet, then
    # demote leader and let the messages fly.
    # The leader, now a follower should get a couple
    # of reply messages that it doesn't expect, and
    # should show up in hull log
    ts_3.hull.state.last_broadcast_time = 0
    ts_3.hull.message_problem_history = []
    await ts_3.hull.state.send_heartbeats()
    await cluster.deliver_all_pending(out_only=True)
    assert len(ts_1.in_messages) == 1
    assert len(ts_2.in_messages) == 1
    logger.debug("about to demote %s %s", uri_3, ts_3.hull.state)
    await ts_3.hull.demote_and_handle()
    await cluster.deliver_all_pending()
    assert len(ts_3.hull.message_problem_history) == 2

    await ts_3.hull.start_campaign()
    ts_1.set_trigger(WhenElectionDone())
    ts_2.set_trigger(WhenElectionDone())
    ts_3.set_trigger(WhenElectionDone())
        
    await asyncio.gather(ts_1.run_till_triggers(),
                         ts_2.run_till_triggers(),
                         ts_3.run_till_triggers())
    
    ts_1.clear_triggers()
    ts_2.clear_triggers()
    ts_3.clear_triggers()
    assert ts_3.hull.get_state_code() == "LEADER"
    assert ts_1.hull.state.leader_uri == uri_3
    assert ts_2.hull.state.leader_uri == uri_3
    # now just poke a random message in there to get
    # at the code that is very hard to arrange by
    # tweaking states, a vote response that isn't expected
    # when the receiver is not a newly elected leader,
    # with leftover votes coming in.
    msg = RequestVoteResponseMessage(sender=uri_2, receiver=uri_3,
                                     term=0, prevLogIndex=0, prevLogTerm=0, vote=False)
    ts_3.in_messages.append(msg)
    ts_3.hull.message_problem_history = []
    await ts_3.do_next_in_msg()
    assert len(ts_3.hull.message_problem_history) == 1
    rep = ts_3.hull.message_problem_history[0]
    assert rep['message'] == msg
