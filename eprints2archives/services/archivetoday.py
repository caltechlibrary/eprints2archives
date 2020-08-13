'''
archivetoday.py: interface to Archive.Today.

Much of the basic algorithm for interacting with Archive.Today was initially
taken from ArchiveNow (https://github.com/oduwsdl/archivenow), from the
Web Science and Digital Libraries Research Group at Old Dominion University.
The ArchiveNow source file used was the following, and it had commit hash
b4e88b2 at the time of this writing (2020-08-06):

https://github.com/oduwsdl/archivenow/blob/master/archivenow/handlers/is_handler.py

The authors & contributors of that specific code were (again at the time of
this writing) Mohamed Aturban, Shawn M. Jones, "veloute", and "evil-wayback".
The license for ArchiveNow at the time timemap.py was copied was the MIT license,
https://github.com/oduwsdl/archivenow/blob/master/LICENSE

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

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
from .upload_status import Status


# Constants.
# .............................................................................

# Archive.today (= Archive.is and other names) deliberately uses multiple
# domains.  The author explained the situation in a blog posting of 2020-08-01
# (https://blog.archive.today/post/625241784047550464):
#
# """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
# No single domain is reliable and I have no means to enforce control on
# each domain.
#
# * archive.today - threatened with confiscation
# http://blog.archive.today/post/116913927371, also a troll attack caused
# service interruption https://blog.archive.today/post/138982909006
#
# * archive.is - threatened with confiscation
# https://twitter.com/archiveis/status/1081276424781287427, asked not to use
# “archive.IS” for branding (that’s why you see “archive.TODAY” in the top-left
# corner; although many people remembered it as “archive.IS” and refer it so)
#
# * archive.fo - threatened with confiscation
# https://twitter.com/archiveis/status/1188222460598116353
#
# * archive.li - attacked by trolls impersonating police, caused few days
# service interruption https://twitter.com/archiveis/status/956025540028268547
#
# * archive.ec - attacked by trolls causing service interruption and finally
# lost https://twitter.com/archiveis/status/1093608363647291393
#
# * archive.vn - ok so far
#
# * archive.ph - ok so far
#
# * archive.md - ok so far
#
# * a nice domain unrelated to archive - one day whois started showing
# someone’s else information and the registrar did not response, the
# domain was lost
#
# """""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
#
# A list of the URLs is available from the Wikipedia page for Archive.Today:
# https://en.wikipedia.org/wiki/Archive.today

_HOSTS = ['archive.li', 'archive.vn','archive.fo', 'archive.md', 'archive.ph',
          'archive.today', 'archive.is']
'''Alternative hosts by which Archive.Today is known.'''

_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.116 Safari/537.36"
'''User agent we pretend to be when contacting Archive.Today.'''

_MAX_RETRIES = 8
'''Maximum number of times we retry before we give up.'''

_RETRY_SLEEP = 60
'''Time in seconds we pause if we get repeated errors.  This pause is on top
of the maximum time reached after exponential back-off by our underlying
network code, and is used to pause before the whole scheme is retried again.
This needs to be a long time because if we invoke our own retry loop, it means
we've already been trying for a considerable amount of time and the root cause
may be significant.'''

_RATE_LIMIT_SLEEP = 300
'''Time in seconds we pause if we hit the rate limit.  This is handled
separately from error conditions.'''


# Classes.
# .............................................................................

class ArchiveToday(Service):
    label = 'archive.today'
    name = 'Archive.today'
    color = 'yellow'

    # Public methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def save(self, url, notify, force = False):
        '''Ask the service to save "url".'''
        if force:
            # If we're forcing a send, we don't care how many copies exist.
            added = self._archive(url, notify)
            return (added, -1)

        existing = self._saved_copies(url)
        if existing:
            if 'mementos' in existing and 'list' in existing['mementos']:
                num_existing = len(existing['mementos']['list'])
                if __debug__: log(f'there are {num_existing} mementos for {url}')
                return (False, num_existing)
            else:
                raise InternalError(f'Unexpected TimeMap format from {self.name}')
        else:
            if __debug__: log(f'{self.name} returned no mementos for {url}')
            added = self._archive(url, notify)
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


    def _archive(self, url, notify, retry = 0):

        # Basic idea and algorithm taken from ArchiveNow.  We iterate over the
        # various domain names that Archive.today uses, because some of them
        # stop responding and others start responding, and we never know which
        # one will work.  If you try to use /submit on archive.today itself,
        # you get an error about too many redirects.  (Not sure if that's
        # deliberate on their part or just a side-effect of what they're doing
        # with their hosts.

        session = requests.Session()
        headers = {"User-Agent": _USER_AGENT}
        archive_host = None
        for host in _HOSTS:
            # headers['host'] = host
            test_url = f'https://{host}/'
            (response, error) = net('get', test_url, session = session, headers = headers)
            if not error:
                archive_host = host
                break
            else:
                raise error
        if not archive_host:
            raise ServiceFailure(f'None of the {self.name} servers are responding')
            return False

        try:
            html = str(response.content)
            # Gnarly line of code from ArchiveNow.
            sid = html.split('name="submitid', 1)[1].split('value="', 1)[1].split('"', 1)[0]
        except:
            raise InternalError(f'Unable to parse {self.name} page')

        action_url = f'https://{archive_host}/submit/'
        headers['host'] = archive_host
        # The order of the content of the post body matters to Archive.today.
        payload = OrderedDict({'submitid': sid, 'url': url})
        (response, error) = net('post', action_url, session = session,
                                handle_rate = False, headers = headers, data = payload)

        if not error:
            if 'Refresh' in response.headers:
                try:
                    saved_url = str(response.headers['Refresh']).split(';url=')[1]
                    if __debug__: log(f'{self.name} saved URL as {saved_url}')
                    return True
                except:
                    raise InternalError('Unexpected response from {self.name}')
            elif 'Location' in response.headers:
                saved_url = response.headers['Location']
                if __debug__: log(f'{self.name} saved URL as {saved_url}')
                return True
            else:
                for h in response.history:
                    if 'Location' in h.headers:
                        saved_url = h.headers['Location']
                        if __debug__: log(f'{self.name} saved URL as {saved_url}')
                        return True
            raise InternalError(f'{self.name} returned unexpected response')
        elif not response:
            # User cancellation can cause this.
            if __debug__: log(f'got {error} from net() and no response -- raising it')
            raise error
        else:
            # Archive.today doesn't return code 429 when you hit the rate limit
            # and instead throws code 503.  See author's posting of 2020-08-04:
            # https://blog.archive.today/post/625519838592417792
            if response.status_code == 503:
                if __debug__: log(f'{self.name} rate limit; pausing {_RATE_LIMIT_SLEEP}s')
                notify(Status.PAUSED_RATE)
                sleep(_RATE_LIMIT_SLEEP)
                notify(Status.RUNNING)
                return self._archive(url, notify)

            # Our underlying net(...) function will retry automatically for
            # some recognizable temporary problems.  Others, we handle here.
            if __debug__: log(f'save request resulted in an error: {str(error)}')
            retry += 1
            retries_left = _MAX_RETRIES - retry
            if __debug__: log(f'we have {retries_left} retries left')
            if retries_left > 0:
                sleeptime = _RETRY_SLEEP * pow(retry, 2)
                warn(f'Got error from {self.name}; pausing for {intcomma(sleeptime)}s.')
                notify(Status.PAUSED_ERROR)
                sleep(sleeptime)
                notify(Status.RUNNING)
                return self._archive(url, notify, retry)
            else:
                if __debug__: log(f'retry limit reached for {self.name}.')
                raise error
        return False
