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
from   pydash import flatten
from   rich.progress import Progress, BarColumn, TextColumn
import sys
from   threading import Thread
import time
from   timeit import default_timer as timer
import validators.url

from .data_helpers import DATE_FORMAT, slice, expand_range, parse_datetime
from .debug import log
from .eprints import *
from .exceptions import *
from .exit_codes import ExitCode
from .network import network_available, hostname
from .services import service_names, service_interfaces, service_by_name
from .ui import inform, warn, alert, alert_fatal
from .styled import styled


# Constants.
# .............................................................................

_PARALLEL_THRESHOLD = 2


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


    def _do_preflight(self):
        '''Do error checks on the options given, and other prep work.'''

        if not network_available():
            alert_fatal('No network connection.')
            raise CannotProceed(ExitCode.no_net)

        if self.api_url is None:
            alert_fatal('Must provide an EPrints API URL.')
            raise CannotProceed(ExitCode.bad_arg)
        elif not validators.url(self.api_url):
            alert_fatal('The given API URL does not appear to be a valid URL')
            raise CannotProceed(ExitCode.bad_arg)

        # The id's are stored as strings, not ints, to avoid repeated conversion
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

        self._do_preflight()

        server = EPrintsServer(self.api_url, self.user, self.password)
        wanted = self.wanted

        if not wanted:
            inform('Asking {} for index ...', styled(server, ['orange']))
            wanted = server.index()
            if len(wanted) == 0:
                raise NoContent('Received empty list from {}'.format(server))

        # We switch strategies depending on what we need to get.  If we're
        # not going to filter by lastmod or status, then we don't need to get
        # more than the official_url field for each record.  We can ask the
        # server for that directly, and that saves bandwidth and is a little
        # faster.  Conversely, if we need to filter by any value, it takes
        # less time to get the XML of every record rather than ask for 2 or
        # more field values separately, because each EPrint lookup is slow
        # and doing 2 or more lookups per record is slower than doing one
        # lookup (even if it entails downloading more data per record).

        skipped = []
        if not self.lastmod and not self.status:
            urls = self._urls_for_ids(wanted, server, self.threads, self.errors_ok)
        else:
            records = self._records_for_ids(wanted, server, self.threads, self.errors_ok)
            if self.lastmod:
                subset = []
                for r in records:
                    value = server.record_value(r, 'lastmod', self.errors_ok)
                    timestamp = parse_datetime(value)
                    if timestamp < self.lastmod:
                        if __debug__: log('{} lastmod {} -- skipping', r, timestamp)
                        skipped.append(r)
                    else:
                        subset.append(r)
                inform('{} records were modified after {}', len(subset), self.lastmod_str)
                records = subset
            if self.status:
                subset = []
                for r in records:
                    status = server.record_value(r, 'eprint_status', self.errors_ok)
                    if ((not self.status_negation and status not in self.status)
                        or (self.status_negation and status in self.status)):
                        skipped.append(r)
                    else:
                        subset.append(r)
                records = subset
                inform('{} records are {} status {}', len(subset),
                       'without' if self.status_negation else 'with',
                       fmt_statuses(self.status, self.status_negation))
            urls = [server.record_value(r, 'official_url', self.errors_ok) for r in records]

        num_urls = len(urls)
        if num_urls == 0:
            warn('List of URLs is empty -- nothing to archive')
            return

        if len(skipped) > 0:
            inform('Skipping a total of {} records due to filtering', len(skipped))
        inform('Sending {} EPrints {} to {} archiving service{}',
               intcomma(num_urls), 'entries' if num_urls > 1 else 'entry',
               len(self.dest), 's' if len(self.dest) > 1 else '')

        self._send(urls)


    def _urls_for_ids(self, wanted, server, threads, missing_ok):
        def urls_for_records(record_list, update_progress):
            num_records = len(record_list)
            results = []
            for index, record in enumerate(record_list):
                if __debug__: log('getting official_url for record #{}', record)
                url = server.record_value(record, 'official_url', missing_ok)
                if url:
                    results.append(url)
                elif not missing_ok:
                    warn('Could not get official_url for record #{}', record)
                update_progress()
            return results

        return self._gather(urls_for_records, wanted, threads, server, 'URLs')


    def _records_for_ids(self, wanted, server, threads, missing_ok):
        def xml_for_records(record_list, update_progress):
            num_records = len(record_list)
            results = []
            for index, record in enumerate(record_list):
                if __debug__: log('getting official_url for record #{}', record)
                xml = server.record_xml(record, missing_ok)
                if xml is not None:
                    results.append(xml)
                elif not missing_ok:
                    warn('Could not get XML for record #{}', record)
                update_progress()
            return results

        return self._gather(xml_for_records, wanted, threads, server, 'records')


    def _gather(self, func, wanted, threads, server, text):
        num_wanted = len(wanted)
        with Progress('[progress.description]{task.description}',
                      BarColumn(bar_width = None),
                      TextColumn('{task.completed}/' + intcomma(num_wanted)),
                      refresh_per_second = 5) as progress:
            # Wrap up the progress bar updater as a lambda that we can pass down.
            styled_name = '[spring_green1]{}[/spring_green1]'.format(server)
            header  = '[green]Getting EPrints {} from {} ...'.format(text, styled_name)
            bar = progress.add_task(header, done = 0, total = num_wanted)
            update_progress = lambda: progress.update(bar, advance = 1)

            # If we want only a few records, don't bother going parallel.
            if threads == 1 or num_wanted <= (threads * _PARALLEL_THRESHOLD):
                return func(wanted, update_progress)

            # In the parallel case, we'll get a list of lists, which we flatten.
            num_threads = min(num_wanted, threads)
            if __debug__: log('using {} threads to gather records', num_threads)
            with ThreadPoolExecutor(max_workers = num_threads) as e:
                # Don't use TPE map() b/c it doesn't bubble up exceptions.
                futures = []
                for group in slice(wanted, num_threads):
                    futures.append(e.submit(func, group, update_progress))
                return flatten(f.result() for f in futures)


    def _send(self, urls_to_send):
        num_urls = len(urls_to_send)
        if self.force:
            inform('Force option given ⟹  adding URLs even if archives have copies')
        with Progress('[progress.description]{task.description}',
                      BarColumn(bar_width = None),
                      TextColumn('{task.fields[added]} added/{task.fields[skipped]} skipped'),
                      refresh_per_second = 5) as progress:

            def send_to_service(dest, pbar):
                header  = '[green]Sending URLs to [{}]{}[/{}]...'.format(
                    dest.color, dest.name, dest.color)
                added = skipped = 0
                bar = pbar.add_task(header, total = num_urls, added = 0, skipped = 0)
                for index, url in enumerate(urls_to_send):
                    if __debug__: log('next for {}: {}', dest, url)
                    (result, num_existing) = dest.save(url, self.force)
                    if __debug__: log('result = {}', result)
                    added += int(result is True)
                    skipped += int(result is False)
                    pbar.update(bar, advance = 1, added = added, skipped = skipped)
                    time.sleep(self.delay/1000)

            if __debug__: log('starting {} threads', self.threads)
            if self.threads == 1:
                # For 1 thread, avoid thread pool to make debugging easier.
                results = [send_to_service(d, progress) for d in self.dest]
            else:
                # Send the list of wanted articles to each service in parallel.
                num_threads = min(len(self.dest), self.threads)
                with ThreadPoolExecutor(max_workers = num_threads) as e:
                    # Don't use TPE map() b/c it doesn't bubble up exceptions.
                    futures = []
                    for service in self.dest:
                        futures.append(e.submit(send_to_service, service, progress))
                    results = [f.result() for f in futures]


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
    return list(flatten(expand_range(x) for x in id_list.split(',')))


def fmt_statuses(status_list, negated):
    as_list = ['"' + x + '"' for x in status_list]
    if len(as_list) > 1:
        and_or = ' or ' if negated else ' and '
        return ', '.join(as_list[:-1]) + and_or + as_list[-1]
    else:
        return as_list[0]
