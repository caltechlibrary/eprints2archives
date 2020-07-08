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

import plac
from   eprints2archives import print_version


# Main program.
# ......................................................................

@plac.annotations(
    api_url    = ('the URL for the REST API of the EPrints server',         'option', 'a'),
    processes  = ('max number of processes to use (default: #cores/2)',     'option', 'c'),
    id_list    = ('list of EPrint record identifiers (can be a file)',      'option', 'i'),
    keep_going = ('do not stop if missing records or errors encountered',   'flag',   'k'),
    lastmod    = ('only get records modified after given date/time',        'option', 'l'),
    quiet      = ('do not print informational messages while working',      'flag',   'q'),
    user       = ('EPrints server user login name "U"',                     'option', 'u'),
    password   = ('EPrints server user password "P"',                       'option', 'p'),
    status     = ('only get records whose status is in the list "S"',       'option', 's'),
    to_service = ('send records to list of services "T" (default: "all")',  'option', 't'),
    services   = ('print list of known services',                           'flag',   'v'),
    delay      = ('wait time bet. requests to services (default: 100 ms)',  'option', 'y'),
    no_color   = ('do not color-code terminal output',                      'flag',   'C'),
    no_keyring = ('do not store credentials in a keyring service',          'flag',   'K'),
    reset_keys = ('reset user and password used',                           'flag',   'R'),
    version    = ('print version info and exit',                            'flag',   'V'),
    debug      = ('write detailed trace to "OUT" ("-" means console)',      'option', '@'),
)

def main(api_url = 'A', processes = 'C', id_list = 'I', keep_going = False,
         lastmod = 'L', quiet = False, user = 'U', password = 'P', status = 'S',
         to_service = 'T', services = False, delay = 100, no_color = False,
         no_keyring = False, reset_keys = False, version = False, debug = 'OUT'):
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
multiuser computer systems. If a given EPrints server does not require a user
name and password, do not use -u or -p and supply blank values when prompted
for them by eprints2archives. (Empty user name and password are allowed values.)

To reset the user name and password (e.g., if a mistake was made the last
time and the wrong credentials were stored in the keyring/keychain system),
add the -R (or /R on Windows) command-line argument to a command. When
eprints2archives is run with this option, it will query for the user name and
password again even if an entry already exists in the keyring or keychain.

Specifying where to send records
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Eprints2archives has a set of built-in adapters to interact with a number of
known public web archives. To learn which services eprints2archives knows
about, use the option -v (or /v on Windows). By default, the program will
send EPrints record URLs to all the known services. The option -t (or /t on
Windows) can be used to select one or a list of services instead. Lists of
services should be separated by commas; e.g., "internetarchive,archive.today".

Eprints2archives will contact the EPrints server serially, but it will use
parallel process threads to send records to archiving services, with one
thread per service. By default the maximum number of threads used is equal
to 1/2 of the number of cores on the computer it is running on. The option
-c (or /c on Windows) can be used to change this number.

Other command-line arguments
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

It is worth noting that hitting an EPrints server for tens of thousands of
records in rapid succession is likely to draw suspicion from server
administrators. By default, this program inserts a small delay between
record fetches (adjustable using the -y command-line option), which may be
too short in some cases. Setting the value to 0 is also possible, but might
get you blocked or banned from an institution's servers.

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
    # Initial setup -----------------------------------------------------------

    # Our defaults are to do things like color the output, which means the
    # command line flags make more sense as negated values (e.g., "no-color").
    # However, dealing with negated variables in our code is confusing, so:
    use_color   = not no_color
    use_keyring = not no_keyring
    debugging   = debug != 'OUT'

    # Preprocess arguments and handle early exits -----------------------------

    if debugging:
        set_debug(True, debug)
        import faulthandler
        faulthandler.enable()
    if version:
        print_version()
        exit()
