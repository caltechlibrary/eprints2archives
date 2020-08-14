import threading

from .debug import log
from .exceptions import *

__waiter = threading.Event()

def wait(duration):
    if __debug__: log(f'waiting for {duration}s')
    __waiter.wait(duration)
    if interrupted():
        if __debug__: log(f'raising UserCancelled')
        raise UserCancelled('Interrupted while waiting')


def interrupt():
    if __debug__: log(f'interrupting wait')
    __waiter.set()


def interrupted():
    return __waiter.is_set()


def raise_for_interrupts():
    if interrupted():
        if __debug__: log(f'raising UserCancelled')
        raise UserCancelled('Interrupted while waiting')

def reset():
    if __debug__: log(f'clearing wait')
    __waiter.clear()
