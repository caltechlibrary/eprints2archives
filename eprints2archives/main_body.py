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

from   concurrent.futures import ThreadPoolExecutor
from   humanize import intcomma
from   itertools import repeat
from   rich.progress import Progress, BarColumn, TextColumn
import sys
from   threading import Thread
import time
from   timeit import default_timer as timer

from .data_helpers import DATE_FORMAT, flatten, expand_range, parse_datetime
from .debug import log
from .eprints import *
from .exceptions import *
from .exit_codes import ExitCode
from .network import network_available, hostname
from .services import service_names, service_interfaces
from .ui import inform, warn, alert, alert_fatal
from .styled import styled


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
        self.records = None


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
        self.records = parsed_id_list(self.id_list)

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
            self.dest = service_interfaces()
        else:
            destination_list = []
            for destination in self.dest.split(','):
                service = service_by_name(destination)
                if service:
                    destination_list.append(service)
                else:
                    alert_fatal('Unknown destination service "{}"', destination)
                    raise CannotProceed(ExitCode.bad_arg)
            self.dest = destination_list

        text = 'EPrints server at ' + hostname(self.api_url)
        self.user, self.password, cancel = self.auth_handler.name_and_password(text)
        if cancel:
            raise UserCancelled


    def _do_main_work(self):
        '''Performs the core work of this program.'''

        inform('Doing initial checks ...')
        self._do_preflight_checks()

        server = hostname(self.api_url)
        inform('Asking {} for index of records ...', styled(server, ['orange']))
        index_xml = eprints_raw_index(self.api_url, self.user, self.password)
        if index_xml == None:
            text = 'Did not get a response from "{}"'.format(self.api_url)
            raise NoContent(text)
        if not self.records:
            self.records = eprints_records_list(index_xml)
        num_records = len(self.records)

        # Now we need to get the XML of individual EPrints records, to extract
        # the <official_url> value, and we want to do that only once rather
        # than separately inside each thread where they get sent to archiving
        # services.  This step could be broken up and done in multiple threads
        # here, but since the EPrints server is probably a single machine, it
        # hitting it in parallely would just increase the load on that single
        # machine.  So, this part is single-threaded and a potential bottleneck.
        # Time will tell if we need to do better here.
        eprints_urls = []
        with Progress('[progress.description]{task.description}', BarColumn(),
                      TextColumn('{task.fields[done]}/' + intcomma(num_records)),
                      refresh_per_second = 5) as progress:
            header = '[green]Getting individual records ...'
            task = progress.add_task(header, done = 0, total = num_records)
            for index, record in enumerate(self.records):
                if __debug__: log('getting XML for record #{}', record)
                xml = eprints_xml(record, self.api_url, self.user, self.password, True)
                url = eprints_official_url(xml)
                if url:
                    eprints_urls.append(url)
                else:
                    warn('Could not get official_url for record #{}', record)
                progress.update(task, advance = 1, done = index)

        inform('Sending {} EPrints {} to {} archiving service{}',
               intcomma(num_records), 'entries' if num_records > 1 else 'entry',
               len(self.dest), 's' if len(self.dest) > 1 else '')
        if self.lastmod:
            inform('Will only keep records modified after {}', self.lastmod_str)
        if self.status:
            inform('Will only keep records {} status {}',
                   'without' if self.status_negation else 'with',
                   fmt_statuses(self.status, self.status_negation))

        import pdb; pdb.set_trace()

        # Send the list of wanted articles to each service in parallel.
        with Progress('[progress.description]{task.description}', BarColumn(),
                      TextColumn('{task.fields[done]} sent', justify = 'right'),
                      refresh_per_second = 5) as progress:
            if __debug__: log('starting {} threads', self.threads)
            if self.threads == 1:
                # For 1 thread, avoid thread pool to make debugging easier.
                results = [self._send(d, progress) for d in self.dest]
            else:
                with ThreadPoolExecutor(max_workers = self.threads) as tpe:
                    results = list(tpe.map(self._send, iter(self.dest), repeat(progress)))


    def _send(self, service, progress):
        header = '[green]Sending to [{}]{} ...'.format(service.color, service.name)
        task = progress.add_task(header, done = 0, total = len(self.records))

            # Ask the service if it's there, and archive it if not.

            # Show some progress
            # progress.update(task, advance = 1, done = index)

            # Be nice to the server.
            # sleep(self.delay/1000)


        # for record in self.records:

        #     last_time = timer()
        #     try:
        #         output = service.result()
        #     except AuthFailure as ex:
        #         raise AuthFailure('Unable to use {}: {}', service, ex)
        #     except RateLimitExceeded as ex:
        #         time_passed = timer() - last_time
        #         if time_passed < 1/service.max_rate():
        #             warn('Pausing {} due to rate limits', service_name)
        #             time.sleep(1/service.max_rate() - time_passed)





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
