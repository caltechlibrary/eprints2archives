Change log for REPOSITORY
=========================

Version 1.2.0
-------------

* In addition to the record pages, `eprints2archives` now also harvests general URLs from the server, including the top-level URL and `/view` and 2 levels of pages underneath it.  However, if a subset of records is requested, only gets those particular `/view/X/N.html` pages rather than all pages under `/view/X/`.
* Minor improvements to some of the run-time status messages.
* More progress bars!
* Improvements to debug logging.
* Some internal code refactoring.


Version 1.1.0
--------------

* Include the top-level server URL among the URLs sent to archives, as well as `/view` and two levels of pages under `/view`.
* Make sure the set of URLs sent to archives is unique.
* Improve debug logging from low-level network module.
* Clarify some things in the README file.


Version 1.0.0
-------------

First working version.  Supports sending EPrints pages to the [Internet Archive](https://archive.org/web/) and [Archive.Today](https://archive.today).  Runs with parallel threads and handles rate limits automatically.  Currently implements a command-line interface only.
