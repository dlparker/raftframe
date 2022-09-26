import logging
from logging.config import dictConfig
from pathlib import Path

from log_server import LogSocketServer
from setup_utils import setup_base_dir

have_logging_server = False

def config_server_logging(filepath):
    lfstring = '%(process)s %(asctime)s [%(levelname)s] %(name)s: %(message)s'
    log_formaters = dict(standard=dict(format=lfstring))
    file_handler = dict(level="DEBUG",
                        formatter="standard",
                        encoding='utf-8',
                        mode='w',
                        filename=str(filepath))
    file_handler['class'] = "logging.FileHandler"
    log_handlers = dict(file=file_handler)
    the_log = dict(handlers=['file'], level="DEBUG", propagate=True)
    log_loggers = dict()
    log_loggers[''] = the_log
    log_config = dict(version=1, disable_existing_loggers = True,
                      formatters=log_formaters,
                      handlers=log_handlers,
                      loggers=log_loggers)
    return log_config
    
def config_logging(logfile_path, use_server=False, server_filepath=None):
    lfstring = '%(process)s %(asctime)s [%(levelname)s] %(name)s: %(message)s'
    log_formaters = dict(standard=dict(format=lfstring))
    file_handler = dict(level="DEBUG",
                        formatter="standard",
                        encoding='utf-8',
                        mode='w',
                        filename=str(logfile_path))
    file_handler['class'] = "logging.FileHandler"
    stdout_handler =  dict(level="DEBUG",
                           formatter="standard",
                           stream="ext://sys.stdout")
    # can't us "class" in above form
    stdout_handler['class'] = "logging.StreamHandler"
    #    socket_handler = logging.handlers.SocketHandler('localhost', 9999)
    log_handlers = dict(file=file_handler, stdout=stdout_handler)
    handler_names = ['file', 'stdout']
    server_config = None
    if use_server:
        socket_handler  = dict(level="DEBUG",
                               host="localhost",
                               port=9999)
        socket_handler['class'] = "logging.handlers.SocketHandler"
        log_handlers['sock'] = socket_handler
        handler_names.append("sock")
        server_config = config_server_logging(server_filepath)
    root_log = dict(handlers=handler_names, level="INFO", propagate=True)
    log_loggers = dict()
    log_loggers[''] = root_log
    raft_log = dict(handlers=handler_names, level="INFO", propagate=False)
    log_loggers['raft'] = raft_log
    follower_log = dict(handlers=handler_names, level="DEBUG", propagate=False)
    #log_loggers['raft.servers.server'] = follower_log
    log_loggers['raft.states.follower'] = follower_log
    log_loggers['raft.states.leader'] = follower_log
    log_loggers['raft.states.memory_log'] = follower_log
    log_config = dict(version=1, disable_existing_loggers = True,
                      formatters=log_formaters,
                      handlers=log_handlers,
                      loggers=log_loggers)
    return log_config, server_config

def setup_logging_for_test(name, file_path="/tmp/raft_tests/test.log",
                           use_server=True,
                           server_filepath="/tmp/raft_tests/combined.log",
                           extra_levels=None):
    setup_base_dir()
    config,server_config = config_logging(file_path,  use_server=use_server,
                                         server_filepath=server_filepath)
    
    # apply the caller's modifications to the level specs
    if extra_levels:
        # get an example logger
        examp = dict()
        examp.update(config['loggers'][''])
        for inspec in extra_levels:
            spec = dict(examp)
            spec['level'] = inspec['level']
            spec['propagate'] = inspec.get("propagate", False)
            config['loggers'][inspec['name']] = spec
    dictConfig(dict(version=1,
                    disable_existing_loggers = True,
                    formatters=[],
                      handlers=[],
                      loggers=[]))
    global have_logging_server
    if use_server and not have_logging_server:
        LogSocketServer.start(port=9999, configDict=server_config)
        have_logging_server = True
    dictConfig(config)
    logging.getLogger("test_control").info("starting test %s", name)
    return config
    
def stop_logging_server():
    global have_logging_server
    if have_logging_server:
        LogSocketServer.stop()
        have_logging_server = False
    

if __name__=="__main__":
    lfile = Path("/tmp/client.log")
    sfile = Path("/tmp/server.log")
    for x in [lfile, sfile]:
        if x.exists():
            x.unlink()

    levels = [dict(name="test", level="DEBUG", propagate=False),]
    config = setup_logging_for_test("test1", lfile, True, sfile,
                                    extra_levels=levels)
    logger = logging.getLogger("test")
    for i in range(10):
        logger.debug("log rec %d", i)
    import time
    time.sleep(0.5)
    stop_logging_server()