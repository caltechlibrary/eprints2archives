'''
__main__: main command-line interface to eprints2archives

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import os
from   os import path, cpu_count
import plac
import sys

import eprints2archives
from   eprints2archives import print_version
from   .auth import AuthHandler
from   .data_helpers import DATE_FORMAT, expand_range, parse_datetime, timestamp
from   .debug import set_debug, log, logr
from   .exceptions import *
from   .exit_codes import ExitCode
from   .files import readable
from   .interruptions import interrupt, interrupted
from   .main_body import MainBody
from   .run_manager import RunManager
from   .services import service_names
from   .ui import UI, inform, warn, alert, alert_fatal


# Main program.
# ......................................................................

@plac.annotations(
    api_url    = ('the URL for the REST API of the EPrints server',        'option', 'a'),
    dest       = ('send to destination service "D" (default: "all")',      'option', 'd'),
    error_out  = ('stop if encounter missing records or similar problems', 'flag',   'e'),
    force      = ('ask services to archive records even if already there', 'flag',   'f'),
    id_list    = ('list of EPrint record identifiers (can be a file)',     'option', 'i'),
    lastmod    = ('only get EPrints records modified after given date',    'option', 'l'),
    quiet      = ('do not print informational messages while working',     'flag',   'q'),
    user       = ('EPrints server user login name "U"',                    'option', 'u'),
    password   = ('EPrints server user password "P"',                      'option', 'p'),
    report     = ('save a report to file "R"',                             'option', 'r'),
    status     = ('only get records whose status is in the list "S"',      'option', 's'),
    threads    = ('number of threads to use (default: #cores/2)',          'option', 't'),
    no_color   = ('do not color-code terminal output',                     'flag',   'C'),
    no_keyring = ('do not store credentials in a keyring service',         'flag',   'K'),
    services   = ('print list of known archiving services and exit',       'flag',   'S'),
    version    = ('print version info and exit',                           'flag',   'V'),
    debug      = ('write detailed trace to "OUT" ("-" means console)',     'option', '@'),
)

def main(api_url = 'A', dest = 'D', error_out = False, force = False,
         id_list = 'I', lastmod = 'L', quiet = False, user = 'U',
         password = 'P', report = 'R', status = 'S', threads = 'T',
         no_color = False, no_keyring = False,
         services = False, version = False, debug = 'OUT'):
    '''eprints2archives sends EPrints content to web archiving services.

This program contacts a given EPrints server, obtains the list of documents it
serves (optionally modified based on selectors such as date), determines the
URLs for the document pages on the EPrints server, and sends the URLs to
archiving sites such as the Internet Archive.  This helps preserve the
EPrints server contents in third-party archiving sites.

Specifying which EPrints server to contact
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This program contacts an EPrints REST server whose network API is accessible
at the URL given by the command-line option -a (or /a on Windows). A typical
EPrints server URL has the form "https://server.institution.edu/rest". This
program will automatically add "/eprint" to the URL path, so when writing the
URL after option -a, omit the trailing "/eprint" part of the URL.

Accessing some EPrints servers via the API requires supplying a user login and
password to the server. By default, this program uses the operating system's
keyring/keychain functionality to get a user name and password. If the
information does not exist from a previous run of eprints2archives, it will
ask the user interactively for the user name and password, and (unless the -K
or /K argument is given) store them in the user's keyring/keychain so that it
does not have to ask again in the future. It is also possible to supply the
information directly on the command line using the -u and -p options (or /u
and /p on Windows), but this is discouraged because it is insecure on
multiuser computer systems. (However, if you need to reset the user name and/or
password for some reason, use -u with a user name and let it prompt for a
password again.)  If a given EPrints server does not require a user name and
password, do not use -u or -p and supply blank values when prompted for them
by eprints2archives. (Empty user name and password are allowed values.)

Specifying which records to send
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The EPrints records to be sent to the web archiving services will be limited to
the records indicated by the option -i (or /i on Windows). If no -i option is
given, this program will use all the records available at the given EPrints
server. The value of -i can be one or more integers separated by commas
(e.g., -i 54602,54604), or a range of numbers separated by a dash (e.g.,
-i 1-100, which is interpreted as the list of numbers 1, 2, ..., 100 inclusive),
or some combination thereof. The value of the option -i can also be a file, in
which case, the file is read to get a list of identifiers.

