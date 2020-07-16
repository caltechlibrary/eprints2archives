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

from .credentials import keyring_credentials, save_keyring_credentials
from .debug import log
from .ui import login_details


# Global constants.
# .............................................................................

_KEYRING = "org.caltechlibrary.".format(__package__)
'''The name of the keyring used to store Caltech access credentials, if any.'''


# Exported class.
# .............................................................................

class AuthHandler():
    '''Class to use the command line to ask the user for login & password.'''

    def __init__(self, user = None, pswd = None, use_keyring = True):
        '''Initializes internal data with user and password if available.'''
        self._user = user
        self._pswd = pswd
        self._use_keyring = use_keyring


    @property
    def user(self):
        '''Returns the last-provided user name.'''
        return self._user

    @property
    def pswd(self):
        '''Returns the last-provided password.'''
        return self._pswd


    def name_and_password(self, text, user = None, password = None):
        '''Returns a tuple of user, password, and a Boolean indicating
        whether the user cancelled the dialog.
        '''
        # If user name is provided and password is provided, use them.
        # If user name is provided and password is None, prompt for password.
        # If no user name is provided, look in keyring & prompt if not there.

        if __debug__: log('keyring {}', 'enabled' if self._use_keyring else 'disabled')
        tmp_user = user if user is not None else self._user
        tmp_pswd = password if password is not None else self._pswd
        if not tmp_user and self._use_keyring:
            if __debug__: log('getting login & password from keyring')
            k_user, k_pswd, _, _ = keyring_credentials(_KEYRING, tmp_user)
            if k_user is not None:
                tmp_user = k_user
                tmp_pswd = k_pswd
        cancel = False
        if not all([tmp_pswd, tmp_user]):
            tmp_user, tmp_pswd, cancel = login_details(text, tmp_user, tmp_pswd)
        if cancel:
            return tmp_user, tmp_pswd, True
        if self._use_keyring:
            # Save the credentials if they're different.
            s_user, s_pswd, _, _ = keyring_credentials(_KEYRING)
            if s_user != tmp_user or s_pswd != tmp_pswd:
                if __debug__: log('saving credentials to keyring')
                save_keyring_credentials(_KEYRING, tmp_user, tmp_pswd)
        self._user = tmp_user
        self._pswd = tmp_pswd
        return self._user, self._pswd, False
