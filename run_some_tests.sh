#!/bin/bash
#set -x
export PYTHONBREAKPOINT=ipdb.set_trace
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
export PYTHONPATH=`pwd`

if [ -z ${VIRTUAL_ENV+x} ]; then
   source .venv/bin/activate
fi    
if [[ `which pytest` != $VIRTUAL_ENV/bin/pytest ]]; then
   source .venv/bin/activate
fi
if [ -z ${TEST_LOGGING+x} ]; then
    LOG_OPTION=""
else
    LOG_OPTION="-p no:logging"
fi    
if [ -z ${PYTEST_NO_STOP+x} ]; then
    STOP_OPTION="-x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb"
else
    STOP_OPTION=""
fi    
if [ -z ${DO_COVERAGE+x} ]; then
    COVER_OPTION=""
else
    COVER_OPTION="--cov=raftframe --cov-config=`pwd`/raftframe/coverage.cfg --cov-report=html --cov-report=term --cov-append"
fi    


pytest --verbose \
       $STOP_OPTION \
       $LOG_OPTION \
       $COVER_OPTION \
       -s  $@
if [ -z ${DO_COVERAGE+x} ]; then
    foo=""
else
    coverage combine --rcfile=`pwd`/raftframe/coverage.cfg --append
    coverage html --rcfile=`pwd`/raftframe/coverage.cfg
    coverage report --rcfile=`pwd`/raftframe/coverage.cfg
fi    
