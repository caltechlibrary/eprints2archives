from   collections import OrderedDict
from   humanize import intcomma
import requests
from   time import sleep
import urllib
from   urllib.parse import quote_plus, urlencode

from ..debug import log
from ..exceptions import *
from ..network import net, hostname
from ..ui import warn

from .base import Service
from .timemap import timemap_as_dict


# Constants.
# .............................................................................

_HOSTS = ['archive.li', 'archive.vn','archive.fo', 'archive.md', 'archive.ph',
          'archive.today', 'archive.is']

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"


# Classes.
# .............................................................................

class ArchiveToday(Service):
    label = 'archive.today'
    name = 'Archive.today'
    color = 'yellow'

    # Public methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def save(self, url, force = False):
        '''Ask the service to save "url".'''
        if force:
            # If we're forcing a send, we don't care how many there exist.
            added = self._archive(url)
            return (added, -1)

        existing = self._saved_copies(url)
        if existing:
            if 'mementos' in existing and 'list' in existing['mementos']:
                num_existing = len(existing['mementos']['list'])
                if __debug__: log(f'there are {num_existing} mementos for {url}')
                return (False, num_existing)
            else:
                raise InternalError('unexpected TimeMap format from Archive.Today')
        else:
            if __debug__: log(f'Archive.Today returned no mementos for {url}')
            added = self._archive(url)
            return (added, 0)


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _uniform(self, url):
        return str(url).strip().replace(' ', '_')


    def _saved_copies(self, url):
        '''Returns a timemap, in the form of a dict.'''

        session = requests.Session()
        headers = {"User-Agent": _USER_AGENT}
        action_url = 'https://archive.today/timemap/' + self._uniform(url)
        (response, error) = net('get', action_url, session = session, headers = headers)
        if not error and response:
            if __debug__: log('converting TimeMap to dict')
            return timemap_as_dict(response.text, skip_errors = True)
        elif isinstance(error, NoContent):
            return {}
        else:
            raise error


    def _archive(self, url, retry = 0):

        # Basic idea and algorithm taken from ArchiveNow.  We iterate over the
        # various domain names that Archive.Today uses, because some of them
        # stop responding and others start responding, and we never know which
        # one will work.  If you try to use /submit on archive.today itself,
        # you get an error about too many redirects.  (Not sure if that's
        # deliberate on their part or just a side-effect of what they're doing
        # with their hosts.

        session = requests.Session()
        headers = {"User-Agent": _USER_AGENT}
        archive_host = None
        response = None
        for host in _HOSTS:
            # headers['host'] = host
            test_url = f'https://{host}/'
            (response, error) = net('get', test_url, session = session, headers = headers)
            if not error:
                archive_host = host
                break
        if not archive_host:
            return False

        try:
            html = str(response.content)
            # Gnarly line of code from ArchiveNow.
            sid = html.split('name="submitid', 1)[1].split('value="', 1)[1].split('"', 1)[0]
        except:
            raise InternalError('Unable to parse Archive.Today page')

        action_url = f'https://{archive_host}/submit/'
        headers['host'] = archive_host
        # The order of the content of the post body matters to archive.today.
        # When wrong you get the error "invalid url: submitid". Use OrderedDict.
        payload = OrderedDict({'submitid': sid, 'url': url})
        (response, error) = net('post', action_url, session = session,
                                headers = headers, data = payload)

        if 'Refresh' in response.headers:
            try:
                saved_url = str(response.headers['Refresh']).split(';url=')[1]
                return True
            except:
                raise InternalError('Unexpected format of response header from Archive.Today')
        elif 'Location' in response.headers:
            saved_url = response.headers['Location']
            import pdb; pdb.set_trace()
        else:
            for h in response.history:
                if 'Location' in h.headers:
                    saved_url = h.headers['Location']
                    import pdb; pdb.set_trace()

        import pdb; pdb.set_trace()
        raise InternalError('Archive.Today returned unexpected response')