If the -l option (or /l on Windows) is given, the records will be additionally
filtered to return only those whose last-modified date/time stamp is no older
than the given date/time description. Valid descriptors are those accepted
by the Python dateparser library. Make sure to enclose descriptions within
single or double quotes. Examples:

  eprints2archives -l "2 weeks ago" -a ....
  eprints2archives -l "2014-08-29"  -a ....
  eprints2archives -l "12 Dec 2014" -a ....
  eprints2archives -l "July 4, 2013" -a ....

If the -s option (or /s on Windows) is given, the records will also be filtered
to include only those whose eprint_status element value is one of the listed
status codes. Comparisons are done in a case-insensitive manner. Putting a
caret character ("^") in front of the status (or status list) negates the
sense, so that eprints2archives will only keep those records whose eprint_status
value is *not* among those given. Examples:

  eprints2archives -s archive -a ...
  eprints2archives -s ^inbox,buffer,deletion -a ...

Both lastmod and status filering are done after the -i argument is processed.

By default, if an error occurs when requesting a record from the EPrints
server, eprints2archives will keep going and not stop execution. Common causes
of errors include missing records implied by the arguments to -i, missing files
associated with a given record, and files inaccessible due to permissions
errors. If the option -e (or /e on Windows) is given, eprints2archives will
instead stop upon encountering a missing record, or missing file within a
record, or similar errors. The default is to merely issue warnings when missing
records are encountered because this is less frustrating for most use-cases.

How URLs are constructed
~~~~~~~~~~~~~~~~~~~~~~~~

eprints2archives always tries to construct 3 URLs for every EPrint record and
verifies that they exist on the EPrints server. The URLs are as follows, where
N is the id number of the EPrint record:

  1. https://SERVER/N
  2. https://SERVER/id/eprint/N
  3. The value of the field official_url (if any) in the EPrint record.

The first two typically go to the same page on an EPrint server, but web
archiving services have no direct mechanism to indicate that a given URL is an
alias or redirection for another, so they need to be sent as separate URLs. On
the other hand, the value of official_url may be an entirely different URL,
which may or may not go to the same location as one of the others.

Next, if no selection or filtering is applied (i.e., none of the options -i,
-l or -s are given to eprints2archives), eprints2archives gathers additional
URLs as follows (where SERVER is the server hostname + post number, if any):

  * https://SERVER
  * https://SERVER/view
  * The set of pages https://SERVER/view/X, where each X is obtained by
    parsing the HTML of https://SERVER/view and extracting links to pages
    under https://SERVER/view/
  * The set of pages https://SERVER/view/X/Y, where each Y is obtained by
    parsing the HTML of https://SERVER/view/X and extracting links to pages
    under https://SERVER/view/X

On the other hand, if selection and/or filtering _are_ in effect (i.e., if any
of the options -i, -l and/or -s are used), then eprints2archives ONLY
extracts the URLs https://SERVER/view/X/N.html for every EPrints identifier N
selected or left after filtering (if such URLs exist on the server).

Specifying where to send records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Eprints2archives has a set of built-in adapters to interact with a number of
known public web archiving services. To learn which services eprints2archives
knows about, use the option -S (or /S on Windows). By default, the program will
send EPrints record URLs to all the known services. The option -d (or /d on
Windows) can be used to select one or a list of destination services instead.
Lists of services should be separated by commas with no spaces between them;
e.g., "internetarchive,archivetoday".

By default, eprints2archives will only ask a service to archive a copy of an
EPrints record if the service does not already have an archived copy.  This
makes sense because EPrints records usually change infrequently, and there's
little point in repeatedly asking web archives to make new archives.  However,
if you have reason to want the web archives to re-archive EPrints records, you
can use the option -f (or /f on Windows).

Eprints2archives will use parallel process threads to query the EPrints server
as well as to send records to archiving services.  By default, the maximum
number of threads used is equal to 1/2 of the number of cores on the computer
it is running on. The option -t (or /t on Windows) can be used to change this
number.  Eprints2archives will always use only one thread per web archiving
service (and since there are only a few services, only a few threads are usable
during that phase of operation), but a high number of threads can be helpful
to speed up the initial data gathering step from the EPrints server.

To save a report of the articles sent to archiving services, you can use the
option -r (/r on Windows) followed by a file name.

Note that there is a lag between when web archives such as Internet Archive
receive a URL submission and when a saved copy is made available from the
archive.  (In the case of Internet Archive, it is 3-10 hours.)  If you cannot
find a given EPrints page in an archive shortly after running eprints2archives,
it may be because not enough time has passed -- try again later.

