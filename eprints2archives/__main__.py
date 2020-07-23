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

from   datetime import datetime as dt
import os
from   os import path
import plac
from   rich.traceback import install as install_rich_traceback
import sys

import eprints2archives
from   eprints2archives import print_version
from   .auth import AuthHandler
from   .cpus import cpus
from   .data_helpers import DATE_FORMAT, flatten, expand_range, parse_datetime
from   .debug import set_debug, log
from   .exceptions import *
from   .exit_codes import ExitCode
from   .files import readable
from   .main_body import MainBody
from   .run_manager import RunManager
from   .services import service_names
from   .ui import UI, inform, warn, alert, alert_fatal


# Main program.
# ......................................................................

@plac.annotations(
    api_url    = ('the URL for the REST API of the EPrints server',         'option', 'a'),
    dest       = ('send to destination service "D" (default: "all")',       'option', 'd'),
    force      = ('ask services to archive records even if already there',  'flag',   'f'),
    id_list    = ('list of EPrint record identifiers (can be a file)',      'option', 'i'),
    keep_going = ('do not stop if missing EPrints records encountered',     'flag',   'k'),
    lastmod    = ('only get EPrints records modified after given date',     'option', 'l'),
    quiet      = ('do not print informational messages while working',      'flag',   'q'),
    user       = ('EPrints server user login name "U"',                     'option', 'u'),
    password   = ('EPrints server user password "P"',                       'option', 'p'),
    status     = ('only get records whose status is in the list "S"',       'option', 's'),
    threads    = ('number of threads to use (default: #cores/2)',           'option', 't'),
    services   = ('print list of known services and exit',                  'flag',   'v'),
    delay      = ('wait time bet. requests to services (default: 100 ms)',  'option', 'y'),
    no_color   = ('do not color-code terminal output',                      'flag',   'C'),
    no_gui     = ('do not start the GUI interface (default: do)',           'flag',   'G'),
    no_keyring = ('do not store credentials in a keyring service',          'flag',   'K'),
    version    = ('print version info and exit',                            'flag',   'V'),
    debug      = ('write detailed trace to "OUT" ("-" means console)',      'option', '@'),
)

