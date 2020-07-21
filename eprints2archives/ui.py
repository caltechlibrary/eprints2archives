'''
ui.py: user interface

Explanation of the architecture
-------------------------------

After trying alternatives and failing to get things to work, I settled on the
following approach that works on both Mac and Windows 10 in my testing.

The control flow of this program is somewhat inverted from a typical WxPython
application.  The typical application would be purely event-driven: it would
be implemented as an object derived from wx.Frame with methods for different
kinds of actions that the user can trigger by interacting with controls in
the GUI.  Once the WxPython app.MainLoop() function is called, nothing
happens until the user does something to trigger an activitiy.  Conversely,
in this program, I not only wanted to allow command-line based interaction,
but also wanted the entire process to be started as soon as the user starts
the application.  This is incompatible with the typical event-driven
application structure because there's an explicit sequential driver and it
needs to be kicked off automatically after app.MainLoop() is called.

The approach taken here has two main features.

* First, there are two threads running: one for the WxPython GUI MainLoop()
  code and all GUI objects (like AppFrame and UserDialog in this file), and
  another thread for the real main body that implements the program's sequence
  of operations.  The main thread is kicked off by the GUI class start()
  method right before calling app.MainLoop().

* Second, the main body thread invokes GUI operations using a combination of
  in-application message passing (using a publish-and-subscribe scheme from
  PyPubsub) and the use of wx.CallAfter().  The AppFrame objects implement
  some methods that can be invoked by other classes, and AppFrame defines
  subscriptions for messages to invoke those methods.  Callers then have to
  use the following idiom to invoke the methods:

    wx.CallAfter(pub.sendMessage, "name", arg1 = "value1", arg2 = "value2")

  The need for this steps from the fact that in WxPython, if you attempt to
  invoke a GUI method from outside the main thread, it will either generate
  an exception or (what I often saw on Windows) simply hang the application.
  wx.CallAfter places the execution into the thread that's running
  MainLoop(), thus solving the problem.

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code is
open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import getpass
import os
import os.path as path
from   pubsub import pub
from   queue import Queue
import sys
import textwrap
from   time import sleep
import webbrowser
import wx
import wx.adv
import wx.lib
from   wx.lib.dialogs import ScrolledMessageDialog
import wx.richtext

from .app_frame import AppFrame
from .debug import log
from .exceptions import *
from .logo import getLogoIcon
from .styled import Styled, styled


# Exported functions
# .............................................................................
# These methods get an instance of the UI by themselves and do not require
# callers to do it.  They are meant to be used largely like basic functions
# such as "print()" are used in Python.

def inform(text, *args):
    '''Print an informational message to the user.  The 'text' can contain
    string format placeholders such as "{}", and the additional arguments in
    args are values to use in those placeholders.
    '''
    ui = UI.instance()
    ui.inform(text, *args)


def warn(text, *args):
    '''Warn the user that something is not right.  This should be used in
    situations where the problem is not fatal nor will prevent continued
    execution.  (For problems that prevent continued execution, use the
    alert(...) method instead.)
    '''
    ui = UI.instance()
    ui.warn(text, *args)


def alert(text, *args):
    '''Alert the user to an error.  This should be used in situations where
    there is a problem that will prevent normal execution.
    '''
    ui = UI.instance()
    ui.alert(text, *args)


def alert_fatal(text, *args, **kwargs):
    '''Print or display a message reporting a fatal error.  The keyword
    argument 'details' can be supplied to pass a longer explanation that will
    be displayed (when a GUI is being used) if the user presses the 'Help'
    button in the dialog.

    Note that when a GUI interface is in use, this method will cause the
    GUI to exit after the user clicks the OK button, so that the calling
    application can regain control and exit.
    '''
    ui = UI.instance()
    ui.alert_fatal(text, *args, **kwargs)


def file_selection(type, purpose, pattern = '*'):
    '''Returns the file selected by the user.  The value of 'type' should be
    'open' if the reason for the request is to open a file for reading, and
    'save' if the reason is to save a file.  The argument 'purpose' should be
    a short text string explaining to the user why they're being asked for a
    file.  The 'pattern' is a file pattern expression of the kind accepted by
    wxPython FileDialog.
    '''
    ui = UI.instance()
    return ui.file_selection(type, purpose, pattern)


def login_details(prompt, user, password):
    '''Asks the user for a login name and password.  The value of 'user' and
    'password' will be used as initial values in the dialog.
    '''
    ui = UI.instance()
    return ui.login_details(prompt, user, password)


def confirm(question):
    '''Returns True if the user replies 'yes' to the 'question'.'''
    ui = UI.instance()
    return ui.confirm(question)


# Base class for UI implementations
# .............................................................................
# This class is not meant to be accessed by external code directly.  The
# classes below subclass from this one and provide the actual implementations
# for the methods depending on the type of interface (GUI or CLI).

class UIBase:
    '''Base class for user interface classes.'''

    def __init__(self, name, subtitle, use_gui, use_color, be_quiet):
        ''''name' is the name of the application.  'subtitle' is a short
        string shown next to the name, in the form "name -- subtitle".
        'use_gui' indicates whether a GUI or CLI interface should be used.
        'use_color' applies only to the CLI, and indicates whether terminal
        output should be colored to indicate different kinds of messages.
        Finally, 'be_quiet' also applies only to the CLI and, if True,
        indicates that informational messages should not be printed.
        '''
        self._name      = name
        self._subtitle  = subtitle
        self._use_gui   = use_gui
        self._use_color = use_color
        self._be_quiet  = be_quiet


    def is_gui(self):
        return self._use_gui


    def app_name(self):
        return self._name


    def app_subtitle(self):
        return self._subtitle


    # Methods for starting and stopping the interface -------------------------

    def start(self): raise NotImplementedError
    def stop(self):  raise NotImplementedError


    # Methods to show messages to the user ------------------------------------

    def inform(self, text, *args):                    raise NotImplementedError
    def warn(self, text, *args):                      raise NotImplementedError
    def alert(self, text, *args):                     raise NotImplementedError
    def alert_fatal(self, text, *args, **kwargs):     raise NotImplementedError


    # Methods to ask the user -------------------------------------------------

    def file_selection(self, type, purpose, pattern): raise NotImplementedError
    def login_details(self, prompt, user, pswd):      raise NotImplementedError
    def confirm(self, question):                      raise NotImplementedError


# Exported classes.
# .............................................................................
# This class is essentially a wrapper that deals with selecting the real
# class that should be used for the kind of interface being used.  Internally
# it implements a singleton instance, and provides a method to access that
# instance.

class UI(UIBase):
    '''Wrapper class for the user interface.'''

    __instance = None

    def __new__(cls, name, subtitle, use_gui, use_color, be_quiet):
        '''Return an instance of the appropriate user interface handler.'''
        if cls.__instance is None:
            obj = GUI if use_gui else CLI
            cls.__instance = obj(name, subtitle, use_gui, use_color, be_quiet)
        return cls.__instance


    @classmethod
    def instance(cls):
        return cls.__instance


class CLI(UIBase, Styled):
    '''Command-line interface.'''


    def __init__(self, name, subtitle, use_gui, use_color, be_quiet):
        UIBase.__init__(self, name, subtitle, use_gui, use_color, be_quiet)
        Styled.__init__(self, apply_styling = not use_gui, use_color = use_color)
        if __debug__: log('initializing CLI')
        self._started = False

        # If another thread was eager to send messages before we finished
        # initialization, messages will get queued up on this internal queue.
        self._queue = Queue()

        # We want to print a welcome message, but have to queue it and wait
        # until the CLI has been fully started before printing it.
        num_dashes = 19 + len(self._name) + len(self._subtitle)
        if self._use_color:
            name = styled(self._name, ['chartreuse', 'bold'])
        else:
            name = self._name
        self.inform('┏' + '━'*num_dashes + '┓')
        self.inform('┃   Welcome to {}: {}   ┃', name, self._subtitle)
        self.inform('┗' + '━'*num_dashes + '┛')


    def start(self):
        '''Start the user interface.'''
        if __debug__: log('starting CLI')
        while not self._queue.empty():
            print(self._queue.get(), flush = True)
        self._started = True


    def stop(self):
        '''Stop the user interface.'''
        pass


    def _print_or_queue(self, text):
        if self._started:
            if __debug__: log(text)
            print(text, flush = True)
        else:
            if __debug__: log('queueing message "{}"', text)
            self._queue.put(text)


    def inform(self, text, *args):
        '''Print an informational message.'''
        if not self._be_quiet:
            self._print_or_queue(self.info_text(text, *args))
        else:
            if __debug__: log(text, *args)


    def warn(self, text, *args):
        '''Print a nonfatal, noncritical warning message.'''
        self._print_or_queue(self.warning_text(text, *args))


    def alert(self, text, *args):
        '''Print a message reporting an error.'''
        self._print_or_queue(self.error_text(text, *args))


    def alert_fatal(self, text, *args, **kwargs):
        '''Print a message reporting a fatal error.

        This method returns after execution and does not force an exit of
        the application.  In that sense it mirrors the behavior of the GUI
        version of alert_fatal(...), which also returns, but unlike the GUI
        version, this method does not stop the user interface (because in the
        CLI case, there is nothing equivalent to a GUI to shut down).
        '''
        text += '\n' + kwargs['details'] if 'details' in kwargs else ''
        self._print_or_queue(self.fatal_text(text, *args))


    def confirm(self, question):
        '''Asks a yes/no question of the user, on the command line.'''
        return input("{} (y/n) ".format(question)).startswith(('y', 'Y'))


    def file_selection(self, operation_type, question, pattern):
        '''Ask the user to type in a file path.'''
        return input(operation_type.capitalize() + ' ' + question + ': ')


    def login_details(self, prompt, user = None, pswd = None):
        '''Returns a tuple of user, password, and a Boolean indicating
        whether the user cancelled the dialog.  If 'user' is provided, then
        this method offers that as a default for the user.  If both 'user'
        and 'pswd' are provided, both the user and password are offered as
        defaults but the password is not shown to the user.
        '''
        try:
            text = (prompt + ' [default: ' + user + ']: ') if user else (prompt + ': ')
            input_user = input(text)
            if len(input_user) == 0:
                input_user = user
            hidden = ' [default: ' + '*'*len(pswd) + ']' if pswd else ''
            text = 'Password' + (' for "' + user + '"' if user else '') + hidden + ': '
            input_pswd = password(text)
            if len(input_pswd) == 0:
                input_pswd = pswd
            return input_user, input_pswd, False
        except KeyboardInterrupt:
            return user, pswd, True


class GUI(UIBase):
    '''Graphical user interface.'''

    def __init__(self, name, subtitle, use_gui, use_color, be_quiet):
        super().__init__(name, subtitle, use_gui, use_color, be_quiet)

        # Initialize our main GUI window.
        self._app = wx.App()
        self._frame = AppFrame(name, subtitle, None, wx.ID_ANY)
        self._app.SetTopWindow(self._frame)
        self._frame.Center()
        self._frame.Show(True)

        # Initialize some stuff we use to communicate with dialogs.
        self._queue = Queue()
        self._response = None


    def start(self):
        '''Start the user interface.'''
        if __debug__: log('starting main UI loop')
        self._app.MainLoop()


    def stop(self):
        '''Stop the user interface.'''
        if __debug__: log('stopping UI')
        wx.CallAfter(self._frame.Destroy)


    def confirm(self, question):
        '''Asks the user a yes/no question using a GUI dialog.'''
        if __debug__: log('generating yes/no dialog')
        wx.CallAfter(self._ask_yes_no, question)
        self._wait()
        if __debug__: log('got response: {}', self._response)
        return self._response


    def login_details(self, prompt, user = None, password = None):
        '''Shows a login-and-password dialog, and returns a tuple of user,
        password, and a Boolean indicating whether the user cancelled the
        dialog.  The dialog will be filled in with the values of 'user' and/or
        'password', if they are provided.
        '''
        # This uses a threadsafe queue to implement a semaphore.  The
        # login_dialog will put a results tuple on the queue, but until then,
        # a get() on the queue will block.  Thus, this function will block
        # until the login dialog is closed by the user.
        results = Queue()
        if __debug__: log('sending message to login_dialog')
        wx.CallAfter(pub.sendMessage, "login_dialog", results = results,
                     user = user, password = password)
        if __debug__: log('blocking to get results')
        results_tuple = results.get()
        if __debug__: log('name_and_password results obtained')
        # Results will be a tuple of user, password, cancelled
        return results_tuple[0], results_tuple[1], results_tuple[2]


    def file_selection(self, type, message, pattern):
        return_queue = Queue()
        if __debug__: log('sending message to {}_file', type)
        if type == 'open':
            wx.CallAfter(pub.sendMessage, 'open_file', return_queue = return_queue,
                         message = message, pattern = pattern)
        else:
            wx.CallAfter(pub.sendMessage, 'save_file', return_queue = return_queue,
                         message = message)
        if __debug__: log('blocking to get results')
        return_queue = return_queue.get()
        if __debug__: log('got results')
        return return_queue


    def inform(self, text, *args):
        '''Print an informational message.'''
        if __debug__: log('generating info notice')
        wx.CallAfter(pub.sendMessage, "info_message", message = text.format(*args))


    def warn(self, text, *args):
        '''Print a nonfatal, noncritical warning message.'''
        if __debug__: log('generating warning notice')
        wx.CallAfter(pub.sendMessage, "info_message",
                     message = 'Warning: ' + text.format(*args))


    def alert(self, text, *args, **kwargs):
        '''Print a message reporting a critical error.'''
        if __debug__: log('generating error notice')
        message = text.format(*args)
        details = kwargs['details'] if 'details' in kwargs else ''
        if wx.GetApp().TopWindow:
            wx.CallAfter(self._show_alert_dialog, message, details, 'error')
        else:
            # The app window is gone, so wx.CallAfter won't work.
            self._show_alert_dialog(message, details, 'error')
        self._wait()


    def alert_fatal(self, text, *args, **kwargs):
        '''Print a message reporting a fatal error.  The keyword argument
        'details' can be supplied to pass a longer explanation that will be
        displayed if the user presses the 'Help' button in the dialog.

        When the user clicks on 'OK', this causes the UI to quit.  It should
        result in the application to shut down and exit.
        '''
        if __debug__: log('generating fatal error notice')
        message = text.format(*args)
        details = kwargs['details'] if 'details' in kwargs else ''
        if wx.GetApp().TopWindow:
            wx.CallAfter(self._show_alert_dialog, message, details, 'fatal')
        else:
            # The app window is gone, so wx.CallAfter won't work.
            self._show_alert_dialog(message, details, 'fatal')
        self._wait()
        wx.CallAfter(pub.sendMessage, 'stop')


    def _ask_yes_no(self, question):
        '''Display a yes/no dialog.'''
        frame = self._current_frame()
        dlg = wx.GenericMessageDialog(frame, question, caption = self._name,
                                      style = wx.YES_NO | wx.ICON_QUESTION)
        clicked = dlg.ShowModal()
        dlg.Destroy()
        frame.Destroy()
        self._response = (clicked == wx.ID_YES)
        self._queue.put(True)


    def _show_note(self, text, *args, severity = 'info'):
        '''Displays a simple notice with a single OK button.'''
        if __debug__: log('showing note dialog')
        frame = self._current_frame()
        icon = wx.ICON_WARNING if severity == 'warn' else wx.ICON_INFORMATION
        dlg = wx.GenericMessageDialog(frame, text.format(*args),
                                      caption = self._name, style = wx.OK | icon)
        clicked = dlg.ShowModal()
        dlg.Destroy()
        frame.Destroy()
        self._queue.put(True)


    def _show_alert_dialog(self, text, details, severity = 'error'):
        if __debug__: log('showing message dialog')
        frame = self._current_frame()
        if severity == 'fatal':
            short = text
            style = wx.OK | wx.ICON_ERROR
            extra_text = 'fatal '
        else:
            short = text + '\n\nWould you like to try to continue?\n(Click "no" to quit now.)'
            style = wx.YES_NO | wx.YES_DEFAULT | wx.ICON_EXCLAMATION
            extra_text = ''
        if details:
            style |= wx.HELP
        caption = self._name + " has encountered a {}problem".format(extra_text)
        dlg = wx.MessageDialog(frame, message = short, style = style, caption = caption)
        clicked = dlg.ShowModal()
        if clicked == wx.ID_HELP:
            body = (self._name + " has encountered a problem:\n"
                    + "─"*30
                    + "\n{}\n".format(details or text)
                    + "─"*30
                    + "\nIf the problem is due to a network timeout or "
                    + "similar transient error, then please quit and try again "
                    + "later. If you don't know why the error occurred or "
                    + "if it is beyond your control, please also notify the "
                    + "developers. You can reach the developers via email:\n\n"
                    + "    Email: mhucka@library.caltech.edu\n")
            info = ScrolledMessageDialog(frame, body, "Error")
            info.ShowModal()
            info.Destroy()
            frame.Destroy()
            self._queue.put(True)
            if 'fatal' in severity:
                if __debug__: log('sending stop message to UI')
                wx.CallAfter(pub.sendMessage, 'stop')
        elif clicked in [wx.ID_NO, wx.ID_OK]:
            dlg.Destroy()
            frame.Destroy()
            self._queue.put(True)
            if __debug__: log('sending stop message to UI')
            wx.CallAfter(pub.sendMessage, 'stop')
        else:
            dlg.Destroy()
            self._queue.put(True)


    def _current_frame(self):
        '''Returns the current application frame, or a new app frame if none
        is currently active.  This makes it possible to use dialogs when the
        application main window doesn't exist.'''
        if wx.GetApp():
            if __debug__: log('app window exists; building frame for dialog')
            app = wx.GetApp()
            frame = wx.Frame(app.TopWindow)
        else:
            if __debug__: log("app window doesn't exist; creating one for dialog")
            app = wx.App(False)
            frame = wx.Frame(None, -1, __package__)
        frame.Center()
        return frame


    def _wait(self):
        self._queue.get()


# Miscellaneous utilities
# .............................................................................

def password(prompt):
    # If it's a tty, use the version that doesn't echo the password.
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    else:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return sys.stdin.readline().rstrip()
