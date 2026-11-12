"""Bounded loopback HTTP host for the disposable end-to-end qualification."""
from contextlib import contextmanager
import socket
import threading
import time
import uvicorn


@contextmanager
def serve_report(app):
    listener=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
    listener.bind(('127.0.0.1',0));listener.listen(128)
    server=uvicorn.Server(uvicorn.Config(app,log_level='error',access_log=False,lifespan='off',ws='none'))
    thread=threading.Thread(target=server.run,kwargs={'sockets':[listener]},daemon=True)
    thread.start();deadline=time.monotonic()+10
    try:
        while not server.started:
            if not thread.is_alive() or time.monotonic()>deadline:
                raise RuntimeError('Report server did not start')
            time.sleep(.01)
        yield 'http://127.0.0.1:'+str(listener.getsockname()[1])
    finally:
        server.should_exit=True;thread.join(timeout=10);listener.close()
        if thread.is_alive():raise RuntimeError('Report server did not stop')
