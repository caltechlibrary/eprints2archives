Change log for eprints2archives
===============================

## Version 1.3.4

Changes in this version:
* Fix handling of occasionally unexpected timemap result from InternetArchive.
* Update versions of some dependencies in `requirements.txt`.


## Version 1.3.3

* Add requirement for a package imported by another requirement but that does not, for some reason, get imported properly when a clean virtual environment is created in the process of making pyz apps.
* Update all requirement versions to latest versions of packages. This was not done for over a year and it showed...
* Define `console_scripts` for setuptools to produce a better wrapper script.


## Version 1.3.2

* Fix a mixhandled exception when a server returns a code 500.
* Improve catching interrupts on Windows.
* Use [CommonPy](https://github.com/caltechlibrary/commonpy) network utilities, file utilities, and data utilities instead of internal copies.
* Use [Bun](https://github.com/caltechlibrary/bun) user interface code instead of internal copy. Also change some colors of messages printed by `eprints2archives`.
* Update internal imports and some requirements.
* Update copyright year.


## Version 1.3.1

* Use [Sidetrack](https://github.com/caltechlibrary/sidetrack) instead of internal `debug.py` version of the same.
* Internally, use different approach to recording version number and other metadata.
* Use updated release procedure codified in `Makefile`.


## Version 1.3.0

* Check that URLs obtained from EPrints records appear to be valid URLs, before trying to send them to web archives. (This is mostly to catch bad values in the `official_url` record field.)
* Be more careful about which `/view/X/N.html` pages are sent.
* Do a better job with HTTP code 400 from Internet Archive.
* Do some more internal network code refactoring.
* Add some more debug log statements.


## Version 1.2.2

* Retry network operations one time if get HTTP code 400.
* Internal network code refactoring.


## Version 1.2.1

* Add missing `requirements.txt` dependency for [`h2`](https://pypi.org/project/h2) package.
* Make parsing of malformed id ranges slightly more robust.
* Fix incorrect pluralization of an info message.
* Remove accidentally left-in invocation of `pdb` upon errors even if debugging not enabled.
* Edit the README.md file slightly.


## Version 1.2.0

* In addition to the record pages, `eprints2archives` now also harvests general URLs from the server, including the top-level URL and `/view` and 2 levels of pages underneath it.  However, if a subset of records is requested, only gets those particular `/view/X/N.html` pages rather than all pages under `/view/X/`.
* Internal changes allow it to use protocol HTTP/2, which was necessary to communicate with Archive.Today (because it appears to have stopped accepting save requests unless HTTP2 is used).
* Now tries to add `https://` or `http://` if the user forgets to provide it, and also removes `/eprint` and adds `/rest` if needed.  This makes it possible for the user to just provide a host name and `eprints2archives` will figure out the rest.
* Minor improvements to some of the run-time status messages.
* More progress bars!
* Improvements to debug logging.
* Improvements to README.md.
* Internal code refactoring.


## Version 1.1.0

* Include the top-level server URL among the URLs sent to archives, as well as `/view` and two levels of pages under `/view`.
* Make sure the set of URLs sent to archives is unique.
* Improve debug logging from low-level network module.
* Clarify some things in the README file.


## Version 1.0.0

First working version.  Supports sending EPrints pages to the [Internet Archive](https://archive.org/web/) and [Archive.Today](https://archive.today).  Runs with parallel threads and handles rate limits automatically.  Currently implements a command-line interface only.
