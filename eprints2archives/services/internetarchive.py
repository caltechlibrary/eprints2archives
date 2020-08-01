from   humanize import intcomma
import requests
from   time import sleep

from ..debug import log
from ..exceptions import *
from ..network import net
from ..ui import warn

from .base import Service
from .timemap import timemap_as_dict


# Constants.
# .............................................................................

_MAX_RETRIES = 3
'''Maximum number of times we back off and try again.'''

_RETRY_SLEEP_TIME = 60 * 60
'''Time in seconds we pause if we get repeated errors.  This pause is on top
of the maximum time reached after exponential back-off by our underlying
network code, and is used to pause before the whole scheme is retried again.
This needs to be a long time because if we invoke our own retry loop, it means
we've already been trying for a considerable amount of time and the root cause
may be significant.'''


# Classes.
# .............................................................................

class InternetArchive(Service):
    label = 'internetarchive'
    name  = 'Internet Archive'
    color = 'white'

    # Public methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def save(self, url, force = False):
        '''Ask the service to save "url".'''
        existing = self._saved_copies(url)
        if existing:
            if 'mementos' in existing and 'list' in existing['mementos']:
                num_existing = len(existing['mementos']['list'])
                if __debug__: log(f'there are {num_existing} mementos for {url}')
            else:
                raise InternalError('unexpected TimeMap format from IA')
            if force:
                added = self._archive(url)
                return (added, num_existing)
            else:
                return (False, num_existing)
        else:
            if __debug__: log(f'IA returned no mementos for {url}')
            added = self._archive(url)
            return (added, 0)


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _uniform(self, url):
        return str(url).strip().replace(' ', '_')


    def _saved_copies(self, url):
        '''Returns a timemap, in the form of a dict.'''
        if __debug__: log(f'asking {self.name} for info about {url}')

        action_url = 'https://web.archive.org/web/timemap/link/' + self._uniform(url)
        (response, error) = net('get', action_url)
        if not error and response:
            if __debug__: log('converting TimeMap to dict')
            return timemap_as_dict(response.text, skip_errors = True)
        elif isinstance(error, NoContent):
            return {}
        else:
            raise error


    def _archive(self, url, retry = 0):
        if __debug__: log(f'asking {self.name} to save {url}')
        payload = {'url': url, 'capture_all': 'on'}
        action_url = 'https://web.archive.org/save/' + self._uniform(url)
        (response, error) = net('post', action_url, data = payload)
        if not error:
            if __debug__: log('save request returned normally')
            return True
        else:
            if __debug__: log(f'save request resulted in an error: {str(error)}')
            # Our underlying net(...) function will retry automatically in
            # the face of problems, but will give up eventually.  Sometimes
            # IA errors are temporary, so we pause for even longer & retry.
            retry += 1
            retries_left = _MAX_RETRIES - retry
            if __debug__: log(f'we have {retries_left} retries left')
            if retries_left > 0:
                warn('Encountered repeated errors from {} -- pausing for {}s',
                     self.name, intcomma(_RETRY_SLEEP_TIME))
                sleep(_RETRY_SLEEP_TIME)
                return self._archive(url, retry)
            else:
                if __debug__: log(f'retry limit reached for {self.name}.')
                raise error
