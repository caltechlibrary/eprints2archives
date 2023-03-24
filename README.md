# eprints2archives<img width="12%" align="right" src="https://raw.githubusercontent.com/caltechlibrary/eprints2archives/main/.graphics/eprints2archives-icon.png">

A program that can obtain records from an EPrints server and send them to public web archiving services such as the [the Wayback Machine at the Internet Archive](https://archive.org/web/) and others.

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://choosealicense.com/licenses/bsd-3-clause)
[![Python](https://img.shields.io/badge/Python-3.6+-brightgreen.svg?color=yellow)](http://shields.io)
[![CodeQL](https://github.com/caltechlibrary/eprints2archives/actions/workflows/codeql-analysis.yml/badge.svg)](https://github.com/caltechlibrary/eprints2archives/actions/workflows/codeql-analysis.yml)
[![Latest release](https://img.shields.io/github/v/release/caltechlibrary/eprints2archives.svg?color=b44e88)](https://github.com/caltechlibrary/eprints2archives/releases)
[![DOI](http://img.shields.io/badge/DOI-10.22002/D1.20119-blue.svg)](https://data.caltech.edu/records/20119)
[![PyPI](https://img.shields.io/pypi/v/eprints2archives.svg?color=red)](https://pypi.org/project/eprints2archives/)


## Table of contents

* [Introduction](#introduction)
* [Installation](#installation)
* [Usage](#usage)
* [Known issues and limitations](#known-issues-and-limitations)
* [Relationships to other similar tools](#relationships-to-other-similar-tools)
* [Getting help](#getting-help)
* [Contributing](#contributing)
* [License](#license)
* [Authors and history](#authors-and-history)
* [Acknowledgments](#authors-and-acknowledgments)


## Introduction

`eprints2archives` is a self-contained program to archive the web pages of an EPrints server in public web archiving sites such as the [Internet Archive](https://archive.org/web/).  It contacts an EPrints server, obtains the list of documents it serves (optionally filtered based on such things as modification date), determines the document URLs, extracts additional URLs by scraping pages under the `/view` section of the public site, and finally, sends the collected URLs to web archives.  Use-cases include archiving an server content ahead of migration to another system, and preserving contents in independent third-party archives.

The program is written in Python 3 and works over a network using an EPrints server's REST API and normal HTTP.  `eprints2archives` can work with EPrints servers that require logins as well as those that allow anonymous access.  It uses parallel threads by default, transparently handles rate limits, and robustly deals with network errors.

<p align="center">
  <a href="https://asciinema.org/a/357432"><img src="https://raw.githubusercontent.com/caltechlibrary/eprints2archives/main/.graphics/eprints2archives-1.2-screenshot.png" alt="Screencast of simple eprints2archives"><i>Click to run asciinema screencast.</i></a>
</p>


## Installation

The instructions below assume you have a Python interpreter version 3.6 or higher installed on your computer; if that's not the case, please first install Python and familiarize yourself with running Python programs on your system. If you are unsure of which version of Python you have, you can find out by running the following command in a terminal and inspecting the results:
```sh
# Note: on Windows, you may have to use "python" instead of "python3"
python3 --version
```

Note: if you are using macOS Catalina (10.15) or later and have never run `python3`, then the first time you do, macOS will ask you if you want to install the macOS command-line developer tools.  Go ahead and do so, as this is the easiest way to get a recent-enough Python&nbsp;3 on those systems.


### Approach 1: using the standalone executables

Beginning with version 1.3.2, runnable self-contained single-file executables are available for select operating system and Python version combinations &ndash; to use them, you **only** need a Python&nbsp;3 interpreter and a copy of `eprints2archives`, but **do not** need to run `pip install` or other steps. Please click on the relevant heading below to learn more.

<details><summary><img alt="macOS" align="bottom" height="26px" src="https://github.com/caltechlibrary/eprints2archives/raw/main/.graphics/mac-os-32.png">&nbsp;<strong>macOS</strong></summary>

Visit the [eprints2archives releases page](https://github.com/caltechlibrary/eprints2archives/releases) and look for the ZIP files with names such as (e.g.) `eprints2archives-1.3.3-macos-python3.8.zip`. Then:
1. Download the one matching your version of Python
2. Unzip the file (if your browser did not automatically unzip it for you)
3. Open the folder thus created (it will have a name like `eprints2archives-1.3.3-macos-python3.8`)
4. Look inside for `eprints2archives` and move it to a location where you put other command-line programs (e.g., `/usr/local/bin`)

</details><details><summary><img alt="Linux" align="bottom" height="26px" src="https://github.com/caltechlibrary/eprints2archives/raw/main/.graphics/linux-32.png">&nbsp;<strong>Linux</strong></summary>

Visit the [eprints2archives releases page](https://github.com/caltechlibrary/eprints2archives/releases) and look for the ZIP files with names such as (e.g.) `eprints2archives-1.3.3-linux-python3.8.zip`. Then:
1. Download the one matching your version of Python
2. Unzip the file (if your browser did not automatically unzip it for you)
3. Open the folder thus created (it will have a name like `eprints2archives-1.3.3-linux-python3.8`)
4. Look inside for `eprints2archives` and move it to a location where you put other command-line programs (e.g., `/usr/local/bin`)

</details><details><summary><img alt="Windows" align="bottom" height="26px" src="https://github.com/caltechlibrary/eprints2archives/raw/main/.graphics/os-windows-32.png">&nbsp;<strong>Windows</strong></summary>

Standalone executables for Windows are not available at this time. If you are running Windows, please use one of the other methods described below.

</details>


### Approach 2: using `pip`

On **Linux**, **macOS**, and **Windows** operating systems, you should be able to install or upgrade `eprints2archives` with [`pip`](https://pip.pypa.io/en/stable/installing/).  To install `eprints2archives` from the [Python package repository (PyPI)](https://pypi.org), run the following command:
```
python3 -m pip install eprints2archives --upgrade
```


### Approach 3: using `git clone`

As an alternative to getting it from [PyPI](https://pypi.org), you can use `pip` to install or upgrade `eprints2archives` directly from GitHub, like this:
```sh
python3 -m pip install git+https://github.com/caltechlibrary/eprints2archives.git --upgrade
```


## Usage

Running `eprints2archives` from a terminal shell then should be as simple as running any other shell command on your system:

```bash
eprints2archives -h
```

If that fails for some reason, you should be able to run `eprints2archives` from anywhere using the normal approach for running Python modules:

```bash
python3 -m eprints2archives -h
```

On Windows, Python 3 is usually installed as just `python` instead of `python3`, and `eprints2archives` follows the Windows convention of using `/` as the option prefix instead of a dash (`-`).  So, instead of the above, you would type

```shell
python -m eprints2archives /h
```


### Specifying the EPrints server

The `eprints2archives` program contacts the EPrints server whose web address is given as the value to the option `-a` (or `/a` on Windows).  A typical EPrints server REST API will have a URL of the form `https://server.institution.edu/rest`, but you can give it just `https://server.institution.edu` and `eprints2archives` will add the `/rest` part if it is missing.  Note that **a value for `-a` is required**; it cannot infer the server address on its own.


### Authentication or anonymous use

Accessing some EPrints servers via the API requires supplying a user login and password to the server. By default, this program retrieves them from your operating system's user keyring/keychain. If the login and password for a given EPrints server does not exist from a previous run of `eprints2archives`, it will ask for the user name and password, and then (unless the `-K` option &ndash; or `/K` on Windows &ndash; is given) store them in your keyring/keychain so that it does not have to ask again in the future. It is also possible to supply the information directly on the command line using the `-u` and `-p` options (or `/u` and `/p` on Windows), but this is discouraged because it is insecure on multiuser computer systems. (However, if you need to reset the user name and/or password for some reason, use `-u` with a user name and let it prompt for a password again.)  

If a given EPrints server does _not_ require a user name and password (i.e., it allows anonymous use), **supply blank values** when prompted for them by `eprints2archives` and do not use the options `-u` or `-p`. (Empty user name and password are allowed values.)


### How the list of records is determined

The EPrints records to be sent to the web archiving services will be limited to the records indicated by the option `-i` (or `/i` on Windows). If no `-i` option is given, this program will use all the records available at the given EPrints server. The value of `-i` can be one or more integers separated by commas (e.g., `-i 54602,54604`), or a range of numbers separated by a dash (e.g., `-i 1-100`, which is interpreted as the list of numbers 1, 2, ..., 100 inclusive), or some combination thereof. The value of the option `-i` can also be a file, in which case, the file is read to get a list of identifiers.

If the `-l` option (or `/l` on Windows) is given, the records will be additionally filtered to return only those whose last-modified date/time stamp is no older than the given date/time description.  Valid descriptors are those accepted by the Python [dateparser](https://pypi.org/project/dateparser/) library.  Make sure to enclose descriptions within single or double quotes.  Examples:

``` shell
eprints2archives -l "2 weeks ago" -a ....
eprints2archives -l "2014-08-29"  -a ....
eprints2archives -l "12 Dec 2014" -a ....
eprints2archives -l "July 4, 2013" -a ....
```

If the `-s` option (or `/s` on Windows) is given, the records will also be filtered to include only those whose `eprint_status` field value is one of the listed status codes.  Comparisons are done in a case-insensitive manner.  Putting a caret character (`^`) in front of the status (or status list) negates the sense, so that `eprints2archives` will only keep those records whose `<eprint_status>` value is *not* among those given. Examples:

``` shell
eprints2archives -s archive -a ...
eprints2archives -s ^inbox,buffer,deletion -a ...
```

Both `--lastmod` and `--status` filtering are done after the `-i` argument is processed.

By default, if an error occurs when requesting a record or value from the EPrints server, `eprints2archives` will keep going, moving on to the next one. Common causes of errors include missing records implied by the arguments to `-i`, missing files associated with a given record, and files inaccessible due to permissions errors. If the option `-e` (or `/e` on Windows) is given, `eprints2archives` will instead stop upon encountering a missing record, or missing file within a record, or similar errors. The default is to only issue warnings because this is less frustrating for most use-cases.


### How URLs are constructed

The list of EPrints URLs sent to web archiving sites depends on the command-line options given to `eprints2archives` as well as the URLs that actually exist on the server.  In a nutshell, if _not_ given a list of identifiers or filtering criteria, it will send URLs for every record along with the URLs of some general pages; by contrast, if the list of records is restricted somehow (by the use of `-i`, `-l`, and/or `-s`), `eprints2archives` will _only_ send URLs related to the records identified.


#### _URLs for individual EPrints records_

`eprints2archives` always tries to construct 3 URLs for every EPrint record and verifies that they exist on the EPrints server.  The URLs are as follows, where `N` is the id number of the EPrint record:

1. `https://SERVER/N`
2. `https://SERVER/id/eprint/N`
3. The value of the field `official_url` (if any) in the EPrint record.

The first two typically go to the same page on an EPrint server, but web archiving services have no direct mechanism to indicate that a given URL is an alias or redirection for another, so they need to be sent as separate URLs.  On the other hand, the value of `official_url` may be an entirely different URL, which may or may not go to the same location as one of the others.  For example, in the CaltechAUTHORS EPrint server, the record at [`https://authors.library.caltech.edu/85447`](https://authors.library.caltech.edu/85447) has an `official_url` value of [`https://resolver.caltech.edu/CaltechAUTHORS:20180327-085537493`](https://resolver.caltech.edu/CaltechAUTHORS:20180327-085537493), but the latter is a redirection back to [`https://authors.library.caltech.edu/85447`](https://authors.library.caltech.edu/85447).  `eprints2archives` performs basic validation on the URL values, to make sure they appear to be formally valid and filter out malformed URLs, but does not verify that the locations actually exist.


#### _Additional general URLs_

If _no_ selection or filtering is applied (i.e., none of the options `-i`, `-l` or `-s` are given to `eprints2archives`), then `eprints2archives` gathers additional URLs as follows (where `SERVER` is the server hostname + post number, if any):

* `https://SERVER`
* `https://SERVER/view`
* The set of pages `https://SERVER/view/X`, where each `X` is obtained by parsing the HTML of `https://SERVER/view` and extracting links to pages under `https://SERVER/view/`
* The set of pages `https://SERVER/view/X/Y`, where each `Y` is obtained by parsing the HTML of `https://SERVER/view/X` and extracting links to pages under `https://SERVER/view/X`

On the other hand, if selection and/or filtering _are_ in effect (i.e., if any of the options `-i`, `-l`, and/or `-s` are used), then `eprints2archives` _only_ extracts the URLs `https://SERVER/view/X/N.html` for every EPrints identifier `N` that is selected via `-i` and left after filtering with `-l` and `-s`, if such URLs exist on the server.  (E.g., Caltech EPrints servers have a page at `https://SERVER/view/ids/`, containing every public EPrint identifier `N`  linked to a page of the form `https://SERVER/view/ids/N.html`.  Other servers may have a similar section named something other than `/view/ids/`; `eprints2archives` avoids hardwired assumptions and simply looks for pages ending in `N.html` under `/view/X/`.)

The general URLs from one of these two cases (the ones used if no selection or filter is applied, _or_ the ones used when selection and/or filtering are in effect) are combined with the URLs for individual EPrints records to produce the final set of URLs sent to web archiving destinations.


### How the destination is determined

`eprints2archives` has a set of built-in adapters to interact with a number of known public web archiving services. To learn which services `eprints2archives` knows about, use the option `-S` (or `/S` on Windows). By default, the program will send EPrints record URLs to all the known services. The option `-d` (or `/d` on Windows) can be used to select one or a list of destination services instead.  Lists of services should be separated by commas with no spaces between them;
e.g., `internetarchive,archivetoday`.

By default, `eprints2archives` will only ask a service to archive a copy of an EPrints record if the service does not already have an archived copy.  This makes sense because EPrints records usually change infrequently, and there's little point in repeatedly asking web archives to make new archives.  However, if you have reason to want the web archives to re-archive EPrints records, you can use the option `-f` (or `/f` on Windows).

`eprints2archives` will use parallel process threads to query the EPrints server as well as to send records to archiving services.  By default, the maximum number of threads used is equal to 1/2 of the number of cores on the computer it is running on. The option `-t` (or `/t` on Windows) can be used to change this number.  `eprints2archives` will always use only one thread per web archiving service (and since there are only a few services, only a few threads are usable during that phase of operation), but a higher number of threads can be helpful to speed up the initial data gathering step from the EPrints server.

**Beware that there is a lag** between when web archives such as Internet Archive receive a URL submission and when a saved copy is made available from the archive.  (For Internet Archive, it is [3-10 hours](https://help.archive.org/hc/en-us/articles/360004651732-Using-The-Wayback-Machine).)  If you cannot find a given EPrints page in an archive shortly after running `eprints2archives`, it may be because not enough time has passed.


### Other command-line arguments

To save a report of the articles sent, you can use the option `-r` (`/r` on Windows) followed by a file name.

`eprints2archives` will print informative messages as it works. To limit the messages to warnings and errors only, use the option `-q` (or `/q` on Windows). Also, output is color-coded by default unless the `-C` option (or `/C` on Windows) is given; this option can be helpful if the color control signals create problems for your terminal emulator.

If given the `-@` argument (`/@` on Windows), this program will output a detailed trace of what it is doing, and will also drop into a debugger upon the occurrence of any errors.  The debug trace will be written to the given destination, which can be a dash character (`-`) to indicate the standard error stream (`sys.stderr`), or a file path.  Note, however, that if `eprints2archives` is being run with [Python optimization](https://docs.python.org/3/using/cmdline.html#cmdoption-o) enabled, then `-@` will have no effect and will be silently ignored.

If given the `-V` option (`/V` on Windows), this program will print the version and other information to the console, and exit without doing anything else.


### _Summary of command-line options_

The following table summarizes all the command line options available. (Note: on Windows computers, `/` must be used as the prefix character instead of `-`):

| Short&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;   | Long&nbsp;form&nbsp;opt&nbsp;&nbsp; | Meaning | Default |  |
|---------- |-------------------|--------------------------------------|---------|---|
| `-a`_A_   | `--api-url`_A_   | Use _A_ as the server's REST API URL | | ⚑ |
| `-d`_D_   | `--dest`_D_      | Send to destination service(s) _D_ | Send to all | |
| `-e`      | `--error-out`   | Stop if encounter missing records | Keep going | |
| `-f`      | `--force`        | Send each record even if copy exists | Skip already-archived records | |
| `-i`_I_   | `--id-list`_I_   | Records to get (can be a file name) | Fetch all EPrints records | |
| `-l`_L_   | `--lastmod`_L_   | Filter by last-modified date/time | Don't filter by date/time | |
| `-q`      | `--quiet`        | Don't print general info messages | Be chatty while working | |
| `-s`_S_   | `--status`_S_    | Filter by status(s) in _S_ | Don't filter by status | |
| `-u`_U_   | `--user`_U_      | User name for EPrints server login | No user name |
| `-p`_P_   | `--password`_U_  | Password for EPrints proxy login | No password |
| `-C`      | `--no-color`     | Don't color-code the output | Color the console messages  | |
| `-K`      | `--no-keyring`   | Don't use a keyring/keychain | Store login info in keyring | |
| `-S`      | `--services`     | Print list of known services and exit | Do other actions instead |
| `-V`      | `--version`      | Print program version info and exit | Do other actions instead | |
| `-@`_OUT_ | `--debug`_OUT_   | Debugging mode; write trace to _OUT_ | Normal mode | ⚐ ★|

 ⚑ &nbsp; Required argument.<br>
⚐ &nbsp; To write to the console, use the character `-` as the value of _OUT_; otherwise, _OUT_ must be the name of a file where the output should be written.<br>
★ &nbsp; Has no effect if `eprints2archives` is being run with [Python optimization](https://docs.python.org/3/using/cmdline.html#cmdoption-o) enabled.


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


## Known issues and limitations

Some services impose severe rate limits on URL submissions, and there  is nothing that `eprints2archives` can do about it.  For example, at the time of this writing, [Archive.Today](https://archive.today) only allows 6 URLs to be submitted every 5 minutes.  If you plan on sending a large number of URLs, it may be more convenient to use a separate `eprints2archives` process with the `-d` option to select only one destination, and let it run in its own terminal window.


## Relationships to other similar tools

Other tools exist for sending content to web archives; some are general-purpose enough that they could be used to send EPrints server contents to web archives.  To the author's knowledge, `eprints2archives` is the only software designed specifically to work with EPrints servers to send content to multiple archiving destinations.

The Internet Archive itself [offers multiple ways of submitting content](https://help.archive.org/hc/en-us/articles/360001513491-Save-Pages-in-the-Wayback-Machine), including sending URLs via email, using a browser extension, and the simple-to-use [Save Page Now](https://web.archive.org/save/). The latter offers the option of capturing pages more deeply if the user is logged in to their Internet Archive (IA) account.  By contrast, `eprints2archives` can send the entire content of an EPrints server in one go, without requiring the user to have an IA account.

Many institutions use IA's [Archive-It](https://help.archive.org/hc/en-us/articles/360004651612-Archive-It-Information) service, and Archive-It can be used to crawl EPrints server pages.  In principle, this can capture an EPrints server site more fully than `eprints2archives` because `eprints2archives` only follows specific common links and pages, and misses any custom data views or additional pages (including "About" pages) that may be present on an EPrints server.  Nevertheless, `eprints2archives` can be useful even for sites that use Archive-It because it asks the EPrints server itself about its records and gets URLs (such as the `official_url` values) that may not be mentioned in the EPrints record views (and thus would be missed by Archive-It's "on the outside looking in" approach).  Since `eprints2archives` by default does not send URLs that are already present in archiving destinations, it can be used in conjunction with Archive-It as a secondary or backup scheme.

A number of third-party archiving tools exist for sending URLs to web archives.  One of the few that can target other archives besides IA is [Archive Now](https://github.com/oduwsdl/archivenow).  It partly inspired the creation of `eprints2archives`.  Archive Now's code for interfacing to web archives also served as initial starting points for figuring out to do the same in `eprints2archives`.  In terms of functionality, `eprints2archives` is more special-purpose (being aimed at extracting content from EPrints servers), and has more advanced capabilities such as handling rate limits, pause-and-retry handling of errors, and use of parallel threads.

Most archiving tools work only with the [Internet Archive's Wayback Machine](https://archive.org/web/). The Ruby-based [WaybackArchiver](https://github.com/buren/wayback_archiver) can crawl a site given a URL or a sitemap and then send URLs to IA; however, it does not appear to attempt to recover from as many error situations as `eprints2archives`, and of course, lacks its EPrints-specific features.  [Waybackpy](https://github.com/akamhy/waybackpy) is a simpler tool designed to interact with IA, and while it can submit URLs to be saved, it lacks other capabilities of `eprints2archives` such as automatically handling rate limits and error retries, as well as not being designed for extracting content from EPrints servers.  Some other similar but much simpler and less advanced IA-specific tools include [savepagenow](https://github.com/pastpages/savepagenow), [ia_wayback](https://github.com/bitsgalore/iawayback), [Wayback Sitemap Archive](https://github.com/plibither8/wayback-sitemap-archive), [Save to the Wayback Machine](https://github.com/VerifiedJoseph/Save-to-the-Wayback-Machine), and the [wayback api](https://github.com/httpreserve/wayback) from HTTPreserve.

[archive.today](https://github.com/dhamaniasad/archive.today) is one of the few tools for working with archives other than IA.  It is a simple command-line tool for sending content to and downloading from Archive.Today.


## Getting help

If you find an issue, please submit it in [the GitHub issue tracker](https://github.com/caltechlibrary/eprints2archives/issues) for this repository.


## Contributing

We would be happy to receive your help and participation with enhancing `eprints2archives`!  Please visit the [guidelines for contributing](CONTRIBUTING.md) for some tips on getting started.


## License

Software produced by the Caltech Library is Copyright (C) 2020&ndash;2023, Caltech.  This software is freely distributed under a BSD/MIT type license.  Please see the [LICENSE](LICENSE) file for more information.


## Authors and history

This program was initially written in mid-2020, in response to discussions in Caltech's [Digital Library Development](https://www.library.caltech.edu/staff?&field_directory_department_name=Digital%20Library%20Development) group.

The TimeMap parsing code in [eprints2archives/services/timemap.py](eprints2archives/services/timemap.py) originally came from the [Off-Topic Memento Toolkit](https://github.com/oduwsdl/off-topic-memento-toolkit), by Shawn M. Jones, as it existed on 2020-07-29.  The OTMT code is made available according to the MIT license.  Acknowledgments and additional information are provided in the file header of [eprints2archives/services/timemap.py](eprints2archives/services/timemap.py).

The algorithm and some code for interacting with [Archive.Today](https://archive.today) were borrowed from [ArchiveNow](https://github.com/oduwsdl/archivenow), a tool developed by [Web Science and Digital Libraries Research Group at Old Dominion University](https://ws-dl.blogspot.com).  The authors and contributors of the specific code file used ([is_handler.py](https://github.com/oduwsdl/archivenow/blob/master/archivenow/handlers/is_handler.py)), as it existed on 2020-07-17, were [Mohamed Aturban](https://github.com/maturban), [Shawn M. Jones](https://github.com/shawnmjones), [veloute](https://github.com/veloute), and [evil-wayback](https://github.com/evil-wayback).  ArchiveNow is made available according to the MIT license.  Acknowledgments and additional information are provided in the file header of [eprints2archives/services/archivetoday.py](eprints2archives/services/archivetoday.py).

`eprints2archives` makes use of numerous open-source packages, without which it would have been effectively impossible to develop `eprints2archives` with the resources we had.  We want to acknowledge this debt.  In alphabetical order, the packages are:

* [aenum](https://pypi.org/project/aenum/) &ndash; advanced enumerations for Python
* [appdirs](https://github.com/ActiveState/appdirs) &ndash; determine the appropriate app dirs on different OSes
* [bun](https://github.com/caltechlibrary/bun) &ndash; a set of basic user interface classes and functions
* [CommonPy](https://github.com/caltechlibrary/commonpy) &ndash; a collection of commonly-useful Python functions
* [cssselect](https://pypi.org/project/cssselect/) &ndash; `lxml` add-on to parse CSS3 selectors 
* [dateparser](https://pypi.org/project/dateparser/) &ndash; parse dates in almost any string format
* [h2](https://pypi.org/project/h2) &ndash; HTTP/2 support library used by [HTTPX](https://www.python-httpx.org)
* [httpx](https://www.python-httpx.org) &ndash; Python HTTP client library that supports HTTP/2
* [humanize](https://github.com/jmoiron/humanize) &ndash; helps write large numbers in a more human-readable form
* [keyring](https://github.com/jaraco/keyring) &ndash; access the system keyring service from Python
* [lxml](https://lxml.de) &ndash; an XML parsing library for Python
* [plac](http://micheles.github.io/plac/) &ndash; a command line argument parser
* [pydash](https://github.com/dgilland/pydash) &ndash; “kitchen sink of Python utility libraries for doing ‘stuff’” 
* [pypubsub](https://github.com/schollii/pypubsub) &ndash; a publish-and-subscribe message-passing library for Python
* [python-dateutil](https://pypi.org/project/python-dateutil/) &ndash; additional date parsing utilities
* [rich](https://rich.readthedocs.io/en/latest/) &ndash; library for writing styled text to the terminal
* [setuptools](https://github.com/pypa/setuptools) &ndash; library for `setup.py`
* [sidetrack](https://github.com/caltechlibrary/sidetrack) &ndash; simple debug logging/tracing package
* [stopit](https://pypi.org/project/stopit/) &ndash; raise asynchronous exceptions
* [tldextract](https://github.com/john-kurkowski/tldextract) &ndash; module to parse domains from URLs
* [urllib3](https://urllib3.readthedocs.io/en/latest/) &ndash; HTTP client library for Python
* [validators](https://github.com/kvesteri/validators) &ndash; data validation package for Python


## Acknowledgments

The [vector artwork](https://thenounproject.com/term/upload/2800646/) of a cloud and arrow contained within the logo for this repository was created by [Vimal](https://thenounproject.com/vimalraj2/) from the Noun Project.  It is licensed under the Creative Commons [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/) license.

The icons of operating systems used on this page were obtained from [iconsdb.com](https://www.iconsdb.com/gray-icons/linux-icon.html). They are distributed under a [Creative Commons Attribution-NoDerivs 3.0](https://creativecommons.org/licenses/by-nd/3.0/) license.

This work was funded by the California Institute of Technology Library.

<div align="center">
  <br>
  <a href="https://www.caltech.edu">
    <img width="100" height="100" src="https://raw.githubusercontent.com/caltechlibrary/eprints2archives/main/.graphics/caltech-round.png">
  </a>
</div>
