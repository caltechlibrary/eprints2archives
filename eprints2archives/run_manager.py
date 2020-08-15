'''
run_manager.py: manage thread execution

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2018-2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   pubsub import pub
import sys
from   threading import Thread

from .debug import set_debug, log
from .exceptions import *
from .interruptions import interrupt


# Class definitions.
# .............................................................................
# This class abstracts away the details of starting both a worker thread and
# the user interface.  The latter typically involves starting a GUI
# interface, although those details are abstracted out to a separate UI class.
#
# The basic problem that this faces is that on macOS, the wx main loop cannot
# be started in a subthread: it must be started in the main thread.  However,
# the wx MainLoop() call is a blocking call, so as soon as we invoke it
# (whether directly or via the ui.start() call as done below), nothing further
# happens in the current thread until the wx app thread exits.  This prevents
# us from doing what would make the most sense, which is to use a subthread
# to start the wx MainLoop() so that we don't block, and can instead wait for
# the worker thread to finish.

class RunManager():
    '''Manager for overall program execution.'''

    def __init__(self):
        # Listen to stop messages.
        pub.subscribe(self.stop, "stop")


    def run(self, ui, worker):
        self._ui = ui
        self._worker = worker

        # On Windows, in Python 3.6+, ^C in a terminal window does not stop
        # execution (at least in my environment).  The following function
        # creates a closure with the worker object so that stop() can be called.

        if sys.platform == "win32":
            if __debug__: log('installing ctrl_handler for Windows')

            # This is defined here because we need the value of worker.ident.
            def ctrl_handler(event, *args):
                if __debug__: log('Keyboard interrupt received')
                from stopit import async_raise
                interrupt()
                async_raise(worker.ident, UserCancelled)
                worker.stop()

            import win32api
            win32api.SetConsoleCtrlHandler(ctrl_handler, True)

        # The worker must be a daemon thread when using the GUI; for CLI, it
        # must not be a daemon thread or else the program exits immediately.
        worker.daemon = ui.is_gui()

        # Must start worker before ui, because in the GUI case, ui.start()
        # will block until the UI thread exits.
        if __debug__: log('starting worker')
        worker.start()
        if __debug__: log('starting main UI loop')
        ui.start()
        if not ui.is_gui():
            if __debug__: log('waiting on worker thread')
            worker.join()
        if __debug__: log('stopping worker')
        worker.stop()


    def stop(self):
        if self._worker:
            if __debug__: log('calling stop() on worker')
            self._worker.stop()
            if __debug__: log('calling stop() on UI')
        self._ui.stop()
