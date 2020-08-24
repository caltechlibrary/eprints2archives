'''
auth.py: code to deal with authenticating the user to the service

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2018-2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import getpass
import keyring
import sys

if sys.platform.startswith('win'):
    import keyring.backends
    from keyring.backends.Windows import WinVaultKeyring
if sys.platform.startswith('darwin'):
    import keyring.backends
    from keyring.backends.OS_X import Keyring

from .debug import log


# Global constants.
# .............................................................................

_KEYRING = f'org.caltechlibrary.{__package__}'
'''The name of the keyring used to store server access credentials, if any.'''

_EMPTY = ''
'''Character used to store an empty login name or password.'''


# Exported class.
# .............................................................................

class AuthHandler():
    '''Class to use the command line to ask the user for login & password.'''

    def __init__(self, prompter = None, user = None, pswd = None, use_keyring = True):
        '''Initializes this authentication handler object.

        The main purpose of AuthHandler is to provide the method named
        "credentials()", which callers can use to ask the user for a login name
        and password for a service.  In support of that goal, this init method
        takes arguments that set the user interface as well as default values
        for a user name and passsword, and whether to use a keyring.

        "prompter" must be a function that takes 3 arguments (a prompt string,
        an optional user name, and an optional password) and asks the user for
        login credentials, using the values of "user" and "pswd" as defaults.

        "user" can be a user name, if it is known at the time of creation of
        this AuthHandler object.  It will be used as the optional user name
        in calls to the "prompter".

        "password" can be a password, if it is known at the time of creation
        of this AuthHandler object.  It will be used as the optional password
        in calls to the "prompter".

        "use_keyring" should be a Boolean to indicate whether the keyring
        should be used.  If the value is False, then the calls to the function
        credentials(...) do not retrieve or store values in the keyring.
        '''
        self._prompter = prompter
        self._user = user
        self._pswd = pswd
        self._use_keyring = use_keyring


    # Explanation about the weird way this is done: the Python keyring module
    # only offers a single function for setting a value; ostensibly, this is
    # intended to store a password associated with an identifier (a user name),
    # and this identifier is expected to be obtained some other way, such as by
    # using the current user's computer login name.  This poses 2 problems for us:
    #
    #  1. The user may want to use a different user name for the remote service,
    #  so we can't assume the user's computer login name is the same.  We also
    #  don't want to ask for the remote user name every time we need the
    #  information, because that can end up presenting a dialog to the user every
    #  time, which quickly becomes unbearably annoying.  This means we can't use
    #  a user-generated identifer to access the keyring value -- we have to
    #  invent a value, and then store the user's name for the remote service as
    #  part of the value we store.
    #
    #  2. We need to store several pieces of information, not just a password,
    #  but the Python keyring module interface (and presumably most system
    #  keychains) does not allow anything but a string value.  The hackacious
    #  solution taken here is to concatenate several values into a single string
    #  used as the actual value stored.  The individual values are separated by a
    #  character that is unlikely to be part of any user-typed value.
    #
    # Explanation of values and their meanings:
    #   None                  => no value stored
    #   _EMPTY                => value stored and it is deliberately an empty string
    #   not None & not _EMPTY => an actual value

    def credentials(self, server, user = None, password = None):
        '''Returns a tuple of user, password, and a Boolean indicating
        whether the user cancelled the dialog.
        '''
        # If user name is provided and password is provided, use them.
        # If no user name is provided, look in keyring & prompt if not there.

        if __debug__: log('keyring {}', 'enabled' if self._use_keyring else 'disabled')
        tmp_user = user if user is not None else self._user
        tmp_pswd = password if password is not None else self._pswd
        if (tmp_user is None and tmp_pswd is None) and self._use_keyring:
            # We weren't given a user name, but we can look in the keyring.
            if __debug__: log(f'getting login & password for {server} from keyring')
            (_, k_user, k_pswd) = keyring_credentials(server)
            tmp_user = '' if k_user == _EMPTY else k_user
            tmp_pswd = '' if k_pswd == _EMPTY else k_pswd
        cancel = False
        if tmp_user is None or tmp_pswd is None:
            # If user is not None but password is, we still have to prompt.
            prompt = f'User credentials for {server}'
            tmp_user, tmp_pswd, cancel = self._prompter(prompt, tmp_user, tmp_pswd)
        if cancel:
            return tmp_user, tmp_pswd, True
        if self._use_keyring:
            # Save the credentials.
            if __debug__: log('saving new credentials to keyring')
            save_keyring_credentials(server, tmp_user or _EMPTY, tmp_pswd or _EMPTY)
        self._user = tmp_user
        self._pswd = tmp_pswd
        return self._user, self._pswd, False


# Utility functions
# .............................................................................

def keyring_credentials(server):
    '''Looks up credentials stored for the given "server".'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = keyring.get_password(_KEYRING, server)
    return _decoded(value) if value else (None, None, None)


def save_keyring_credentials(server = '', user = '', pswd = ''):
    '''Saves the "user" and "password" for "server".'''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    keyring.set_password(_KEYRING, server, _encoded(server, user, pswd))


_sep = ''
'''Character used to separate multiple actual values stored as a single
encoded value string.  This character is deliberately chosen to be something
very unlikely to be part of a legitimate string value typed by user at a
shell prompt, because control-c is normally used to interrupt programs.
'''


def _encoded(server, user, pswd):
    return f'{server}{_sep}{user}{_sep}{pswd}'


def _decoded(value_string):
    return tuple(value_string.split(_sep))
