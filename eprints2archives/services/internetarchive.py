import requests

from ..debug import log
from ..exceptions import *
from ..network import net

from .base import Service
from .timemap import timemap_as_dict


class SendToInternetArchive(Service):
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
                if __debug__: log('there are {} mementos for {}', num_existing, url)
            else:
                raise InternalError('unexpected TimeMap format from IA')
            if force:
                added = self._archive(url)
                return (added, num_existing)
            else:
                return (False, num_existing)
        else:
            added = self._archive(url)
            return (added, 0)


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _uniform(self, url):
        return str(url).strip().replace(' ', '_')


    def _saved_copies(self, url):
        '''Returns a timemap, in the form of a dict.'''
        if __debug__: log('asking {} for info about {}', self.name, url)

        action_url = 'https://web.archive.org/web/timemap/link/' + self._uniform(url)
        (response, error) = net('get', action_url)
        if not error and response:
            if __debug__: log('converting TimeMap to dict')
            return timemap_as_dict(response.text, skip_errors = True)
        elif isinstance(error, NoContent):
            return {}
        else:
            raise error


    def _archive(self, url):
        if __debug__: log('asking {} to save {}', self.name, url)
        payload = {'url': url, 'capture_all': 'on'}
        action_url = 'https://web.archive.org/save/' + self._uniform(url)
        (response, error) = net('post', action_url, data = payload)
        if not error:
            if __debug__: log('save request returned normally')
            return True
        else:
            import pdb; pdb.set_trace()
            if __debug__: log('save request resulted in an error: {}', str(error))
            raise error
