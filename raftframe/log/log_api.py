"""
Definitions for the API of the operations log managed by the state variants.

"""
import os
import abc
from dataclasses import dataclass, field, asdict
from typing import Union, List, Optional, Any
from enum import Enum

class RecordCode(str, Enum):
    """ String enum representing purpose of record. """

    """ When leader starts up, marks start of term with this """
    no_op = "NO_OP"

    """ Results of client command operation """
    client = "CLIENT" 

    """ Results of local client command operation """
    local_client = "LOCAL_CLIENT" 
    
@dataclass
class LogRec:
    code: RecordCode = field(default=RecordCode.client)
    index: int = field(default = 0)
    term: int = field(default = 0)
    committed: bool = field(default = False)
    user_data: list =  field(default=None, repr=False)

    @classmethod
    def from_dict(cls, data):
        rec = cls(RecordCode(data['code']),
                  index=data['index'],
                  term=data['term'],
                  committed=data['committed'],
                  user_data=data['user_data'])
        return rec
    
# abstract class for all states
class LogAPI(metaclass=abc.ABCMeta):
    """
    Abstract base class that functions as an interface definition for 
    implmentations of Log storage that can be used by the raftframe state classes
    to create and view log records to implement the algorythm.
    """
    
    @abc.abstractmethod
    def start(self, server, working_directory: os.PathLike): # pragma: no cover abstract
        raise NotImplementedError
    
    @abc.abstractmethod
    def get_term(self) -> int:  # pragma: no cover abstract
        raise NotImplementedError
    
    @abc.abstractmethod
    def set_term(self, value: int):  # pragma: no cover abstract
        raise NotImplementedError
    
    @abc.abstractmethod
    def incr_term(self) -> int:  # pragma: no cover abstract
        raise NotImplementedError
    
    @abc.abstractmethod
    def commit(self, index: int): # pragma: no cover abstract
        raise NotImplementedError

    @abc.abstractmethod
    def get_commit_index(self) -> int:  # pragma: no cover abstract
        raise NotImplementedError

    @abc.abstractmethod
    def append(self, entries: List[LogRec]):  # pragma: no cover abstract
        raise NotImplementedError

    @abc.abstractmethod
    def replace_or_append(self, entry: LogRec) -> LogRec:  # pragma: no cover abstract
        raise NotImplementedError

    @abc.abstractmethod
    def read(self, index: Union[int, None] = None) -> Union[LogRec, None]:  # pragma: no cover abstract
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_index(self) -> int:  # pragma: no cover abstract
        raise NotImplementedError

    @abc.abstractmethod
    def get_last_term(self) -> int:  # pragma: no cover abstract
        raise NotImplementedError

    
        



        
    
