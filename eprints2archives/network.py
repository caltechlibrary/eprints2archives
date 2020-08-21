'''
network.py: miscellaneous network utilities for Microarchiver

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2018-2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import http.client
from   http.client import responses as http_responses
from   os import stat
import requests
from   requests.packages.urllib3.exceptions import InsecureRequestWarning
from   requests.exceptions import *
import socket
import ssl
import urllib
from   urllib import request
import urllib3
import warnings

from .debug import log
from .exceptions import *
from .interruptions import wait, interrupted


# Constants.
# .............................................................................

_MAX_RECURSIVE_CALLS = 10
'''How many times can certain network functions call themselves upon
encountering a network error before they stop and give up.'''

_MAX_CONSECUTIVE_FAILS = 3
'''Maximum number of consecutive failures before pause and try another round.'''

_MAX_RETRIES = 5
'''Maximum number of times we back off and try again.  This also affects the
maximum wait time that will be reached after repeated retries.'''


# Main functions.
# .............................................................................

def network_available(address = "8.8.8.8", port = 53, timeout = 5):
    '''Return True if it appears we have a network connection, False if not.
    By default, this attempts to contact one of the Google DNS servers (as a
    plain TCP connection, not as an actual DNS lookup).  Argument 'address'
    and 'port' can be used to test a different server address and port.  The
    socket connection is attempted for 'timeout' seconds.
    '''
    # Portions of this code are based on the answer by user "7h3rAm" posted to
    # Stack Overflow here: https://stackoverflow.com/a/33117579/743730
    try:
        if __debug__: log('testing if we have a network connection')
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((address, port))
        if __debug__: log('we have a network connection')
        return True
    except Exception:
        if __debug__: log('could not connect to https://www.google.com')
        return False


def hostname(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.hostname


def scheme(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.scheme


def netloc(url):
    parsed = urllib.parse.urlsplit(url)
    return parsed.netloc


def timed_request(method, url, session = None, timeout = 20, **kwargs):
    '''Perform a network access, automatically retrying if exceptions occur.

    The value given to parameter "method" must be a string chosen from among
    valid HTTP methods, such as "get", "post", or "head".  If "session" is
    not None, it is used as a requests.Session object. "Timeout" is a timeout
    (in seconds) on the network requests get or post. Other keyword arguments
    are passed to the network call.
    '''
    def logurl(text):
        if __debug__: log(f'{text} for {url}')

    failures = 0
    retries = 0
    error = None
    while failures < _MAX_CONSECUTIVE_FAILS and not interrupted():
        try:
            with warnings.catch_warnings():
                # The underlying urllib3 library used by the Python requests
                # module will issue a warning about missing SSL certificates.
                # We don't care here.  See also this for a discussion:
                # https://github.com/kennethreitz/requests/issues/2214
                warnings.simplefilter("ignore", InsecureRequestWarning)
                if __debug__: logurl(f'doing http {method}')
                func = getattr(session, method) if session else getattr(requests, method)
                response = func(url, timeout = timeout, verify = False, **kwargs)
                if __debug__: logurl(f'received {response}')
                return response
        except (KeyboardInterrupt, UserCancelled) as ex:
            if __debug__: logurl(f'network {method} interrupted by {str(ex)}')
            raise
        except (MissingSchema, InvalidSchema, URLRequired, InvalidURL,
                InvalidHeader, InvalidProxyURL, UnrewindableBodyError,
                ContentDecodingError, ChunkedEncodingError) as ex:
            # Nothing more we can do about these.
            if __debug__: logurl(f'exception {str(ex)}')
            raise
        except Exception as ex:
            if ex.args and len(ex.args) > 0:
                if isinstance(ex.args[0], urllib3.exceptions.MaxRetryError):
                    # No point in retrying if we get this.
                    raise
            # Problem might be transient.  Don't quit right away.
            failures += 1
            if __debug__: logurl(f'exception (failure #{failures}): {str(ex)}')
            # Record the first error we get, not the subsequent ones, because
            # in the case of network outages, the subsequent ones will be
            # about being unable to reconnect and not the original problem.
            if not error:
                error = ex
            # Pause briefly b/c it's rarely a good idea to retry immediately.
            if __debug__: logurl('pausing for 0.5 s')
            wait(0.5)
        if failures >= _MAX_CONSECUTIVE_FAILS:
            # Pause with exponential back-off, reset failure count & try again.
            if retries < _MAX_RETRIES:
                retries += 1
                failures = 0
                pause = 10 * retries * retries
                if __debug__: logurl(f'pausing {pause} s due to consecutive failures')
                wait(pause)
            else:
                if __debug__: logurl('exceeded max failures and max retries')
                raise error
    if interrupted():
        if __debug__: logurl('interrupted -- raising UserCancelled')
        raise UserCancelled(f'Network request has been interrupted for {url}')
    else:
        # In theory, we should never reach this point.  If we do, then:
        raise InternalError(f'Unexpected code contingency in timed_request for {url}')


def net(method, url, session = None, timeout = 20, handle_rate = True,
        polling = False, recursing = 0, **kwargs):
    '''Invoke HTTP "method" on 'url' with optional keyword arguments provided.

    Returns a tuple of (response, exception), where the first element is
    the response from the get or post http call, and the second element is
    an exception object if an exception occurred.  If no exception occurred,
    the second element will be None.  This allows the caller to inspect the
    response even in cases where exceptions are raised.

    If keyword 'session' is not None, it's assumed to be a Python requests
    Session object to use for the network call.

    If keyword 'handle_rate' is True, this function will automatically pause
    and retry if it receives an HTTP code 429 ("too many requests") from the
    server.  If False, it will return the exception RateLimitExceeded instead.

    If keyword 'polling' is True, certain statuses like 404 are ignored and
    the response is returned; otherwise, they are considered errors.  The
    behavior when True is useful in situations where a URL does not exist until
    something is ready at the server, and the caller is repeatedly checking
    the URL.  It is up to the caller to implement the polling schedule and
    call this function (with polling = True) as needed.

    This method always passes the argument allow_redirects = True to the
    underlying Python requests library network call.
    '''
    def addurl(text):
        return f'{text} for {url}'

    resp = None
    try:
        resp = timed_request(method, url, session, timeout,
                             allow_redirects = True, **kwargs)
    except requests.exceptions.ConnectionError as ex:
        if __debug__: log(addurl(f'got network exception: {str(ex)}'))
        if recursing >= _MAX_RECURSIVE_CALLS:
            if __debug__: log(addurl('returning NetworkFailure'))
            return (resp, NetworkFailure(addurl('Too many connection errors')))
        arg0 = ex.args[0]
        if isinstance(arg0, urllib3.exceptions.MaxRetryError):
            if __debug__: log(addurl(str(arg0)))
            # This can be a transient error due to various causes.  Retry once.
            if recursing == 0:
                wait(1)
                return net(method, url, session, timeout, handle_rate,
                           polling, recursing + 1, **kwargs)
            else:
                # We've seen maxretry before or we're recursing due to some
                # other failure.  Time to bail.
                original = unwrapped_urllib3_exception(arg0)
                if __debug__: log(addurl('returning NetworkFailure'))
                if isinstance(original, str) and 'unreacheable' in original:
                    return (resp, NetworkFailure(addurl('Unable to connect to server')))
                elif network_available():
                    return (resp, NetworkFailure(addurl('Unable to resolve host')))
                else:
                    return (resp, NetworkFailure(addurl('Lost connection with server')))
        elif (isinstance(arg0, urllib3.exceptions.ProtocolError)
              and arg0.args and isinstance(args0.args[1], ConnectionResetError)):
            if __debug__: log(addurl('net() got ConnectionResetError; pausing for 1 s'))
            wait(1)                     # Sleep a short time and try again.
            if __debug__: log(addurl(f'doing recursive call #{recursing + 1}'))
            return net(method, url, session, timeout, polling, handle_rate,
                       recursing + 1, **kwargs)
        else:
            if __debug__: log(addurl('returning NetworkFailure'))
            return (resp, NetworkFailure(addurl(str(ex))))
    except requests.exceptions.ReadTimeout as ex:
        if network_available():
            if __debug__: log(addurl('returning ServiceFailure'))
            return (resp, ServiceFailure(addurl('Timed out reading data from server')))
        else:
            if __debug__: log(addurl('returning NetworkFailure'))
            return (resp, NetworkFailure(addurl('Timed out reading data over network')))
    except requests.exceptions.InvalidSchema as ex:
        if __debug__: log(addurl('returning NetworkFailure'))
        return (resp, NetworkFailure(addurl('Unsupported network protocol')))
    except Exception as ex:
        if __debug__: log(addurl(f'returning exception: {str(ex)}'))
        return (resp, ex)

    # Interpret the response.  Note that the requests library handles code 301
    # and 302 redirects automatically, so we don't need to do it here.
    error = None
    code = resp.status_code
    if __debug__: log(addurl(f'got http status code {code}'))
    if code == 400:
        error = ServiceFailure(addurl('Server rejected the request'))
    elif code in [401, 402, 403, 407, 451, 511]:
        error = AuthenticationFailure(addurl('Access is forbidden'))
    elif code in [404, 410] and not polling:
        error = NoContent(addurl("No content found"))
    elif code in [405, 406, 409, 411, 412, 414, 417, 428, 431, 505, 510]:
        error = InternalError(addurl(f'Server returned code {code} ({resp.reason})'))
    elif code in [415, 416]:
        error = ServiceFailure(addurl('Server rejected the request ({resp.reason})'))
    elif code == 429:
        if handle_rate and recursing < _MAX_RECURSIVE_CALLS:
            pause = 5 * (recursing + 1)   # +1 b/c we start with recursing = 0.
            if __debug__: log(addurl(f'rate limit hit -- sleeping {pause} s'))
            wait(pause)                   # 5 s, then 10 s, then 15 s, etc.
            if __debug__: log(addurl(f'doing recursive call #{recursing + 1}'))
            return net(method, url, session = session, timeout = timeout,
                       polling = polling, handle_rate = True,
                       recursing = recursing + 1, **kwargs)
        error = RateLimitExceeded(addurl('Server blocking requests due to rate limits'))
    elif code == 503:
        error = ServiceFailure(addurl(f'{resp.reason}'))
    elif code == 504:
        error = ServiceFailure(addurl(f'Server timeout: {resp.reason}'))
    elif code in [500, 501, 502, 506, 507, 508]:
        error = ServiceFailure(addurl(f'Server error (code {code} -- {resp.reason})'))
    elif not (200 <= code < 400):
        error = NetworkFailure(addurl(f'Unable to resolve {url}'))
    # The error msg will have had the URL added already; no need to do it here.
    if __debug__: log('returning {}'.format(f'error {error}' if error else 'no error'))
    return (resp, error)


# Next code originally from https://stackoverflow.com/a/39779918/743730
def disable_ssl_cert_check():
    requests.packages.urllib3.disable_warnings()
    try:
        _create_unverified_https_context = ssl._create_unverified_context
    except AttributeError:
        # Legacy Python that doesn't verify HTTPS certificates by default
        pass
    else:
        # Handle target environment that doesn't support HTTPS verification
        ssl._create_default_https_context = _create_unverified_https_context


def unwrapped_urllib3_exception(ex):
    if hasattr(ex, 'args') and isinstance(ex.args, tuple):
        return unwrapped_urllib3_exception(ex.args[0])
    else:
        return ex
