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

from .data_helpers import DATE_FORMAT, slice, expand_range, parse_datetime, plural
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
            if __debug__: log(f'got {type(ex).__name__} exception')
            inform('User cancelled operation -- stopping.')
        except CannotProceed as ex:
            self.exception = (CannotProceed, ex)
            return
        except Exception as ex:
            if __debug__: log(f'exception in main body: {str(ex)}')
            self.exception = sys.exc_info()
            alert_fatal(f'Error occurred during execution:', details = str(ex))
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
        self.wanted_list = parsed_id_list(self.id_list)

        if self.lastmod:
            try:
                self.lastmod = parse_datetime(self.lastmod)
                self.lastmod_str = self.lastmod.strftime(DATE_FORMAT)
                if __debug__: log(f'parsed lastmod as {self.lastmod_str}')
            except Exception as ex:
                alert_fatal(f'Unable to parse lastmod value: {str(ex)}')
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

        text = 'Login for EPrints server at ' + hostname(self.api_url)
        self.user, self.password, cancel = self.auth_handler.name_and_password(text)
        if cancel:
            raise UserCancelled


    def _do_main_work(self):
        '''Performs the core work of this program.'''

        self._do_preflight()

        server = EPrintServer(self.api_url, self.user, self.password)

        inform('Getting EPrints index from {} ...', styled(server, ['SpringGreen']))
        available = server.index()
        if not available:
            raise NoContent(f'Received empty list from {server}.')

        # If the user wants specific records, check which ones actually exist.
        if self.wanted_list:
            nonexistent = list(set(self.wanted_list) - set(available))
            if nonexistent and not self.errors_ok:
                raise ValueError(f'{intcomma(len(nonexistent))} of the requested'
                                 + ' records do not exist on the server.')
            elif nonexistent:
                warn(f"Records {self.id_list} were specified, but the following"
                     + " don't exist and will be skipped: "
                     + ', '.join(str(x) for x in sorted(nonexistent, key = int)) + '.')
            wanted = sorted(list(set(self.wanted_list) - set(nonexistent)), key = int)
        else:
            wanted = available

        # We switch strategies for getting official_url depending on filters.
        # If we're not filtering by lastmod or status, then we don't need to
        # get more than the official_url field for each record.  We can ask the
        # server for that directly, and that saves bandwidth and is a little
        # faster.  Conversely, if we need to filter by any value, it takes
        # less time to get the XML of every record rather than ask for 2 or
        # more field values separately, because each such EPrint fetch is slow
        # and doing 2 or more lookups per record is slower than doing one
        # lookup (even if that one entails downloading more data per record).

        records = []
        if not self.lastmod and not self.status:
            official_url = lambda r: server.eprint_value(r, 'official_url')
            urls = self._eprints(official_url, wanted, server, "official_url values")
        else:
            skipped = []
            for r in self._eprints(server.eprint_xml, wanted, server, 'XML records'):
                eprintid = server.eprint_value(r, 'eprintid')
                if self.lastmod:
                    modtime = server.eprint_value(r, 'lastmod')
                    if modtime and parse_datetime(modtime) >= self.lastmod:
                        records.append(r)
                    else:
                        if __debug__: log(f'{eprintid} lastmod == {modtime} -- skipping')
                        skipped.append(r)
                    continue
                if self.status:
                    status = server.eprint_value(r, 'eprint_status')
                    if status and self._status_acceptable(status):
                        records.append(r)
                    else:
                        if __debug__: log(f'{eprintid} status == {status} -- skipping')
                        skipped.append(r)
            if len(skipped) > 0:
                inform(f'Skipping {len(skipped)} records due to filtering.')
            urls = [server.eprint_value(r, 'official_url') for r in records]

        # Get the normal URLs
        inform('Constructing list of valid EPrint URLs ...')
        urls += [server.eprint_id_url(r) for r in (wanted or records)]
        urls += [server.eprint_page_url(r) for r in (wanted or records)]
        urls = list(filter(None, urls))

        num_urls = len(urls)
        if num_urls == 0:
            warn('List of URLs is empty -- nothing to archive')
            return

        inform(f'Sending {intcomma(num_urls)} {plural("URL", urls)}'
               + f' to {len(self.dest)} {plural("archiving service", self.dest)}.')
        if self.report_file:
            inform(f'A report of the results will be written to "{self.report_file}"')

        self._send(urls)


    def _eprints(self, value_function, items, server, description):

        # Helper function: body of loop that is executed in all cases.
        def loop(item_list, update_progress):
            results = []
            for index, item in enumerate(item_list):
                if __debug__: log(f'getting data for {item}')
                try:
                    data = value_function(item)
                    if data is not None:
                        results.append(data)
                    elif not self.errors_ok:
                        warn(f'Received no data for {item}')
                except Exception as ex:
                    if isinstance(ex, NoContent) and self.errors_ok:
                        warn(f'Server has no content for {item}')
                    elif isinstance(ex, AuthenticationFailure) and self.errors_ok:
                        warn(f'Authentication failure trying to get data for {item}')
                    else:
                        warn(f'Unable to get data for {item}')
                update_progress()
            return results

        # Start of actual procedure.
        num_items = len(items)
        with Progress('[progress.description]{task.description}',
                      BarColumn(bar_width = None),
                      TextColumn('{task.completed}/' + intcomma(num_items)),
                      refresh_per_second = 5) as progress:
            # Wrap up the progress bar updater as a lambda that we can pass down.
            server_name = f'[spring_green1]{server}[/spring_green1]'
            header  = f'[green]Getting {description} from {server_name} ...'
            bar = progress.add_task(header, done = 0, total = num_items)
            update_progress = lambda: progress.update(bar, advance = 1)

            # If the number of items is too small, don't bother going parallel.
            if self.threads == 1 or num_items <= (self.threads * _PARALLEL_THRESHOLD):
                return loop(items, update_progress)

            num_threads = min(num_items, self.threads)
            if __debug__: log(f'using {num_threads} threads to gather records')
            with ThreadPoolExecutor(max_workers = num_threads) as e:
                # Don't use TPE map() b/c it doesn't bubble up exceptions.
                futures = []
                for sublist in slice(items, num_threads):
                    futures.append(e.submit(loop, sublist, update_progress))
                # We get a list of lists, so flatten it before returning.
                return flatten(f.result() for f in futures)


    def _send(self, urls_to_send):
        num_urls = len(urls_to_send)
        if self.force:
            inform('Force option given ⟹  adding URLs even if archives have copies.')
        with Progress('[progress.description]{task.description}',
                      BarColumn(bar_width = None),
                      TextColumn('{task.fields[added]} added/{task.fields[skipped]} skipped'),
                      refresh_per_second = 5) as progress:

            def send_to_service(dest, pbar):
                header  = f'[green]Sending URLs to [{dest.color}]{dest.name}[/{dest.color}] ...'
                added = skipped = 0
                bar = pbar.add_task(header, total = num_urls, added = 0, skipped = 0)
                for index, url in enumerate(urls_to_send):
                    if __debug__: log(f'next for {dest}: {url}')
                    (result, num_existing) = dest.save(url, self.force)
                    if __debug__: log(f'result = {result}')
                    added += int(result is True)
                    skipped += int(result is False)
                    pbar.update(bar, advance = 1, added = added, skipped = skipped)

            if __debug__: log(f'starting {self.threads} threads')
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


    def _status_acceptable(self, status):
        return ((not self.status_negation and status in self.status)
                or (self.status_negation and status not in self.status))


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
            raise RuntimeError(f'File not readable: {candidate}')
        with open(candidate, 'r', encoding = 'utf-8-sig') as file:
            if __debug__: log(f'reading {candidate}')
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
