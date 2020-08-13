import threading

from .debug import log


__waiter = threading.Event()

def wait(duration):
    if __debug__: log(f'waiting for {duration}s')
    __waiter.wait(duration)


def interrupt():
    if __debug__: log(f'interrupting wait')
    __waiter.set()


def interrupted():
    return __waiter.is_set()


def reset():
    if __debug__: log(f'clearing wait')
    __waiter.clear()
