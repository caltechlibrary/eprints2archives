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
import re
from   rich.progress import Progress, BarColumn, TextColumn
import sys
from   threading import Thread
import time
from   timeit import default_timer as timer
import validators.url

from .data_helpers import DATE_FORMAT, slice, expand_range, plural
from .data_helpers import timestamp, parse_datetime
from .debug import log
from .eprints import *
from .exceptions import *
from .exit_codes import ExitCode
from .files import writable
from .network import network_available, hostname, netloc
from .services import service_names, service_interfaces, service_by_name
from .ui import inform, warn, alert, alert_fatal
from .styled import styled

from .services.upload_status import Status


# Constants.
# .............................................................................

_PARALLEL_THRESHOLD = 2


# Class definitions.
# .............................................................................

class MainBody(Thread):
    '''Main body of eprints2archives implemented as a Python thread.'''

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
            self._do_preflight()
            self._do_main_work()
            inform('Done.')
        except (KeyboardInterrupt, UserCancelled) as ex:
            if __debug__: log(f'got {type(ex).__name__}')
            inform('User cancelled operation -- stopping.')
        except CannotProceed as ex:
            if __debug__: log(f'got CannotProceed')
            self.exception = (CannotProceed, ex)
        except Exception as ex:
            if __debug__: log(f'exception in main body: {str(ex)}')
            self.exception = sys.exc_info()
            alert_fatal(f'Error occurred during execution:', details = str(ex))
        if __debug__: log('finished MainBody')


    def stop(self):
        '''Stop the main body thread.'''
        if __debug__: log('stopping main body thread')
        # Nothing to do for the current application.
        pass


    def _do_preflight(self):
        '''Check the option values given by the user, and do other prep.'''

        if not network_available():
            alert_fatal('No network connection.')
            raise CannotProceed(ExitCode.no_net)

        if self.api_url is None:
            alert_fatal('Must provide an EPrints API URL.')
            raise CannotProceed(ExitCode.bad_arg)
        elif not validators.url(self.api_url):
            alert_fatal('The given API URL does not appear to be a valid URL')
            raise CannotProceed(ExitCode.bad_arg)

        if self.lastmod:
            try:
                self.lastmod = parse_datetime(self.lastmod)
                self.lastmod_str = self.lastmod.strftime(DATE_FORMAT)
                if __debug__: log(f'parsed lastmod as {self.lastmod_str}')
            except Exception as ex:
                alert_fatal(f'Unable to parse lastmod value: {str(ex)}')
                raise CannotProceed(ExitCode.bad_arg)

        # It's easier to use None as an indication of no restriction (= 'any').
        if self.status:
            self.status = None if self.status == 'any' else re.split('(\W)', self.status)

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

        server = netloc(self.api_url)
        self.user, self.password, cancel = self.auth_handler.credentials(server)
        if cancel:
            raise UserCancelled

        # The id's are stored as strings, not ints, to avoid repeated conversion
        self.wanted_list = parsed_id_list(self.id_list)

        if self.report_file:
            if writable(self.report_file):
                inform(f'A report will be written to "{self.report_file}"')
                self._report(f'eprints2archives starting {timestamp()}.', True)
            else:
                alert_fatal(f'Cannot write to file "{self.report_file}"')
                raise CannotProceed(ExitCode.file_error)


    def _do_main_work(self):
        '''Performs the core work of this program.'''

        server = EPrintServer(self.api_url, self.user, self.password)

        inform('Getting full EPrints index from {} ...', styled(server, ['SpringGreen']))
        available = server.index()
        if not available:
            raise NoContent(f'Received empty list from {server}.')
        self._report(f'EPrints server at {self.api_url} has {len(available)} records.')

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
            self._report(f'User-supplied list of identifiers has {len(wanted)} items in it.')
        else:
            wanted = available

        # The basic URLs for EPrint pages can be constructed without doing
        # any record lookups -- all you need is id numbers from the index.
        # Some sites like Caltech use an additional field, <official_url>,
        # that DOES require a database lookup, but we can't know if a site
        # uses official_url until we try it, and we can't be sure every
        # record has a value, so we have to try to get official_url for all
        # records.  If we're not filtering by lastmod or status, then it's
        # faster to do direct lookups of <official_url>; conversely, if we
        # need lastmod or status values, it takes less time to just get the
        # XML of every record rather than ask for 2 or more field values
        # separately, because each such EPrint lookup is slow and doing 2 or
        # more lookups per record is slower than doing one XML fetch.

        records = []
        if not self.lastmod and not self.status:
            official_url = lambda r: server.eprint_value(r, 'official_url')
            urls = self._eprints(official_url, wanted, server, "<official_url>'s")
        else:
            skipped = []
            for r in self._eprints(server.eprint_xml, wanted, server, "record materials"):
                eprintid = server.eprint_value(r, 'eprintid')
                modtime  = server.eprint_value(r, 'lastmod')
                status   = server.eprint_value(r, 'eprint_status')
                if self.lastmod and modtime and parse_datetime(modtime) < self.lastmod:
                    if __debug__: log(f'{eprintid} lastmod == {modtime} -- skipping')
                    skipped.append(r)
                    continue
                if self.status and status and not self._status_acceptable(status):
                    if __debug__: log(f'{eprintid} status == {status} -- skipping')
                    skipped.append(r)
                    continue
                if __debug__: log(f'{eprintid} passed filter checks')
                records.append(r)
            if len(skipped) > 0:
                inform(f'Skipping {len(skipped)} records due to filtering.')
                self._report(f'Skipping {len(skipped)} records due to filtering.')
            if len(records) == 0:
                warn('Filtering left 0 records -- nothing left to do')
                return
            urls = [server.eprint_value(r, 'official_url') for r in records]

        # Next, construct "standard" URLs and check that they exist.  Do this
        # AFTER the steps above, because if we did any filtering, we may have
        # a much shorter list of records now than what we started with.

        urls += self._standard_urls(server, records or wanted)

        # Clean up any None's and make sure we have something left to do.
        urls = list(filter(None, urls))
        if not urls:
            alert('List of URLs is empty -- nothing to archive')
            return

        # If we get this far, we're doing it.
        inform(f'We have a total of {intcomma(len(urls))} {plural("URL", urls)}'
               + f' to send to {len(self.dest)} {plural("archive", self.dest)}.')
        self._send(urls)


    def _standard_urls(self, server, records_list):

        # Helper function: body of loop that is executed in all cases.
        def loop(item_list, update_progress):
            urls = []
            for r in item_list:
                if __debug__: log(f'getting URLs for {server.eprint_value(r, "eprintid")}')
                urls.append(server.eprint_id_url(r))
                urls.append(server.eprint_page_url(r))
                update_progress()
            return urls

        # Start of actual procedure.
        num_items = len(records_list)
        with Progress('[progress.description]{task.description}',
                      BarColumn(bar_width = None),
                      TextColumn('{task.completed}/' + intcomma(num_items)),
                      refresh_per_second = 5) as progress:
            # Wrap up the progress bar updater as a lambda that we can pass down.
            server_name = f'[spring_green1]{server}[/spring_green1]'
            header  = f'[green]Checking variant record URLs on {server_name} ...'
            bar = progress.add_task(header, total = num_items)
            update_progress = lambda: progress.update(bar, advance = 1)

            # If the number of items is too small, don't bother going parallel.
            if self.threads == 1 or num_items <= (self.threads * _PARALLEL_THRESHOLD):
                return loop(records_list, update_progress)

            num_threads = min(num_items, self.threads)
            if __debug__: log(f'using {num_threads} threads to gather records')
            with ThreadPoolExecutor(max_workers = num_threads) as e:
                # Don't use TPE map() b/c it doesn't bubble up exceptions.
                futures = []
                for sublist in slice(records_list, num_threads):
                    futures.append(e.submit(loop, sublist, update_progress))
                # We get a list of lists, so flatten it before returning.
                return flatten(f.result() for f in futures)


    def _eprints(self, value_function, items, server, description):

        # Helper function: body of loop that is executed in all cases.
        def loop(item_list, update_progress):
            results = []
            for item in item_list:
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
            header  = f'[green]Gathering {description} from {server_name} ...'
            bar = progress.add_task(header, total = num_items)
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
        '''Send the list of URLs to each web archiving service in parallel.'''

        num_urls = len(urls_to_send)
        num_dest = len(self.dest)
        self._report(f'{num_urls} URLs to be sent to {num_dest} {plural("service", num_dest)}.')
        if self.force:
            inform('Force option given ⟹  adding URLs even if archives have copies.')

        # Helper function: send urls to given service & use progress bar.
        def send_to_service(dest, pbar):
            num_added = 0
            num_skipped = 0
            description = activity(dest, Status.RUNNING)
            task = pbar.add_task(description, total = num_urls, added = 0, skipped = 0)
            notify = lambda s: pbar.update(task, description = activity(dest, s), refresh = True)
            for url in urls_to_send:
                if __debug__: log(f'next for {dest}: {url}')
                (added, num_existing) = dest.save(url, notify, self.force)
                added_str = "added" if added else "skipped"
                num_added += int(added)
                num_skipped += int(not added)
                pbar.update(task, advance = 1, added = num_added, skipped = num_skipped)
                self._report(f'{url} ➜ {dest.name}: {added_str}')

        # Start of actual procedure.
        bar  = BarColumn(bar_width = None)
        info = TextColumn('{task.fields[added]} added/{task.fields[skipped]} skipped')
        with Progress('[progress.description]{task.description}', bar, info) as pbar:
            if __debug__: log(f'starting {self.threads} threads')
            if self.threads == 1:
                # For 1 thread, avoid thread pool to make debugging easier.
                results = [send_to_service(service, pbar) for service in self.dest]
            else:
                num_threads = min(num_dest, self.threads)
                with ThreadPoolExecutor(max_workers = num_threads) as e:
                    # Don't use TPE map() b/c it doesn't bubble up exceptions.
                    futures = []
                    for service in self.dest:
                        futures.append(e.submit(send_to_service, service, pbar))
                    results = [f.result() for f in futures]
        self._report(f'Completed sending {num_urls} URLs.')


    def _status_acceptable(self, this_status):
        # The presence of '^' indicates negation, i.e., "not any of these".
        return ((not '^' in self.status and this_status in self.status)
                or ('^' in self.status and this_status not in self.status))


    def _report(self, text, overwrite = False):
        # Opening/closing the file for every write is inefficient, but our
        # network operations are slow, so I think this is not going to have
        # enough impact to be concerned
        if __debug__: log(text)
        with open(self.report_file, 'w' if overwrite else 'a') as f:
            f.write(text + os.linesep)


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


def activity(dest, status):
    name = f'[{dest.color}]{dest.name}[/{dest.color}]'
    if status == Status.RUNNING:
        return f'[green]Sending URLs to {name} ...         '
    elif status == Status.PAUSED_RATE:
        return f'[magenta3]Paused for rate limit {name} ... '
    elif status == Status.PAUSED_ERROR:
        return f'[orange1]Paused for error {name} ...      '
    else:
        import pdb; pdb.set_trace()
