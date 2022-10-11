#!/bin/bash
set -x
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
    $LOG_OPTION=$(-p no:logging)
else
    $LOG_OPTION=""
fi    


pytest --verbose --cov=raft --cov-config=`pwd`/raft/coverage.cfg --cov-report=html \
       --cov-report=term  -x --pdb --pdbcls=IPython.terminal.debugger:TerminalPdb \
       $LOG_OPTION \
       -s  $@
coverage combine --rcfile=`pwd`/raft/coverage.cfg --append
coverage html --rcfile=`pwd`/raft/coverage.cfg
coverage report --rcfile=`pwd`/raft/coverage.cfg
