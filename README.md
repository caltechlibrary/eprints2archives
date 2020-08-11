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

One way to improve preservation and distribution of EPrints server contents is to ask web archiving sites such as the [Internet Archive](https://archive.org/web/) to archive the public web pages for a given EPrints server.  _Eprints2archives_ is a self-contained program that does exactly that.  It contacts a given EPrints server, obtains the list of documents it serves (optionally modified based on selectors such as date), and sends the URLs to archiving sites.  The program is written in Python 3 and works over a network using an EPrints server's REST API.


Installation
------------

The instructions below assume you have a Python interpreter installed on your computer; if that's not the case, please first install Python and familiarize yourself with running Python programs on your system.

On **Linux**, **macOS**, and **Windows** operating systems, you should be able to install `eprints2archives` with [pip](https://pip.pypa.io/en/stable/installing/).  (If you don't have `pip` already installed on your computer, please seek out instructions for how to obtain it for your particular operating system.)  To install `eprints2archives` from the [Python package repository (PyPI)](https://pypi.org), run the following command:
```
python3 -m pip install eprints2archives --upgrade
```

As an alternative to getting it from PyPI, you can use `pip` to install `eprints2archives` directly from GitHub:
```sh
python3 -m pip install git+https://github.com/caltechlibrary/eprints2archives.git --upgrade
```

Assuming that the installation proceeds normally, on Linux and macOS systems, you should end up with a program called `eprints2archives` in a location normally searched by your terminal shell for commands.
 

Usage
-----

For help with usage at any time, run `eprints2archives` with the option `-h` (or `/h` on Windows).


Known issues and limitations
----------------------------

_Forthcoming_


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
* [Pypubsub]() &ndash; library to implement publish/subscribe mechanisms
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
