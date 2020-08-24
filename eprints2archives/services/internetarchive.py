'''
internetarchive.py: interface to the Wayback Machine at the Internet Archive.

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   humanize import intcomma
import requests
from   time import sleep

from ..debug import log
from ..exceptions import *
from ..interruptions import wait
from ..network import net
from ..ui import warn

from .base import Service
from .timemap import timemap_as_dict, timemap_mementos
from .upload_status import ServiceStatus


# Constants.
# .............................................................................

_MAX_RETRIES = 8
'''Maximum number of times we retry before we give up.'''

_RETRY_SLEEP = 60
'''Time in seconds we pause if we get repeated errors.  This pause is on top
of the maximum time reached after exponential back-off by our underlying
network code, and is used to pause before the whole scheme is retried again.
This needs to be a long time because if we invoke our own retry loop, it means
we've already been trying for a considerable amount of time and the root cause
may be significant.'''

_RATE_LIMIT_SLEEP = 10
'''Time in seconds we pause if we hit the rate limit.  This is handled
separately from error conditions.'''


# Classes.
# .............................................................................

class InternetArchive(Service):
    label = 'internetarchive'
    name  = 'Internet Archive'
    color = 'white'

    # Public methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def save(self, url, notify, force = False):
        '''Ask the service to save "url".'''
        if force:
            # If we're forcing a send, we don't care how many there exist.
            added = self._archive(url, notify)
            return (added, -1)

        timemap = self._timemap_for_url(url, notify)
        if timemap:
            mementos = timemap_mementos(timemap)
            if __debug__: log(f'{self.name} returned {len(mementos)} mementos for {url}')
            return (False, len(mementos))
        else:
            if __debug__: log(f'{self.name} returned no mementos for {url}')
            added = self._archive(url, notify)
            return (added, 0)


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _uniform(self, url):
        return str(url).strip().replace(' ', '_')


    def _timemap_for_url(self, url, notify):
        '''Returns a timemap, in the form of a dict.'''
        if __debug__: log(f'asking {self.name} for info about {url}')

        action_url = 'https://web.archive.org/web/timemap/link/' + self._uniform(url)
        (response, error) = net('get', action_url, handle_rate = False)
        if not error and response:
            if __debug__: log('converting TimeMap to dict')
            return timemap_as_dict(response.text, skip_errors = True)
        elif isinstance(error, NoContent):
            if __debug__: log(f'no content for {url}')
            return {}
        elif isinstance(error, RateLimitExceeded):
            if __debug__: log(f'{self.name} rate limit; pausing {_RATE_LIMIT_SLEEP}s')
            notify(ServiceStatus.PAUSED_RATE_LIMIT)
            wait(_RATE_LIMIT_SLEEP)
            notify(ServiceStatus.RUNNING)
            return self._timemap_for_url(url, notify)
        else:
            if __debug__: log(f'got {error} for {url}')
            raise error


    def _archive(self, url, notify, retry = 0):
        if __debug__: log(f'asking {self.name} to save {url}')
        if retry > 0:
            if __debug__: log(f'this is retry #{retry}')
        payload = {'url': url, 'capture_all': 'on'}
        action_url = 'https://web.archive.org/save/' + self._uniform(url)
        (response, error) = net('post', action_url, handle_rate = False, data = payload)
        if not error:
            if __debug__: log(f'save request accepted by {self.name}')
            return True
        elif isinstance(error, RateLimitExceeded):
            if __debug__: log(f'{self.name} rate limit; pausing {_RATE_LIMIT_SLEEP}s')
            notify(ServiceStatus.PAUSED_RATE_LIMIT)
            wait(_RATE_LIMIT_SLEEP)
            notify(ServiceStatus.RUNNING)
            if __debug__: log(f'trying again recursively for {url}')
            return self._archive(url, notify)
        else:
            if __debug__: log(f'save request resulted in an error: {str(error)}')
            # Our underlying net(...) function will retry automatically in
            # the face of problems, but will give up eventually.  Sometimes
            # IA errors are temporary, so we pause for even longer & retry.
            retry += 1
            retries_left = _MAX_RETRIES - retry
            if __debug__: log(f'we have {retries_left} retries left')
            if retry == 1:
                # Might have been a transient server-unavailable type of error.
                if __debug__: log(f'retrying once without pause')
                return self._archive(url, notify, retry)
            elif retries_left > 0:
                # Subtract 1 b/c we try without pause once, before we land here.
                if __debug__: log(f'pausing due to multiple retries')
                sleeptime = _RETRY_SLEEP * pow(retry - 1, 2)
                notify(ServiceStatus.PAUSED_ERROR)
                wait(sleeptime)
                notify(ServiceStatus.RUNNING)
                return self._archive(url, notify, retry)
            else:
                if __debug__: log(f'retry limit reached for {self.name}.')
                raise error
        return False
