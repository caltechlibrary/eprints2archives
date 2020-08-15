eprints2archives<img width="100px" align="right" src=".graphics/eprints2archives-icon.svg">
================

A program that can obtain records from an EPrints server and send them to public web archiving services such as the [Internet Archive](https://archive.org/web/) and others.

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg?style=flat-square)](https://choosealicense.com/licenses/bsd-3-clause)
[![Python](https://img.shields.io/badge/Python-3.6+-brightgreen.svg?style=flat-square)](http://shields.io)
[![Latest release](https://img.shields.io/github/v/release/caltechlibrary/eprints2archives.svg?style=flat-square&color=b44e88)](https://github.com/caltechlibrary/eprints2archives/releases)


Table of contents
-----------------

* [Introduction](#introduction)
* [Installation](#installation)
* [Usage](#usage)
* [Known issues and limitations](#known-issues-and-limitations)
* [Getting help](#getting-help)
* [Contributing](#contributing)
* [License](#license)
* [Authors and history](#authors-and-history)
* [Acknowledgments](#authors-and-acknowledgments)


Introduction
------------

One way to improve preservation and distribution of EPrints server contents is to archive the web pages in archiving sites such as the [Internet Archive](https://archive.org/web/).  _Eprints2archives_ is a self-contained program that does exactly that.  It contacts a given EPrints server, obtains the list of documents it serves (optionally filtered based such as such things as modification date), and sends the document URLs to archiving sites.  The program is written in Python 3 and works over a network using an EPrints server's REST API.


Installation
------------

The instructions below assume you have a Python interpreter installed on your computer; if that's not the case, please first install Python and familiarize yourself with running Python programs on your system.

On **Linux**, **macOS**, and **Windows** operating systems, you should be able to install `eprints2archives` with [`pip`](https://pip.pypa.io/en/stable/installing/).  (If you don't have `pip` already installed on your computer, please seek out instructions for how to obtain it for your particular operating system.)  To install `eprints2archives` from the [Python package repository (PyPI)](https://pypi.org), run the following command:
```
python3 -m pip install eprints2archives --upgrade
```

As an alternative to getting it from [PyPI](https://pypi.org), you can use `pip` to install `eprints2archives` directly from GitHub:
```sh
python3 -m pip install git+https://github.com/caltechlibrary/eprints2archives.git --upgrade
```

Assuming that the installation proceeds normally, on Linux and macOS systems, you should end up with a program called `eprints2archives` in a location normally searched by your terminal shell.
 

Usage
-----

For help with usage at any time, run `eprints2archives` with the option `-h` (or `/h` on Windows).

`eprints2archives` contacts an EPrints REST server whose network API is accessible at the URL given as the value to option `-a` (or `/a` on Windows).  `eprints2archives` **must be given a value for this option**; it cannot infer the server address on its own.  A typical EPrints server URL has the form `https://server.institution.edu/rest`. **This program will automatically add `/eprint` to the URL**, so omit the trailing `/eprint` part of the URL given to `-a`.

Accessing some EPrints servers via the API requires supplying a user login and password to the server. By default, this program retrieves them from your operating system's user keyring/keychain. If the login and password for a given EPrints server does not exist from a previous run of `eprints2archives`, it will ask the user interactively for the user name and password, and then (unless the `-K` option &ndash; or `/K` &ndash; is given) store them in the user's keyring/keychain so that it does not have to ask again in the future. It is also possible to supply the information directly on the command line using the `-u` and `-p` options (or `/u` and `/p` on Windows), but this is discouraged because it is insecure on multiuser computer systems. (However, if you need to reset the user name and/or password for some reason, use `-u` with a user name and let it prompt for a password again.)  If the EPrints server does not require a user name and password, do not use `-u` or `-p`, and supply blank values when prompted for them by `eprints2archives`. (Empty user name and password are allowed values.)


### How the list of records is determined

The EPrints records to be sent to the web archiving services will be limited to the records indicated by the option `-i` (or `/i` on Windows). If no `-i` option is given, this program will use all the records available at the given EPrints server. The value of `-i` can be one or more integers separated by commas (e.g., `-i 54602,54604`), or a range of numbers separated by a dash (e.g., `-i 1-100`, which is interpreted as the list of numbers 1, 2, ..., 100 inclusive), or some combination thereof. The value of the option `-i` can also be a file, in which case, the file is read to get a list of identifiers.

If the `-l` option (or `/l` on Windows) is given, the records will be additionally filtered to return only those whose last-modified date/time stamp is no older than the given date/time description.  Valid descriptors are those accepted by the Python [dateparser](https://pypi.org/project/dateparser/) library.  Make sure to enclose descriptions within single or double quotes.  Examples:

``` shell
eprints2archives -l "2 weeks ago" -a ....
eprints2archives -l "2014-08-29"  -a ....
eprints2archives -l "12 Dec 2014" -a ....
eprints2archives -l "July 4, 2013" -a ....
```

If the `-s` option (or `/s` on Windows) is given, the records will also be filtered to include only those whose `<eprint_status>` element value is one of the listed status codes.  Comparisons are done in a case-insensitive manner.  Putting a caret character (`^`) in front of the status (or status list) negates the sense, so that `eprints2archives` will only keep those records whose `<eprint_status>` value is *not* among those given. Examples:

``` shell
eprints2archives -s archive -a ...
eprints2archives -s ^inbox,buffer,deletion -a ...
```

Both `--lastmod` and `--status` filering are done after the `-i` argument is processed.

By default, if an error occurs when requesting a record from the EPrints server, `eprints2archives` will keep going and not stop execution. Common causes of errors include missing records implied by the arguments to `-i`, missing files associated with a given record, and files inaccessible due to permissions errors. If the option `-e` (or `/e` on Windows) is given, `eprints2archives` will instead stop upon encountering a missing record, or missing file within a record, or similar errors. The default is to merely issue warnings when missing records are encountered because this is less frustrating for most use-cases.


### How URLs are constructed

For every EPrint record, `eprints2archives` constructs 3 URLs and verifies that they exist on the EPrints server; thus, there may be up to 3 URLs sent to each public web archive for every EPrint record on a server.  The URLs are as follows (where `SERVER` is the server hostname + post number (if any), and `N` is the id number of the EPrint record):

1. `https://SERVER/N`
2. `https://SERVER/id/eprint/N`
3. The value of the field `<official_url>` (if any) in the EPrint record.

The first two typically go to the same page on an EPrint server, but web archiving services have no direct mechanism to indicate that a given URL is an alias or redirection for another, so they need to be sent as separate URLs.  The third (the value of `<official_url>`) may be an entirely different URL, which may or may not go to the same location as one of the others.  For example, in the CaltechAUTHORS EPrint server, the record at [`https://authors.library.caltech.edu/85447`](https://authors.library.caltech.edu/85447) has an `<official_url>` value of [`https://resolver.caltech.edu/CaltechAUTHORS:20180327-085537493`](https://resolver.caltech.edu/CaltechAUTHORS:20180327-085537493), but the latter resolves to the former.


### How the destination is determined

`eprints2archives` has a set of built-in adapters to interact with a number of known public web archiving services. To learn which services `eprints2archives` knows about, use the option `-S` (or `/S` on Windows). By default, the program will send EPrints record URLs to all the known services. The option `-d` (or `/d` on Windows) can be used to select one or a list of destination services instead.  Lists of services should be separated by commas with no spaces between them;
e.g., `internetarchive,archivetoday`.

By default, `eprints2archives` will only ask a service to archive a copy of an EPrints record if the service does not already have an archived copy.  This makes sense because EPrints records usually change infrequently, and there's little point in repeatedly asking web archives to make new archives.  However, if you have reason to want the web archives to re-archive EPrints records, you can use the option `-f` (or `/f` on Windows).

`eprints2archives` will use parallel process threads to query the EPrints server as well as to send records to archiving services.  By default, the maximum number of threads used is equal to 1/2 of the number of cores on the computer it is running on. The option `-t` (or `/t` on Windows) can be used to change this number.  `eprints2archives` will always use only one thread per web archiving service (and since there are only a few services, only a few threads are usable during that phase of operation), but a high number of threads can be helpful to speed up the initial data gathering step from the EPrints server.

Beware that there is a lag between when web archives such as Internet Archive receive a URL submission and when a saved copy is made available from the archive.  (In the case of Internet Archive, it is [3-10 hours](https://help.archive.org/hc/en-us/articles/360004651732-Using-The-Wayback-Machine).)  If you cannot find a given EPrints page in an archive shortly after running `eprints2archives`, it may be because not enough time has passed &ndash; try again later.


### Other command-line arguments

To save a report of the articles sent, you can use the option `-r` (`/r` on Windows) followed by a file name.

`eprints2archives` will print informative messages as it works. To limit the messages to warnings and errors only, use the option `-q` (or `/q` on Windows). Also, output is color-coded by default unless the `-C` option (or `/C` on Windows) is given; this option can be helpful if the color control signals create problems for your terminal emulator.

If given the `-@` argument (`/@` on Windows), this program will output a detailed trace of what it is doing, and will also drop into a debugger upon the occurrence of any errors.  The debug trace will be written to the given destination, which can be a dash character (`-`) to indicate console output, or a file path.

If given the `-V` option (`/V` on Windows), this program will print the version and other information to the console, and exit without doing anything else.


### _Summary of command-line options_

The following table summarizes all the command line options available. (Note: on Windows computers, `/` must be used as the prefix character instead of `-`):

| Short&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   | Long&nbsp;form&nbsp;opt&nbsp;&nbsp; | Meaning | Default |  |
|---------- |-------------------|--------------------------------------|---------|---|
| `-a`_A_   | `--api-url`_A_   | Use _A_ as the server's REST API URL | | ⚑ |
| `-d`_D_   | `--dest`_D_      | Send to destination service(s) _D_ | Send to all | |
| `-e`      | `--error-out`   | Stop if encounter missing records | Keep going | |
| `-f`      | `--force`        | Send every record even if copy exists | Skip already-archived records | |
| `-i`_I_   | `--id-list`_I_   | Records to get (can be a file name) | Fetch all records from the server | |
| `-l`_L_   | `--lastmod`_L_   | Filter by last-modified date/time | Don't filter by date/time | |
| `-q`      | `--quiet`        | Don't print info messages while working | Be chatty while working | |
| `-s`_S_   | `--status`_S_    | Filter by status(s) in _S_ | Don't filter by status | |
| `-u`_U_   | `--user`_U_      | User name for EPrints server login | No user name |
| `-p`_P_   | `--password`_U_  | Password for EPrints proxy login | No password |
| `-C`      | `--no-color`     | Don't color-code the output | Color the console messages  | |
| `-K`      | `--no-keyring`   | Don't use a keyring/keychain | Store login info in keyring | |
| `-S`      | `--services`     | Print list of known services and exit | Do other actions instead |
| `-V`      | `--version`      | Print program version info and exit | Do other actions instead | |
| `-@`_OUT_ | `--debug`_OUT_   | Debugging mode; write trace to _OUT_ | Normal mode | ⚐ |

 ⚑ &nbsp; Required argument.<br>
⚐ &nbsp; To write to the console, use the character `-` as the value of _OUT_; otherwise, _OUT_ must be the name of a file where the output should be written.


### Return values

This program exits with a return code of 0 if no problems are encountered.  It returns a nonzero value otherwise, following conventions used in shells such as [bash](https://www.gnu.org/software/bash) which only understand return code values of 0 to 255. The following table lists the possible return values:

```
0 = success -- program completed normally
1 = no network detected -- cannot proceed
2 = encountered a bad or missing value for an option
3 = file error -- encountered a problem with a file
4 = the user interrupted the program's execution
5 = an exception or fatal error occurred
```


Known issues and limitations
----------------------------

Some services impose severe rate limits on URL submissions, and there  is nothing that `eprints2archives` can do about it.  For example, at the time of this writing, [Archive.Today](https://archive.today) only allows 3 URLs to be submitted every 5 minutes.  If you plan on sending a large number of URLs, it may be more convenient to use a separate `eprints2archives` process with the `-d` option to select only one destination, and let it run in its own terminal window.


Getting help
------------

If you find an issue, please submit it in [the GitHub issue tracker](https://github.com/caltechlibrary/eprints2archives/issues) for this repository.


Contributing
------------

We would be happy to receive your help and participation with enhancing `eprints2archives`!  Please visit the [guidelines for contributing](CONTRIBUTING.md) for some tips on getting started.


License
-------

Software produced by the Caltech Library is Copyright (C) 2020, Caltech.  This software is freely distributed under a BSD/MIT type license.  Please see the [LICENSE](LICENSE) file for more information.


Authors and history
---------------------------

[Mike Hucka](https://github.com/mhucka) began writing this program in mid-2020, in response to discussions with colleagues in Caltech's [Digital Library Development](https://www.library.caltech.edu/staff?&field_directory_department_name=Digital%20Library%20Development) group.

The TimeMap parsing code in [eprints2archives/services/timemap.py](eprints2archives/services/timemap.py) originally came from the [Off-Topic Memento Toolkit](https://github.com/oduwsdl/off-topic-memento-toolkit), by Shawn M. Jones, as it existed on 2020-07-29.  The OTMT code is made available according to the MIT license.  Acknowledgements and additional information are provided in the file header of [eprints2archives/services/timemap.py](eprints2archives/services/timemap.py).

The algorithm and some code for interacting with [Archive.Today](https://archive.today) were borrowed from [ArchiveNow](https://github.com/oduwsdl/archivenow), a tool developed by [Web Science and Digital Libraries Research Group at Old Dominion University](https://ws-dl.blogspot.com).  The authors and contributors of the specific code file used ([is_handler.py](https://github.com/oduwsdl/archivenow/blob/master/archivenow/handlers/is_handler.py)), as it existed on 2020-07-17, were [Mohamed Aturban](https://github.com/maturban), [Shawn M. Jones](https://github.com/shawnmjones), [veloute](https://github.com/veloute), and [evil-wayback](https://github.com/evil-wayback).  ArchiveNow is made available according to the MIT license.  Acknowledgements and additional information are provided in the file header of [eprints2archives/services/archivetoday.py](eprints2archives/services/archivetoday.py).

`eprints2archives` makes use of numerous open-source packages, without which it would have been effectively impossible to develop `eprints2archives` with the resources we had.  We want to acknowledge this debt.  In alphabetical order, the packages are:

* [aenum](https://pypi.org/project/aenum/) &ndash; advanced enumerations for Python
* [appdirs](https://github.com/ActiveState/appdirs) &ndash; determine the appropriate app dirs on different OSes
* [dateparser](https://pypi.org/project/dateparser/) &ndash; parse dates in almost any string format
* [distro](https://github.com/nir0s/distro) &ndash; get info about the OS distribution running the current computer
* [humanize](https://github.com/jmoiron/humanize) &ndash; helps write large numbers in a more human-readable form
* [ipdb](https://github.com/gotcha/ipdb) &ndash; the IPython debugger
* [keyring](https://github.com/jaraco/keyring) &ndash; access the system keyring service from Python
* [lxml](https://lxml.de) &ndash; an XML parsing library for Python
* [plac](http://micheles.github.io/plac/) &ndash; a command line argument parser
* [pydash]() &ndash; kitchen sink of Python utility libraries for doing “stuff” 
* [pypubsub](https://github.com/schollii/pypubsub) &ndash; a publish-and-subscribe message-passing library for Python
* [requests](http://docs.python-requests.org) &ndash; an HTTP library for Python
* [rich](https://rich.readthedocs.io/en/latest/) &ndash; library for writing styled text to the terminal
* [setuptools](https://github.com/pypa/setuptools) &ndash; library for `setup.py`
* [urllib3](https://urllib3.readthedocs.io/en/latest/) &ndash; HTTP client library for Python
* [validators](https://github.com/kvesteri/validators) &ndash; data validation package for Python


Acknowledgments
---------------

The [vector artwork](https://thenounproject.com/term/upload/2800646/) of a cloud and arrow contained within the logo for this repository was created by [Vimal](https://thenounproject.com/vimalraj2/) from the Noun Project.  It is licensed under the Creative Commons [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/) license.

This work was funded by the California Institute of Technology Library.

<div align="center">
  <br>
  <a href="https://www.caltech.edu">
    <img width="100" height="100" src=".graphics/caltech-round.svg">
  </a>
</div>
