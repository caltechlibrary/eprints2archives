'''
credentials: credentials management code

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2018-2019 by the California Institute of Technology.  This code
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


# Credentials/keyring functions
# .............................................................................

def credentials(service, display_name, user=None, pswd=None, host=-1, port=-1,
                default_host=None, default_port=None):
    '''Asks the user for credentials.  If 'service' is provided, first gets the
    credentials for the system keyring under the name of the 'service', and
    only asks the user for missing information. Returns a 4-tuple:
        user name, password, host, port
    This doesn't save any information; it only queries the keyring and/or user.
    '''
    (s_user, s_pswd, s_host, s_port) = (None, None, None, None)
    if service:
        # If we're given a service, retrieve the stored (if any) for defaults.
        (s_user, s_pswd, s_host, s_port) = keyring_credentials(service)

    if host != -1 and not host:
        host = s_host or input("{} host (default: {}): ".format(display_name,
                                                                default_host))
        host = host or default_host
    if port != -1 and not port:
        port = s_port or input("{} port (default: {}): ".format(display_name,
                                                                default_port))
        port = port or default_port
    if not user:
        user = s_user or input("{} user name: ".format(display_name))
    if not pswd:
        pswd = s_pswd or password('{} password: '.format(display_name))

    return (user, pswd, host, port)

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
#  part of the value we store.  (Here, we use the fake user name "credentials" to
#  access the value stored in the user's keyring for a given service.)
#
#  2. We need to store several pieces of information, not just a password,
#  but the Python keyring module interface (and presumably most system
#  keychains) does not allow anything but a string value.  The hackacious
#  solution taken here is to concatenate several values into a single string
#  used as the actual value stored.  The individual values are separated by a
#  character that is unlikely to be part of any user-typed value.

def keyring_credentials(service, user=None):
    '''Looks up the user's credentials for the given 'service' using the
    keyring/keychain facility on this computer.  If 'user' is None, this uses
    the fake user named "credentials".  The latter makes it possible to access a
    service with a different user login name than the user's current login
    name without having to ask the user for the alternative name every time.
    '''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    value = keyring.get_password(service, user if user else 'credentials')
    return _decoded(value) if value else (None, None, None, None)


def save_keyring_credentials(service, user, pswd, host=None, port=None):
    '''Saves the user, password, host and port info for 'service'.'''
    user = user if user else ''
    pswd = pswd if pswd else ''
    host = host if host else ''
    port = port if port else ''
    if sys.platform.startswith('win'):
        keyring.set_keyring(WinVaultKeyring())
    if sys.platform.startswith('darwin'):
        keyring.set_keyring(Keyring())
    keyring.set_password(service, 'credentials', _encoded(user, pswd, host, port))


_sep = ''
'''Character used to separate multiple actual values stored as a single
encoded value string.  This character is deliberately chosen to be something
very unlikely to be part of a legitimate string value typed by user at a
shell prompt, because control-c is normally used to interrupt programs.
'''

def _encoded(user, pswd, host, port):
    return '{}{}{}{}{}{}{}'.format(user, _sep, pswd, _sep, host, _sep, port)


def _decoded(value_string):
    return tuple(value_string.split(_sep))


def password(prompt):
    # If it's a tty, use the version that doesn't echo the password.
    if sys.stdin.isatty():
        return getpass.getpass(prompt)
    else:
        sys.stdout.write(prompt)
        sys.stdout.flush()
        return sys.stdin.readline().rstrip()


# For Emacs users
# ......................................................................
# Local Variables:
# mode: python
# python-indent-offset: 4
# End:
