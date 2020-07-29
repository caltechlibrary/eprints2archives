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
        if __debug__: log('creating EPrintsServer object for ', api_url)
        self._api_url    = api_url
        self._hostname   = hostname(self._api_url)
        self._user       = user
        self._password   = password
        # List of all record identifiers known to the server:
        self._index      = []
        # Cache of record XML objects obtained from the server:
        self._records    = {}


    def __str__(self):
        return self._hostname


    # Public methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def index(self, as_int = False):
        '''Return a list of all record identifiers from the server.  By
        default, the numbers are returned as strings, not ints, because the
        most common uses of the results end up using strings anyway.  However,
        if the parameter 'as_int' is set to True, the list will be returned
        as integers.'''

        # The raw index returned by EPrints is in XHTML format, like this:
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
        # We extract the identifiers by looping over the XML elements.

        if self._index:
            if __debug__: log('using cached copy of index')
        else:
            xml = etree.fromstring(self._eprints_raw_index())
            if __debug__: log("parsing raw EPrints index to get record id's")
            for node in xml.findall('.//{http://www.w3.org/1999/xhtml}a'):
                if 'href' in node.attrib and node.attrib['href'].endswith('xml'):
                    self._index.append(node.attrib['href'].split('.')[0])
        if self._index and as_int:
            if __debug__: log('returning list of identifiers as ints')
            return [int(x) for x in self._index]
        else:
            return self._index


    def record_xml(self, record_id, missing_ok):
        '''Return an XML object identified by the given record identifier.'''
        record_id = str(record_id)
        if record_id in self._records:
            if __debug__: log('returning cached XML for record {}', record_id)
            return self._records[record_id]

        if __debug__: log('getting XML for {} from server', record_id)
        try:
            response = self._get('/eprint/{}.xml'.format(record_id), missing_ok)
        except AuthenticationFailure as ex:
            # Our EPrints server sometimes returns with access forbidden for
            # specific records.  When ignoring missing entries, I guess it
            # makes sense to just flag them and move on.
            if missing_ok:
                warn(str(error) + ' for record {}'.format(record_id))
                self._records[record_id] = None
                return None
            else:
                raise error
        if response is None and missing_ok:
            warn('Server has no contents for record {}', record_id)
            self._records[record_id] = None
            return None
        xml = etree.fromstring(response.content)
        self._records[str(record_id)] = xml
        return xml


    def record_value(self, id_or_record, field, missing_ok):
        '''Return the value of 'field' of the record 'id_or_record'.  If
        'id_or_record' is a number (either as a string or an integer), this
        method will ask the server for the field value using the REST API;
        if 'id_or_record' is an XML object, then the value is looked up in the
        object itself.'''

        if isinstance(id_or_record, str) or isinstance(id_or_record, int):
            id_or_record = str(id_or_record)
            if id_or_record in self._records:
                # We have a copy of the XML for this one.  Use it.
                if __debug__: log('using cached copy of record {}', id_or_record)
                xml = self._records[id_or_record]
            else:
                # Contact the server.
                if __debug__: log('{} not cached -- asking server', id_or_record)
                field_url = '/eprint/' + id_or_record + '/' + field + '.txt'
                response = self._get(field_url, missing_ok)
                return response.text if response else ''
        else:
            xml = id_or_record
        return self._xml_field_value(xml, field)


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get(self, op, missing_ok = True):
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
        elif isinstance(error, NoContent) and missing_ok:
            return None
        else:
            raise error


    def _eprints_raw_index(self):
        if __debug__: log('asking {} for index of records', self._hostname)
        response = self._get('/eprint')
        if response and response.text and response.text.startswith('<?xml'):
            return response.content
        else:
            # This shouldn't happen.
            raise InternalError('Internal error processing server response')


    def _xml_field_value(self, xml, field):
        if xml is not None and etree.iselement(xml):
            node = xml.find('.//{' + _EPRINTS_XMLNS + '}' + field)
            return node.text if node != None else ''
        else:
            raise InternalError('Not an XML object: {}'.format(xml))
