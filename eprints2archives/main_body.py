'''
main_body.py: main body logic for this application

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2018-2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from   humanize import intcomma
import sys
from   threading import Thread

from .data_helpers import DATE_FORMAT, flatten, expand_range, parse_datetime
from .debug import log
from .eprints import *
from .exceptions import *
from .exit_codes import ExitCode
from .network import network_available, hostname
from .services import KNOWN_SERVICES, services_list
from .ui import UI, inform, warn, alert, alert_fatal


# Class definitions.
# .............................................................................

class MainBody(Thread):
    '''Main body of Check It! implemented as a Python thread.'''

    def __init__(self, **kwargs):
        '''Initializes main body thread object but does not start the thread.'''
        Thread.__init__(self)

        # Assign parameters to self to make them available within this object.
        for key, value in kwargs.items():
            setattr(self, key, value)

        # We expose attribute "exception" that callers can use to find out if
        # the thread finished normally or with an exception.
        self.exception = None

        # Additional attributes we set later.
        self.user = None
        self.password = None
        self.wanted = None


    def run(self):
        '''Run the main body.'''
        # In normal operation, this method returns after things are done and
        # leaves it to the user to exit the application via the control GUI.
        # If exceptions occur, we capture the stack context for the caller.
        if __debug__: log('running MainBody thread')

        try:
            self._do_main_work()
            inform('Done.')
        except (KeyboardInterrupt, UserCancelled) as ex:
            if __debug__: log('got {} exception', type(ex).__name__)
            inform('User cancelled operation -- stopping.')
        except CannotProceed as ex:
            self.exception = (CannotProceed, ex)
            return
        except Exception as ex:
            if __debug__: log('exception in main body: {}', str(ex))
            self.exception = sys.exc_info()
            alert_fatal('Error occurred during execution', details = str(ex))
            return
        if __debug__: log('finished')


    def stop(self):
        '''Stop the main body thread.'''
        if __debug__: log('stopping main body thread')
        # Nothing to do for the current application.
        pass


    def _do_preflight_checks(self):
        '''Do error checks on the options given, and other prep work.'''

        if not network_available():
            alert_fatal('No network connection.')
            raise CannotProceed(ExitCode.no_net)

        if self.api_url is None:
            alert_fatal('Must provide an EPrints API URL.')
            raise CannotProceed(ExitCode.bad_arg)
        elif not self.api_url.startswith('http') or not self.api_url.find('//') > 0:
            alert_fatal('The given API URL does not appear to be a valid URL')
            raise CannotProceed(ExitCode.bad_arg)

        # The wanted list contains strings to avoid repeated conversions.
        self.wanted = parsed_id_list(self.id_list)

        if self.lastmod:
            try:
                self.lastmod = parse_datetime(self.lastmod)
                self.lastmod_str = self.lastmod.strftime(DATE_FORMAT)
                if __debug__: log('Parsed lastmod as {}', self.lastmod_str)
            except Exception as ex:
                alert_fatal('Unable to parse lastmod value: {}', str(ex))
                raise CannotProceed(ExitCode.bad_arg)

        # It's easier to use None as an indication of no restriction.
        if self.status == 'any':
            self.status = None
        elif self.status:
            self.status = self.status.split(',')
        self.status_negation = (self.status and self.status[0].startswith('^'))
        if self.status_negation:        # Remove the '^' if it's there.
            self.status[0] = self.status[0][1:]

        if self.dest == 'all':
            self.dest = services_list()
        else:
            self.dest = self.dest.split(',')
            for destination in self.dest:
                if destination not in KNOWN_SERVICES.keys():
                    alert_fatal('Unknown destination service "{}"', destination)
                    raise CannotProceed(ExitCode.bad_arg)

        text = 'EPrints server at ' + hostname(self.api_url)
        self.user, self.password, cancel = self.auth_handler.name_and_password(text)
        if cancel:
            raise UserCancelled


    def _do_main_work(self):
        '''Performs the core work of this program.'''

        inform('Doing initial checks')
        self._do_preflight_checks()

        inform('Asking server for list of available articles')
        raw_list = eprints_raw_index(self.api_url, self.user, self.password)
        if raw_list == None:
            text = 'Did not get a response from server "{}"'.format(self.api_url)
            raise NoContent(text)
        if not self.wanted:
            inform('Fetching records list from {}', self.api_url)
            self.wanted = eprints_records_list(raw_list)

        inform('Beginning to process {} EPrints {}', intcomma(len(self.wanted)),
               'entries' if len(self.wanted) > 1 else 'entry')
        if self.lastmod:
            inform('Will only keep records modified after {}', self.lastmod_str)
        if self.status:
            inform('Will only keep records {} status {}',
                   'without' if self.status_negation else 'with',
                   fmt_statuses(self.status, self.status_negation))





# Helper functions.
# ......................................................................

def parsed_id_list(id_list):
    if id_list is None:
        return []

    # If it's a single digit, asssume it's not a file and return the number.
    if id_list.isdigit():
        return [id_list]

    # Things get trickier because anything else could be (however improbably)
    # a file name.  So use a process of elimination: try to see if a file by
    # that name exists, and if it doesn't, parse the argument as numbers.
    candidate = id_list
    if not path.isabs(candidate):
        candidate = path.realpath(path.join(os.getcwd(), candidate))
    if path.exists(candidate):
        if not readable(candidate):
            raise RuntimeError('File not readable: {}'.format(candidate))
        with open(candidate, 'r', encoding = 'utf-8-sig') as file:
            if __debug__: log('Reading {}'.format(candidate))
            return [id.strip() for id in file.readlines()]

    # Didn't find a file.  Try to parse as multiple numbers.
    if ',' not in id_list and '-' not in id_list:
        raise ValueError('Unable to understand list of record identifiers')
    return flatten(expand_range(x) for x in id_list.split(','))


def fmt_statuses(status_list, negated):
    as_list = ['"' + x + '"' for x in status_list]
    if len(as_list) > 1:
        and_or = ' or ' if negated else ' and '
        return ', '.join(as_list[:-1]) + and_or + as_list[-1]
    else:
        return as_list[0]
