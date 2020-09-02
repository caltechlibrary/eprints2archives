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
import validators.url

from .data_helpers import DATE_FORMAT, slice, expand_range, plural
from .data_helpers import timestamp, parse_datetime
from .debug import log
from .eprints import *
from .exceptions import *
from .exit_codes import ExitCode
from .interruptions import interrupted, raise_for_interrupts
from .files import writable
from .network import network_available, hostname, scheme, netloc
from .services import ServiceStatus, service_names, service_interfaces, service_by_name
from .ui import inform, warn, alert, alert_fatal


# Constants.
# .............................................................................

_PARALLEL_THRESHOLD = 2

_BAR = BarColumn(bar_width = None)
'''All our progress bars use the same kind of column.'''


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

        # An unfortunate feature of Python's thread handling is that threads
        # don't get interrupt signals: if the user hits ^C, the parent thread
        # has to do something to interrupt the child threads deliberately.
        # We can't do that unless we keep a pointer to the executor and share
        # it between methods in this class.  Thus, the need for the following:
        self._executor = None
        self._futures = []


    def run(self):
        '''Run the main body.'''
        # In normal operation, this method returns after things are done and
        # leaves it to the user to exit the application via the control GUI.
        # If exceptions occur, we capture the stack context for the caller.
        if __debug__: log('running MainBody thread')

        try:
            self._do_preflight()
            self._do_main_work()
        except (KeyboardInterrupt, UserCancelled) as ex:
            if __debug__: log(f'got {type(ex).__name__}')
            self._report('Interrupted')
            self.exception = ex
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
        if self._executor:
            if __debug__: log('cancelling futures & shutting down executor')
            for f in self._futures:
                f.cancel()
            self._executor.shutdown(wait = False)
        else:
            if __debug__: log('no thread pool threads running')


    def _do_preflight(self):
        '''Check the option values given by the user, and do other prep.'''
        # We can't do anything without a network.
        if not network_available():
            alert_fatal('No network connection.')
            raise CannotProceed(ExitCode.no_net)

        hint = f'(Hint: use {"/" if sys.platform.startswith("wi") else "-"}h for help.)'

        # We can't do anything without the EPrints server URL.
        if self.api_url is None:
            alert_fatal(f'Must provide an EPrints API URL. {hint}')
            raise CannotProceed(ExitCode.bad_arg)

        if self.lastmod:
            try:
                self.lastmod = parse_datetime(self.lastmod)
                self.lastmod_str = self.lastmod.strftime(DATE_FORMAT)
                if __debug__: log(f'parsed lastmod as {self.lastmod_str}')
            except Exception as ex:
                alert_fatal(f'Unable to parse lastmod value: "{str(ex)}". {hint}')
                raise CannotProceed(ExitCode.bad_arg)

        # It's easier to use None as an indication of no restriction (= 'any').
        if self.status:
            self.status = None if self.status == 'any' else re.split('(\W)', self.status)

        if self.dest == 'all':
            self.dest = service_interfaces()
        else:
            destination_list = self.dest.split(',')
            self.dest = [service_by_name(d) for d in destination_list]
            if None in self.dest:
                bad_dest = destination_list[self.dest.index(None)]
                alert_fatal(f'Unknown destination service "{bad_dest}". {hint}')
                raise CannotProceed(ExitCode.bad_arg)

        host = netloc(self.api_url)
        self.user, self.password, cancel = self.auth_handler.credentials(host)
        if cancel:
            raise UserCancelled
        if self.user:
            inform(f'Using login credentials for user "{self.user}" on {host}.')
        else:
            inform(f'Will not use a login or password for {host}.')

        # The id's are stored as strings, not ints, to avoid repeated conversion
        self.wanted_list = parsed_id_list(self.id_list)

        if self.report_file:
            if writable(self.report_file):
                inform(f'A report will be written to "{self.report_file}"')
            else:
                alert_fatal(f'Cannot write to file "{self.report_file}"')
                raise CannotProceed(ExitCode.file_error)


    def _do_main_work(self):
        '''Performs the core work of this program.'''
        self._report(f'eprints2archives starting {timestamp()}.', True)

        server = EPrintServer(self.api_url, self.user, self.password)
        available = self._eprints_index(server)
        if not available:
            raise NoContent(f'Received empty list from {server}.')
        self._report(f'EPrints server at {self.api_url} has {len(available)} records.')

        # If the user wants specific records, check which ones actually exist.
        if self.wanted_list:
            missing = sorted(list(set(self.wanted_list) - set(available)), key = int)
            if missing and self.quit_on_error:
                raise ValueError(f'{intcomma(len(missing))} of the requested records'
                                 + ' do not exist on the server: {", ".join(missing)}.')
            elif missing:
                msg = (f"Of the records requested, the following don't exist and"
                       + f" will be skipped: {', '.join(missing)}.")
                warn(msg)
                self._report(msg)
            wanted = sorted(list(set(self.wanted_list) - set(missing)), key = int)
            self._report(f'A total of {len(wanted)} records from {server} will be used.')
        else:
            wanted = available

        # Make sure to archive the front pages and some common pages.

        urls = self._eprints_general_urls(server, self.wanted_list)

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
            official_url = lambda r: server.eprint_field_value(r, 'official_url')
            urls += self._eprints_values(official_url, wanted, server, "<official_url>'s")
        else:
            skipped = []
            for r in self._eprints_values(server.eprint_xml, wanted, server, "record materials"):
                eprintid = server.eprint_field_value(r, 'eprintid')
                modtime  = server.eprint_field_value(r, 'lastmod')
                status   = server.eprint_field_value(r, 'eprint_status')
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
            urls += [server.eprint_field_value(r, 'official_url') for r in records]

        # Next, construct "standard" URLs and check that they exist.  Do this
        # AFTER the steps above, because if we did any filtering, we may have
        # a much shorter list of records now than what we started with.

        urls += self._eprints_record_urls(server, records or wanted)

        # Good time to check if the parent thread sent an interrupt.
        raise_for_interrupts()

        # Clean up any None's and make sure we have something left to do.
        # Also make sure the URLs are unique (that's the dict.fromkeys bit).
        urls = list(dict.fromkeys(filter(None, urls)))
        if not urls:
            alert('List of URLs is empty -- nothing to archive')
            return

        # If we get this far, we're doing it.
        inform(f'We have a total of {intcomma(len(urls))} {plural("URL", urls)}'
               + f' to send to {len(self.dest)} {plural("archive", self.dest)}.')
        self._send(urls)
        inform('Done.')


    def _eprints_values(self, value_function, items_list, server, description):
        '''Get values using "value_function" for items in "items_list".'''
        # Helper function: body of loop that is executed in all cases.
        def record_values(items, update_progress):
            results = []
            for item in items:
                if __debug__: log(f'getting data for record {item}')
                failure = None
                try:
                    data = value_function(item)
                except NoContent as ex:
                    failure = f'Server has no content for {item}'
                except AuthenticationFailure as ex:
                    failure = f'Authentication failure trying to get data for {item}'
                except Exception as ex:
                    raise ex
                if failure:
                    if self.quit_on_error:
                        alert(failure)
                        raise CannotProceed(ExitCode.exception)
                    else:
                        warn(failure)
                        continue
                if data is not None:
                    results.append(data)
                elif self.quit_on_error:
                    alert(f'Received no data for {item}')
                    raise CannotProceed(ExitCode.exception)
                update_progress()
                raise_for_interrupts()
            return results

        server_name = f'[sea_green2]{server}[/]'
        header  = f'[green3]Gathering {description} from {server_name} ...'
        return self._gathered(record_values, items_list, header)


    def _eprints_index(self, server):
        '''Return the index from the server, getting it with a progress bar.'''
        header = f'[green3]Getting full EPrints index from [sea_green2]{server}[/] ...'
        with Progress('[progress.description]{task.description}', _BAR) as progress:
            bar = progress.add_task(header, start = False)
            progress.update(bar)
            index = server.index()
            progress.start_task(bar)
            progress.update(bar, advance = 100)
        return index


    def _eprints_general_urls(self, server, id_subset = None):
        '''Return a list of commonly-available, high-level EPrints URLs.

        If parameter value "id_subset" is not None, it is taken to be a list
        of EPrint id's that is used to limit the pages under /view to be
        returned.  Otherwise, if no "id_subset" list is given, all /view
        pages are returned.
        '''
        header = '[green3]Looking through /view pages for URLs ...' + ' '*(len(str(server)) - 4)
        with Progress('[progress.description]{task.description}', _BAR) as progress:
            bar = progress.add_task(header, start = False)
            progress.update(bar)
            if id_subset:
                urls = server.view_urls(id_subset)
            else:
                urls = unique(server.top_level_urls() + server.view_urls())
            progress.start_task(bar)
            progress.update(bar, advance = 100)
        return urls


    def _eprints_record_urls(self, server, records_list):
        '''Get the normal EPrints URLS for the items in "records_list".'''
        # Helper function: body of loop that is executed in all cases.
        def eprints_urls(item_list, update_progress):
            urls = []
            for r in item_list:
                # Note: don't use log() here b/c r could be an xml etree.
                try:
                    urls.append(server.eprint_id_url(r))
                    urls.append(server.eprint_page_url(r))
                except (NoContent, AuthenticationFailure) as ex:
                    continue
                update_progress()
                raise_for_interrupts()
            return urls

        server_name = f'[sea_green2]{server}[/]'
        header  = f'[green3]Checking variant record URLs on {server_name} ...'
        return self._gathered(eprints_urls, records_list, header)


    def _send(self, urls_to_send):
        '''Send the list of URLs to each web archiving service in parallel.'''
        num_urls = len(urls_to_send)
        num_dest = len(self.dest)
        self._report(f'Will send {num_urls} URLs to {num_dest} {plural("service", num_dest)}.')
        if self.force:
            inform('Force option given ⟹  adding URLs even if archives have copies.')

        # Helper function: send urls to given service & use progress bar.
        def send_to_service(dest, prog):
            num_added = 0
            num_skipped = 0
            status_text = activity(dest, ServiceStatus.RUNNING)
            row = prog.add_task(status_text, total = num_urls, added = 0, skipped = 0)
            notify = lambda s: prog.update(row, description = activity(dest, s), refresh = True)
            for url in urls_to_send:
                if __debug__: log(f'next for {dest}: {url}')
                (added, num_existing) = dest.save(url, notify, self.force)
                added_str = "added" if added else "skipped"
                num_added += int(added)
                num_skipped += int(not added)
                prog.update(row, advance = 1, added = num_added, skipped = num_skipped)
                self._report(f'{url} ➜ {dest.name}: {added_str}')
                raise_for_interrupts()

        # Start of actual procedure.
        info = TextColumn('{task.fields[added]} added/{task.fields[skipped]} skipped')
        with Progress('[progress.description]{task.description}', _BAR, info) as prog:
            if __debug__: log(f'starting {self.threads} threads')
            if self.threads == 1:
                # For 1 thread, avoid thread pool to make debugging easier.
                results = [send_to_service(service, prog) for service in self.dest]
            else:
                num_threads = min(num_dest, self.threads)
                if __debug__: log(f'using {num_threads} threads to send records')
                self._executor = ThreadPoolExecutor(max_workers = num_threads,
                                                    thread_name_prefix = 'SendThread')
                self._futures = []
                for service in self.dest:
                    future = self._executor.submit(send_to_service, service, prog)
                    self._futures.append(future)
                [f.result() for f in self._futures]
        self._report(f'Finished sending {num_urls} URLs.')


    def _status_acceptable(self, this_status):
        '''Return True if "this_status" should be accepted based on filters.'''
        # The presence of '^' indicates negation, i.e., "not any of these".
        return ((not '^' in self.status and this_status in self.status)
                or ('^' in self.status and this_status not in self.status))


    def _gathered(self, loop, items_list, header):
        '''Return the collected results of running "loop" in multiple threads.'''
        num_items = len(items_list)
        text = TextColumn('{task.completed}/' + intcomma(num_items) + ' records')
        with Progress('[progress.description]{task.description}', _BAR, text) as progress:
            # Wrap up the progress bar updater as a lambda that we pass down.
            bar = progress.add_task(header, total = num_items)
            update_progress = lambda: progress.update(bar, advance = 1)

            # If the number of items is too small, don't bother going parallel.
            if self.threads == 1 or num_items <= (self.threads * _PARALLEL_THRESHOLD):
                return loop(items_list, update_progress)

            # If we didn't return above, we're going parallel.
            num_threads = min(num_items, self.threads)
            if __debug__: log(f'using {num_threads} threads to gather records')
            self._executor = ThreadPoolExecutor(max_workers = num_threads,
                                                thread_name_prefix = 'GatherThread')
            self._futures = []
            for sublist in slice(items_list, num_threads):
                future = self._executor.submit(loop, sublist, update_progress)
                self._futures.append(future)
            # We get a list of lists, so flatten it before returning.
            return flatten(f.result() for f in self._futures)


    def _report(self, text, overwrite = False):
        '''Write text to the report file, if a report file is being written.'''
        # Opening/closing the file for every write is inefficient, but our
        # network operations are slow, so I think this is not going to have
        # enough impact to be concerned
        if __debug__: log(text)
        if self.report_file:
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
    name = f'[{dest.color}]{dest.name}[/]'
    if status == ServiceStatus.RUNNING:
        return f'[green3]Sending URLs to {name} ...                     '
    elif status == ServiceStatus.PAUSED_RATE_LIMIT:
        return f'[yellow3 on grey35]Paused for rate limit {name} ...               '
    elif status == ServiceStatus.PAUSED_ERROR:
        return f'[orange1]Paused due to {name} error -- will retry ...   '
    elif status == ServiceStatus.UNAVAILABLE:
        return f'[red]No response from {name} servers ...            '
    else:
        return f'[red]Unknown status                                 '