def main(api_url = 'A', dest = 'D', force = False, id_list = 'I',
         keep_going = False, lastmod = 'L', quiet = False, user = 'U',
         password = 'P', status = 'S', threads = 'T', services = False,
         delay = 100, no_gui = False, no_color = False, no_keyring = False,
         version = False, debug = 'OUT'):
    '''eprints2archives sends EPrints content to web archiving services.

This program contacts an EPrints REST server whose network API is accessible
at the URL given by the command-line option -a (or /a on Windows). A typical
EPrints server URL has the form "https://server.institution.edu/rest". This
program will automatically add "/eprint" to the URL path, so when writing the
URL after option -a, omit that part of the URL.

Specifying which records to get
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The EPrints records to be written will be limited to the list of EPrints
numbers found in the file given by the option -i (or /i on Windows). If no
-i option is given, this program will download all the contents available at
the given EPrints server. The value of -i can also be one or more integers
separated by commas (e.g., -i 54602,54604), or a range of numbers separated
by a dash (e.g., -i 1-100, which is interpreted as the list of numbers 1, 2,
..., 100 inclusive), or some combination thereof. In those cases, the
records written will be limited to those numbered.

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
server, eprints2archives will stop execution. Common causes of errors include
missing records implied by the arguments to -i, missing files associated with
a given record, and files inaccessible due to permissions errors. If the
option -k (or /k on Windows) is given, eprints2archives will attempt to keep
going upon encountering missing records, or missing files within records, or
similar errors. Option -k is particularly useful when giving a range of numbers
with the -i option, as it is common for EPrints records to be updated or deleted
and gaps to be left in the numbering. (Running without -i will skip over gaps
in the numbering because the available record numbers will be obtained directly
from the server, which is unlike the user providing a list of record numbers
that may or may not exist on the server. However, even without -i, errors may
still result from permissions errors or other causes.)

Providing EPrints server credentials
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Accessing some EPrints servers via the API requires supplying a user login and
password to the server. By default, this program uses the operating system's
keyring/keychain functionality to get a user name and password. If the
information does not exist from a previous run of eprints2archives, it will
query the user interactively for the user name and password, and (unless the -K
or /K argument is given) store them in the user's keyring/keychain so that it
does not have to ask again in the future. It is also possible to supply the
information directly on the command line using the -u and -p options (or /u
and /p on Windows), but this is discouraged because it is insecure on
multiuser computer systems. (However, if you need to reset the user name and/or
password for some reason, use -u with a user name and let it prompt for a
password again.)  If a given EPrints server does not require a user name and
password, do not use -u or -p and supply blank values when prompted for them
by eprints2archives. (Empty user name and password are allowed values.)

Specifying where to send records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Eprints2archives has a set of built-in adapters to interact with a number of
known public web archives. To learn which services eprints2archives knows
about, use the option -v (or /v on Windows). By default, the program will
send EPrints record URLs to all the known services. The option -d (or /d on
Windows) can be used to select one or a list of services instead. Lists of
services should be separated by commas; e.g., "internetarchive,archive.today".

Eprints2archives will contact the EPrints server serially, but it will use
parallel process threads to send records to archiving services, with one
thread per service. By default the maximum number of threads used is equal
to 1/2 of the number of cores on the computer it is running on. The option
-t (or /t on Windows) can be used to change this number.

By default, eprints2archives will only ask a service to archive a copy of an
EPrints record if the service does not already have an archived copy.  This
makes sense because EPrints records usually change infrequently, and there's
little point in repeatedly asking web archives to store new copies.  However,
if you have reason to want the web archives to re-archive EPrints records, you
can use the option -f (or /f on Windows).

Return values
~~~~~~~~~~~~~

This program exits with a return code of 0 if no problems are encountered.
It returns a nonzero value otherwise, following conventions used in shells
such as bash which only understand return code values of 0 to 255. The
following table lists the possible return values:

    0 = no errors were encountered -- success
    1 = no network detected -- cannot proceed
    2 = encountered a bad or missing value for an option
    3 = the user interrupted the program's execution
    4 = an exception or fatal error occurred

Other command-line arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Web archiving services may not accept high rates of submission, so by default,
this program inserts a small delay (100 milliseconds) between submissions of
URLs to archiving services.  The delay time is adjustable using the option -y
(or /y on Windows).  Setting the value to 0 is possible, but beware that it
might get you blocked or banned from a service.

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

    if __debug__: log('='*8 + ' started {}' + '='*8, dt.now().strftime(DATE_FORMAT))
    ui = manager = exception = None
    try:
        ui = UI('eprints2archives', 'send EPrints records to web archives',
                use_gui = not no_gui, use_color = not no_color, be_quiet = quiet)
        auth = AuthHandler(user = None if user == 'U' else user,
                           pswd = None if password == 'P' else password,
                           use_keyring = not no_keyring)
        body = MainBody(api_url = None if api_url == 'A' else api_url,
                        id_list = None if id_list == 'I' else id_list,
                        lastmod = None if lastmod == 'L' else lastmod,
                        status  = 'any' if status == 'S' else status,
                        dest    = 'all' if dest == 'D' else dest,
                        threads = max(1, cpus()//2 if threads == 'T' else int(threads)),
                        auth_handler = auth,
                        errors_ok = keep_going,
                        delay   = int(delay),
                        force = force)
        manager = RunManager()
        manager.run(ui, body)
        exception = body.exception
    except Exception as ex:
        # MainBody exceptions are caught in its thread, so this is something else.
        exception = sys.exc_info()

    # Try to deal with exceptions gracefully ----------------------------------

    exit_code = ExitCode.success
    if exception:
        if type(exception[1]) == CannotProceed:
            exit_code = exception[1].args[0]
        elif type(exception[1]) in [KeyboardInterrupt, UserCancelled]:
            if __debug__: log('received {}', exception[1].__class__.__name__)
            exit_code = ExitCode.user_interrupt
        else:
            exit_code = ExitCode.exception
            from traceback import format_exception
            ex_type = str(exception[1])
            details = ''.join(format_exception(*exception))
            if __debug__: log('Exception: {}\n{}', ex_type, details)
            if debugging:
                import pdb; pdb.set_trace()
            if ui:
                ui.stop()
            if manager:
                manager.stop()
    if __debug__: log('exiting')
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
