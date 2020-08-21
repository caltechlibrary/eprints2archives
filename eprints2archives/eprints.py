'''
eprints.py: EPrints-specific utilities

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code is
open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

import codecs
from   collections import defaultdict
from   lxml import etree, html
import os
from   os import path
import shutil

from .data_helpers import parse_datetime
from .debug import log
from .exceptions import *
from .network import net, hostname, scheme, netloc
from .ui import warn, alert


# Constants.
# .............................................................................

_EPRINTS_XMLNS = 'http://eprints.org/ep2/data/2.0'
'''XML namespace used in EPrints XML output.'''


# Main functions.
# .............................................................................

class EPrintServer():

    def __init__(self, api_url, user, password):
        if __debug__: log('creating EPrintsServer object for ', api_url)
        self._api_url    = api_url
        self._protocol   = scheme(self._api_url)
        self._netloc     = netloc(self._api_url)
        self._hostname   = hostname(self._api_url)
        self._base_url   = self._protocol + '://' + self._netloc
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


    def front_page_url(self):
        '''Return the public front page URL of this EPrints server.'''
        return self._base_url


    def view_urls(self):
        '''Return a list of URLs corresponding to pages under /view.'''
        # Start with the top-level one
        view_base = self._base_url + '/view/'
        (response, error) = net('get', view_base, timeout = 10)
        if error:
            if __debug__: log(f'got {type(error)} error for {view_base}')
            return urls
        # Scrape the HTML to find the block of links to pages under /view.
        doc = html.fromstring(response.text)
        doc.make_links_absolute(view_base)
        view_urls = [x.get('href') for x in doc.cssselect('div.ep_view_browse_list li a')]
        if __debug__: log(f'found {len(view_urls)} URLs under /view')
        # Iterate over each page found to get the links to its subpages.
        # There will be many under /view/ids, one for each record, but they're
        # separate pages from the individual EPrint record pages.
        subpage_urls = []
        for view_subpage in view_urls:
            (response, error) = net('get', view_subpage, timeout = 10)
            if error:
                if __debug__: log(f'got {type(error)} error for {view_subpage}')
                continue
            doc = html.fromstring(response.text)
            doc.make_links_absolute(view_subpage)
            subpage_urls += [x.get('href') for x in doc.cssselect('div.ep_view_menu li a')]
        if __debug__: log(f'collected {len(subpage_urls)} /view subpage URLs')
        return view_urls + subpage_urls


    def eprint_id_url(self, id_or_record, verify = True):
        '''Return the main URL of the web page for the record on this server.

        This URL is for the page located at "https://.../id/eprint/N", where N
        is the eprint id of the record in question.  Note that EPrints servers
        typically also make the same records available from a URL of the form
        "https://.../N"; this other form is returned by the companion method
        eprint_page_url().

        The argument value for "id_or_record" can be either an identifier or
        an EPrint XML object (as a Python lxml.etree object).

        A server's index may report EPrint record identifiers for records that
        are not actually exposed to the public (e.g., because they've been
        deleted or otherwise marked as not publicly displayed).  Thus, given
        an identifier or even an XML record, it is possible to create URLs
        that do not lead to valid web pages.  Without additional knowledge
        about a specific server's conventions for public/private record
        visibility, the only way to know is to attempt to access the web page
        at the expected address.  Consequently, this method will attempt to do
        a network lookup on the URL, unless the parameter "verify" is given a
        value of False.
        '''
        if isinstance(id_or_record, (str, int)):
            url = f'{self._protocol}://{self._netloc}/id/eprint/{id_or_record}'
        else:
            eprintid = self._xml_field_value(id_or_record, 'eprintid')
            url = f'{self._protocol}://{self._netloc}/id/eprint/{eprintid}'
        if verify:
            (response, error) = net('head', url, timeout = 10)
            if error:
                return None
        return url


    def eprint_page_url(self, id_or_record, verify = True):
        '''Return the web page address for the record on this server.

        This URL is for the page located at "https://.../N", where N is the
        eprint id of the record in question.  Note that EPrints servers
        typically also make the same records available from a URL of the form
        "https://.../id/eprint/N"; this other form is returned by the companion
        method eprint_id_url().

        The argument value for "id_or_record" can be either an identifier or
        an EPrint XML object (as a Python lxml.etree object).

        A server's index may report EPrint record identifiers for records that
        are not actually exposed to the public (e.g., because they've been
        deleted or otherwise marked as not publicly displayed).  Thus, given
        an identifier or even an XML record, it is possible to create URLs
        that do not lead to valid web pages.  Without additional knowledge
        about a specific server's conventions for public/private record
        visibility, the only way to know is to attempt to access the web page
        at the expected address.  Consequently, this method will attempt to do
        a network lookup on the URL, unless the parameter "verify" is given a
        value of False.
        '''
        if isinstance(id_or_record, (str, int)):
            url = f'{self._protocol}://{self._netloc}/{id_or_record}'
        else:
            eprintid = self._xml_field_value(id_or_record, 'eprintid')
            url = f'{self._protocol}://{self._netloc}/{eprintid}'
        if verify:
            (response, error) = net('head', url, timeout = 10)
            if error:
                return None
        return url


    def eprint_xml(self, eprintid):
        '''Return an XML object identified by the given record identifier.'''
        eprintid = str(eprintid)
        if eprintid in self._records:
            if __debug__: log(f'returning cached XML for record {eprintid}')
            return self._records[eprintid]

        if __debug__: log(f'getting XML for {eprintid} from server')
        try:
            response = self._get(f'/eprint/{eprintid}.xml')
        except Exception as ex:
            # Our EPrints server sometimes returns with access forbidden for
            # specific records.  Our caller may simply move on, so we store
            # a value before bubbling up the exception.
            if __debug__: log(f'{str(ex)} for {eprintid}')
            self._records[eprintid] = None
            raise ex
        if response is None:
            self._records[eprintid] = None
            return None
        xml = etree.fromstring(response.content)
        self._records[eprintid] = xml
        return xml


    def eprint_field_value(self, id_or_record, field):
        '''Return the value of 'field' of the record 'id_or_record'.  If
        'id_or_record' is a number (either as a string or an integer), this
        method will ask the server for the field value using the REST API;
        if 'id_or_record' is an XML object, then the value is looked up in the
        object itself.'''

        if isinstance(id_or_record, (str, int)):
            id_or_record = str(id_or_record)
            if field == 'eprintid':
                # Data lookups are unnecessary since we have the id already.
                # This case is here to provide a uniform calling experience.
                return id_or_record
            elif id_or_record in self._records:
                # We have a copy of the XML for this one.  Use it.
                if __debug__: log(f'using cached copy of record {id_or_record}')
                xml = self._records[id_or_record]
            else:
                # Contact the server.
                if __debug__: log(f'{id_or_record} not cached -- asking server')
                field_url = f'/eprint/{id_or_record}/{field}.txt'
                try:
                    response = self._get(field_url)
                except NoContent as ex:
                    if __debug__: log(f'No content for {field} in {id_or_record}')
                    return None
                except AuthenticationFailure as ex:
                    if __debug__: log(f'Auth failure for {field} in {id_or_record}')
                    return None
                except Exception as ex:
                    if __debug__: log(f'{str(ex)} for {field} in {id_or_record}')
                    raise
                if __debug__: log(f'got response: {response.text}')
                return response.text if response and response.text != '' else None
        else:
            xml = id_or_record
        value = self._xml_field_value(xml, field)
        if __debug__: log(f'obtained value: {value}')
        return value


    # Internal methods ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    def _get(self, op):
        if not self._api_url:
            return None

        url = self._api_url
        start = url.find('//')
        if start < 0:
            raise BadURL(f'Unable to parse "{url}" as a normal URL')
        if self._user and self._password:
            endpoint = url[:start + 2] + self._user + ':' + self._password + '@' + url[start + 2:] + op
        elif self._user and not self._password:
            endpoint = url[:start + 2] + self._user + '@' + url[start + 2:] + op
        else:
            endpoint = url[:start + 2] + url[start + 2:] + op

        (response, error) = net('get', endpoint)
        if not error and response:
            return response
        else:
            if __debug__: log(f'got {type(error)} error for {url}')
            raise error


    def _eprints_raw_index(self):
        if __debug__: log(f'asking {self._hostname} for index of records')
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
            raise InternalError(f'Not an XML object: {xml}')
