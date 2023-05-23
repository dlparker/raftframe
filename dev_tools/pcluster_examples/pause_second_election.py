#!/usr/bin/env python
"""
An example of how to run a cluster and do something when pausing happens.

It sets up a cluster of three servers, then configures them to pause 
on completion of leader election, and to call our pause_callback 
async function once paused. This allows us to identify the leader 
server so we can kill it. At this point the mainline code waits for a flag to 
be set and then tells all servers to resume. It then waits a bit and
then tells the leader to stop. This should result in another pause
on election but this one should show a different leader and a different
term.

"""
import os
import sys
import time
import asyncio
from pathlib import Path
import shutil
from raftframe.states.base_state import State, Substate
from dev_tools.log_control import one_proc_log_setup
from dev_tools.pserver import PServer
from dev_tools.pcluster import PausingCluster

if __name__=="__main__":
    wdir = Path(f"/tmp/raft_tests")
    if wdir.exists():
        shutil.rmtree(wdir)
    wdir.mkdir(parents=True)
    one_proc_log_setup(f"{wdir.as_posix()}/server.log")

    pc = PausingCluster(3, wdir)
    go_flag = False
    first_done = False
    first_leader = None
    second_leader = None
    async def pause_callback(pserver, context):
        global go_flag
        global first_done
        global first_leader
        global second_leader
        
        state = pserver.state_map.get_state()
        print(f'{pserver.name} {state} pausing')
        if str(state) == "leader":
            print("I am paused in leader server")
        elif str(state) == "candidate":
            print("I am paused in candidate server")
        elif str(state) == "follower":
            print("I am paused in follower server")
        if not first_done:
            first_done = True
            if str(state) == "leader":
                first_leader = pserver
                go_flag = True
                print("first pause done")
                return
        else:
            if str(state) == "leader":
                second_leader = pserver
        log = pserver.thread.server.get_log()
        print("*"*100)
        print(f"Server {pserver.name} log stats\n" 
              f"term = {log.get_term()}, last_rec_term = {log.get_last_term()}\n" 
              f"last_rec_index = {log.get_last_index()}, commit = {log.get_commit_index()}")
        print("*"*100)
        go_flag = True
        
    async def resume_callback(pserver):
        print(f'{pserver.name} resumed')
        
    for server in pc.servers:
        server.pause_callback = pause_callback
        server.resume_callback = resume_callback
        # pause leader after new term record
        server.pause_on_substate(Substate.became_leader)
        # pause followers after they accept leader
        server.pause_on_substate(Substate.joined)
    pc.start_all()
    paused = []
    while len(paused) < 3:
        paused = []
        for server in pc.servers:
            if server.paused:
                paused.append(server)
        time.sleep(0.1)
    print('All paused, awaiting go flag')
    while not go_flag:
        time.sleep(0.1)
    print('Got go flag, resuming')
    for server in pc.servers:
        server.resume()
    print('All resumed')
    print("Stopping leader")
    go_flag = False
    first_leader.stop()
    time.sleep(0.1)

    paused = []
    while len(paused) < 2:
        paused = []
        for server in pc.servers:
            if server != first_leader:
                if server.paused:
                    paused.append(server)
        time.sleep(0.1)
    print('Remaining paused, awaiting go flag')
    while not go_flag:
        time.sleep(0.1)
    print('Got go flag, resuming')
    for server in pc.servers:
        if server != first_leader:
            server.resume()
    print('All resumed')
    print('Stopping')
    for server in pc.servers:
        if server != first_leader:
            server.stop()
    stopped = []
    while len(stopped) < 3:
        stopped = []
        for server in pc.servers:
            if not server.running:
                stopped.append(server)
        time.sleep(0.1)
    print('All stopped')
    
        
    
    