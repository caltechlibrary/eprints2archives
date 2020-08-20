Change log for REPOSITORY
=========================

Version 1.1.0
--------------

* Include the top-level server URL among the URLs sent to archives, as well as `/view` and pages under `/view`.
* Make sure the set of URLs sent to archives is unique.
* Improve debug logging from low-level network module.
* Clarify some things in the README file.


Version 1.0.0
-------------

First working version.  Supports sending EPrints pages to the [Internet Archive](https://archive.org/web/) and [Archive.Today](https://archive.today).  Runs with parallel threads and handles rate limits automatically.  Currently implements a command-line interface only.