Return values
~~~~~~~~~~~~~

This program exits with a return code of 0 if no problems are encountered.
It returns a nonzero value otherwise, following conventions used in shells
such as bash which only understand return code values of 0 to 255. The
following table lists the possible return values:

    0 = success -- program completed normally
    1 = no network detected -- cannot proceed
    2 = encountered a bad or missing value for an option
    3 = file error -- encountered a problem with a file
    4 = the user interrupted the program's execution
    5 = an exception or fatal error occurred

Other command-line arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

eprints2archives will print messages as it works. To limit the messages
to warnings and errors only, use the option -q (or /q on Windows). Also,
output is color-coded by default unless the -C option (or /C on Windows) is
given; this option can be helpful if the color control signals create
problems for your terminal emulator.

If given the -@ argument (/@ on Windows), this program will output a detailed
trace of what it is doing, and will also drop into a debugger upon the
occurrence of any errors. The debug trace will be written to the given
destination, which can be a dash character (-) to indicate console output, or
a file path.

If given the -V option (/V on Windows), this program will print the version
and other information, and exit without doing anything else.

Command-line options summary
~~~~~~~~~~~~~~~~~~~~~~~~~~~~
'''
    # Preprocess arguments and handle early exits -----------------------------

    debugging = debug != 'OUT'
    if debugging:
        set_debug(True, debug)
        from rich.traceback import install as install_rich_traceback
        install_rich_traceback()
        import faulthandler
        faulthandler.enable()

    if version:
        print_version()
        exit(0)

    if services:
        print('Known services:', ', '.join(service_names()))
        exit(0)

    # Do the real work --------------------------------------------------------

    if __debug__: log('='*8 + f' started {timestamp()} ' + '='*8)
    ui = manager = exception = None
    try:
        ui = UI('eprints2archives', 'send EPrints records to web archives',
                use_color = not no_color, be_quiet = quiet)
        auth = AuthHandler(prompter = ui.login_details,
                           user = None if user == 'U' else user,
                           pswd = None if password == 'P' else password,
                           use_keyring = not no_keyring)
        body = MainBody(api_url = None if api_url == 'A' else api_url,
                        id_list = None if id_list == 'I' else id_list,
                        lastmod = None if lastmod == 'L' else lastmod,
                        status  = 'any' if status == 'S' else status,
                        dest    = 'all' if dest == 'D' else dest,
                        threads = max(1, cpu_count()//2 if threads == 'T' else int(threads)),
                        auth_handler = auth,
                        quit_on_error = error_out,
                        force = force,
                        report_file = None if report == 'R' else report)
        manager = RunManager()
        manager.run(ui, body)
        exception = body.exception
    except (KeyboardInterrupt, UserCancelled) as ex:
        # In Python, the main thread (i.e., this one) is the one that gets ^C.
        alert('Quit received; shutting down ...')
        interrupt()
        manager.stop()
        exception = sys.exc_info()
    except Exception as ex:
        # MainBody exceptions are caught in its thread, so this is something else.
        exception = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    exit_code = ExitCode.success
    if exception:
        if type(exception[1]) == CannotProceed:
            exit_code = exception[1].args[0]
        elif type(exception[1]) in [KeyboardInterrupt, UserCancelled]:
            if __debug__: log(f'received {exception[1].__class__.__name__}')
            exit_code = ExitCode.user_interrupt
        else:
            exit_code = ExitCode.exception
            from traceback import format_exception
            msg = str(exception[1])
            details = ''.join(format_exception(*exception))
            if __debug__: logr(f'Exception: {msg}\n{details}')
            import pdb; pdb.set_trace()
            if debugging:
                import pdb; pdb.set_trace()
            if manager:
                manager.stop()
    if __debug__: log('_'*8 + f' stopped {timestamp()} ' + '_'*8)
    exit(exit_code.value[0])


# Main entry point.
# ......................................................................

# On windows, we want plac to use slash intead of hyphen for cmd-line options.
if sys.platform.startswith('win'):
    main.prefix_chars = '/'

# The following allows users to invoke this using "python3 -m eprints2archives".
if __name__ == '__main__':
    plac.call(main)


# For Emacs users
# ......................................................................
# Local Variables:
# mode: python
# python-indent-offset: 4
# End:
