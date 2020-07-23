'''
eprints.py: EPrints-specific utilities

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2019 by the California Institute of Technology.  This code is
open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import codecs
from   collections import defaultdict
from   lxml import etree
import os
from   os import path
import shutil

from .data_helpers import parse_datetime
from .debug import log
from .exceptions import *
from .network import net, hostname
from .ui import warn, alert


# Constants.
# .............................................................................

_EPRINTS_XMLNS = 'http://eprints.org/ep2/data/2.0'
'''XML namespace used in EPrints XML output.'''


# Main functions.
# .............................................................................

class EPrintsServer():

    def __init__(self, api_url, user, password):
        self._api_url  = api_url
        self._hostname = hostname(self._api_url)
        self._user     = user
        self._password = password
        self._raw_index = []


    def __str__(self):
        return self._hostname


    # Public methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def records_list(self):
        xml = etree.fromstring(self._eprints_raw_index())
        # The content from this call is in XHTML format.  It looks like this, and
        # the following loop extracts the numbers from the <li> elements:
        #
        #   <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"
        #       "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
        #   <html xmlns="http://www.w3.org/1999/xhtml">
        #   <head>
        #     <title>EPrints REST: Eprints DataSet</title>
        #     <style type="text/css">
        #       body { font-family: sans-serif; }
        #     </style>
        #   </head>
        #   <body>
        #     <h1>EPrints REST: Eprints DataSet</h1>
        #   <ul>
        #   <li><a href='4/'>4/</a></li>
        #   <li><a href='4.xml'>4.xml</a></li>
        #   <li><a href='5/'>5/</a></li>
        #   <li><a href='5.xml'>5.xml</a></li>
        #   ...
        #
        numbers = []                    # Numbers as strings, not as ints.
        for node in xml.findall('.//{http://www.w3.org/1999/xhtml}a'):
            if 'href' in node.attrib and node.attrib['href'].endswith('xml'):
                numbers.append(node.attrib['href'].split('.')[0])
        return numbers


    def field_value(self, record_id, field_name):
        field_value_url = '/eprint/' + str(record_id) + '/' + field_name + '.txt'
        response = self._get(field_value_url)
        return response.text if response else ''


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get(self, op):
        if not self._api_url:
            return None

        url = self._api_url
        start = url.find('//')
        if start < 0:
            raise BadURL('Unable to parse "{}" as a normal URL'.format(url))
        if self._user and self._password:
            endpoint = url[:start + 2] + self._user + ':' + self._password + '@' + url[start + 2:] + op
        elif self._user and not self._password:
            endpoint = url[:start + 2] + self._user + '@' + url[start + 2:] + op
        else:
            endpoint = url[:start + 2] + url[start + 2:] + op

        (response, error) = net('get', endpoint)
        if not error and response:
            return response
        elif type(error) == NoContent:
            return None
        else:
            raise error


    def _eprints_raw_index(self):
        # Return cached value if we have one.
        if self._raw_index:
            if __debug__: log('returning cached raw index')
            return self._raw_index

        if __debug__: log('asking {} for index of records', self._hostname)
        response = self._get('/eprint')
        if response and response.text and response.text.startswith('<?xml'):
            self._raw_index = response.content
            return self._raw_index
        else:
            # This shouldn't happen.
            raise InternalError('Internal error processing server response')
