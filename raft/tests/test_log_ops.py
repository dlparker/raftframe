import unittest
import asyncio
import time
import logging
import traceback
import os

import pytest

from raft.log.log_api import LogRec
from raft.log.memory_log import MemoryLog

LOGGING_TYPE=os.environ.get("TEST_LOGGING", "silent")
if LOGGING_TYPE != "silent":
    logging.root.handlers = []
    lfstring = '%(process)s %(asctime)s [%(levelname)s] %(name)s: %(message)s'
    logging.basicConfig(format=lfstring,
                        level=logging.DEBUG)

    # set up logging to console
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    root = logging.getLogger()
    root.setLevel(logging.WARNING)
    raft_log = logging.getLogger("raft")
    raft_log.setLevel(logging.DEBUG)


class TestMemoryLog(unittest.TestCase):

    def test_mem_log(self):
        mlog = MemoryLog()
        rec = mlog.read()
        self.assertIsNone(rec)
        self.assertEqual(mlog.get_last_index(), 0)
        self.assertEqual(mlog.get_last_term(), 0)
        self.assertEqual(mlog.get_term(), 0)
        mlog.incr_term()
        self.assertEqual(mlog.get_term(), 1)
        limit1 = 100
        for i in range(int(limit1/2)):
            rec = LogRec(term=1, user_data=dict(index=i))
            mlog.append([rec,])
        self.assertEqual(mlog.get_last_index(), int(limit1/2))
        self.assertEqual(mlog.get_last_term(), 1)
        
        for i in range(int(limit1/2), limit1):
            rec = LogRec(term=2, user_data=dict(index=i))
            mlog.append([rec,])
        self.assertEqual(mlog.get_last_index(), limit1)
        self.assertEqual(mlog.get_last_term(), 2)
        with self.assertRaises(Exception) as context:
            mlog.commit(111)
        with self.assertRaises(Exception) as context:
            mlog.commit(0)

        mlog.commit(1)
        self.assertEqual(mlog.get_commit_index(), 1)
        rec1 = mlog.read(1)
        self.assertTrue(rec1.committed)
        for i in range(1, limit1 + 1):
            mlog.commit(i)
        self.assertEqual(mlog.get_commit_index(), limit1)
        for i in range(2, limit1+1):
            rec = mlog.read(i)
            self.assertTrue(rec.committed)

        # now rewrite a record
        rec = mlog.read(15)
        rec.user_data = "foo"
        x = mlog.replace_or_append(rec)
        self.assertEqual(x.index, 15)
        self.assertEqual(x.user_data, "foo")
        rec.index = None
        with self.assertRaises(Exception) as context:
            y = mlog.replace_or_append(rec)
        rec.index = 0
        with self.assertRaises(Exception) as context:
            y = mlog.replace_or_append(rec)
        rec.index = limit1 + 1
        y = mlog.replace_or_append(rec)
        self.assertEqual(y.index, limit1 + 1)
        
        with self.assertRaises(Exception) as context:
            mlog.read(0)
        with self.assertRaises(Exception) as context:
            mlog.read(1000)
