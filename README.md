eprints2archives<img width="100px" align="right" src=".graphics/eprints2archives-icon.svg">
================

A program to obtain records from an EPrints server and send them to the [Internet Archive](https://archive.org/web/) and other archiving sites.

[![License](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg?style=flat-square)](https://choosealicense.com/licenses/bsd-3-clause)
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

One approach to improve preservation and distribution of EPrints server contents is to ask web archiving sites such as the [Internet Archive](https://archive.org/web/) and [Archive.today](http://archive.vn) to archive the public web pages for a given EPrints server.  _Eprints2archives_ is a self-contained program that does just that.  It contacts a given EPrints server, obtains the list of documents it servers (optionally modified based on selectors such as date), and sends the URLs to archiving sites.  The program is written in Python 3 and works over a network using an EPrints server's REST API.


Installation
------------

_Forthcoming_
 

Usage
-----

_Forthcoming_


Known issues and limitations
----------------------------

_Forthcoming_


Getting help
------------

_Forthcoming_


Contributing
------------

_Forthcoming_


License
-------

Software produced by the Caltech Library is Copyright (C) 2020, Caltech.  This software is freely distributed under a BSD/MIT type license.  Please see the [LICENSE](LICENSE) file for more information.


Authors and history
---------------------------

[Mike Hucka](https://github.com/mhucka) began writing this program in mid-2020, in response to discussions with colleagues in Caltech's [Digital Library Development](https://www.library.caltech.edu/staff?&field_directory_department_name=Digital%20Library%20Development) group.

The TimeMap parsing code in [eprints2archives/services/timemap.py](eprints2archives/services/timemap.py) originally came from the [Off-Topic Memento Toolkit](https://github.com/oduwsdl/off-topic-memento-toolkit), by Shawn M. Jones, as it existed on 2020-07-29.  The OTMT code is made available according to the MIT license.  Acknowledgements and additional information are provided in the file header of [eprints2archives/services/timemap.py](eprints2archives/services/timemap.py).


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
