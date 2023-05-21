from __future__ import annotations
import abc
from typing import Optional, Union
import asyncio
import logging
import traceback

from raftframe.app_api.app import StateChangeMonitor
from raftframe.states.base_state import State, Substate
from raftframe.states.candidate import Candidate
from raftframe.states.follower import Follower
from raftframe.states.leader import Leader


# abstract class for all states
class StateMap(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    async def activate(self, server) -> State:
        """ Stores a reference to the server object. This must
        be called before any of the other methods.
        Assumes there is no current state and switches to 
        the first state, telling it and the server about each other.
        In the standard state map, the "first" state is Follower.
        StateMap implementors can choose to have some additional
        state happen prior to the switch to Follower by making
        this method switch to that one. 
        """
        raise NotImplementedError
    
    def get_server(self):
        """ Returns the reference to the server object. 
        TODO: should create a base class for Servers 
        to be used in type hints.
        """
        raise NotImplementedError

    @abc.abstractmethod
    def get_state(self) -> State:
        raise NotImplementedError

    @abc.abstractmethod
    def changing_state(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def add_state_change_monitor(self, monitor: StateChangeMonitor) -> None:
        raise NotImplementedError
        
    @abc.abstractmethod
    def remove_state_change_monitor(self, monitor: StateChangeMonitor) -> None:
        raise NotImplementedError
        
    @abc.abstractmethod
    def start_state_change(self, old_state: Union[str, None],
                           new_state: str) -> None:
        raise NotImplementedError
    
    @abc.abstractmethod
    def finish_state_change(self, old_state: Union[str, None],
                            new_state: str) -> None:
        raise NotImplementedError
    
    @abc.abstractmethod
    def switch_to_follower(self, old_state: Optional[State] = None) -> Follower:
        raise NotImplementedError

    @abc.abstractmethod
    def switch_to_candidate(self, old_state: Optional[State] = None) -> Candidate:
        raise NotImplementedError

    @abc.abstractmethod
    def switch_to_leader(self, old_state: Optional[State] = None) -> Leader:
        raise NotImplementedError
    
    
class StandardStateMap(StateMap):

    def __init__(self, timeout_basis=1.0):
        self.server = None
        self.state = None
        self.queue = None
        self.logger = None
        self.monitors = None
        self.timeout_basis = timeout_basis
        self.follower_leaderless_timeout = 0.75 * timeout_basis
        self.candidate_voting_timeout = 0.5 * timeout_basis
        self.leader_heartbeat_timeout = 0.5 * timeout_basis
        self.changing = False
        self.pre_change = None
        
    # can't be done with init because instance
    # of this class required for server class init
    async def activate(self, server) -> State:
        if not self.monitors:
            self.monitors = []
        self.server = server
        self.state = None
        self.substate = None
        self.logger = logging.getLogger(__name__)
        self.logger.info("activating state map for server %s", server)
        return await self.switch_to_follower()

    def add_state_change_monitor(self, monitor: StateChangeMonitor) -> None:
        if not self.monitors:
            self.monitors = []
        if monitor not in self.monitors:
            self.monitors.append(monitor)
            
    def remove_state_change_monitor(self, monitor: StateChangeMonitor) -> None:
        if monitor in self.monitors:
            self.monitors.remove(monitor)
            
    def get_server(self):
        return self.server
    
    def get_state(self) -> Optional[State]:
        if not self.server:
            raise Exception('must call activate before this method!')
        return self.state

    def get_substate(self) -> Optional[State]:
        if not self.server:
            raise Exception('must call activate before this method!')
        return self.substate
    
    def changing_state(self) -> bool:
        return self.changing

    def start_state_change(self, old_state: Union[str, None],
                           new_state: str) -> None:
        self.changing = True
        self.pre_change = self.state
    
    def finish_state_change(self, old_state: Union[str, None],
                            new_state: str) -> None:
        self.changing = False
        self.pre_change = None
    
    def failed_state_change(self, old_state: Union[str, None],
                            target_state: str,
                            error_data: str) -> None:
        self.changing = False
        self.server.record_failed_state_change(old_state, target_state,
                                               error_data)
        self.state = self.pre_change
        self.pre_change = None
    
    async def set_substate(self, state, substate):
        if not self.server:
            msg = 'must call activate before this method!'
            raise Exception(msg)
        if state != self.state:
            msg = 'set_substate call on non-current state!'
            self.logger.error(msg)
            raise Exception(msg)
        for monitor in self.monitors:
            try:
                await monitor.new_substate(self, state, substate)
            except GeneratorExit: # pragma: no cover error
                pass
            except:
                self.logger.error("Monitor new_substate call got" \
                                  " exception \n\t%s",
                                  traceback.format_exc())
        self.substate = substate
        
    async def switch_to_follower(self, old_state: Optional[State] = None) -> Follower:
        if not self.server:
            raise Exception('must call activate before this method!')
        self.logger.info("switching state from %s to follower", self.state)
        follower =  Follower(server=self.server,
                             timeout=self.follower_leaderless_timeout)
        for monitor in self.monitors:
            try:
                follower = await monitor.new_state(self, self.state, follower)
            except GeneratorExit: # pragma: no cover error
                raise
            except:
                self.logger.error("Monitor new_state call got exception \n\t%s",
                                  traceback.format_exc())
        self.state = follower
        if old_state:
            os_name = str(old_state)
        else:
            os_name = None
        follower.start()
        await asyncio.sleep(0)
        self.finish_state_change(os_name, 'follower')
        return follower
    
    async def switch_to_candidate(self, old_state: Optional[State] = None) -> Candidate:
        if not self.server:
            raise Exception('must call activate before this method!')
        self.logger.info("switching state from %s to candidate", self.state)
        candidate =  Candidate(server=self.server,
                               timeout=self.candidate_voting_timeout)
        for monitor in self.monitors:
            try:
                candidate = await monitor.new_state(self, self.state, candidate)
            except GeneratorExit: # pragma: no cover error
                pass
            except:
                self.logger.error("Monitor new_state call got exception \n%s",
                                  traceback.format_exc())
        self.state = candidate
        if old_state:
            os_name = str(old_state)
        else:
            os_name = None
        candidate.start()
        await asyncio.sleep(0)
        self.finish_state_change(os_name, 'candidate')
        return candidate

    async def switch_to_leader(self, old_state: Optional[State] = None) -> Leader:
        if not self.server:
            raise Exception('must call activate before this method!')
        self.logger.info("switching state from %s to leader", self.state)
        leader =  Leader(server=self.server,
                         heartbeat_timeout=self.leader_heartbeat_timeout)

        for monitor in self.monitors:
            try:
                leader = await monitor.new_state(self, self.state, leader)
            except GeneratorExit: # pragma: no cover error
                pass
            except:
                self.logger.error("Monitor new_state call got exception \n%s",
                                  traceback.format_exc())
        self.state = leader
        if old_state:
            os_name = str(old_state)
        else:
            os_name = None
        leader.start()
        await asyncio.sleep(0)
        self.finish_state_change(os_name, 'candidate')
        return leader

    
    
