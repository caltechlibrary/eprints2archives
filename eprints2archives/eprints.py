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
import httpx
from   lxml import etree, html
import os
from   os import path
import shutil
import ssl
import validators

from .data_helpers import parse_datetime, unique
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

    def __init__(self, given_url, user, password):
        if __debug__: log(f'creating EPrintsServer object for {given_url}')
        # For efficiency, create an httpx Client object and reuse it (since
        # we're always talking to the same EPrints server).  Note about SSL
        # security settings: EPrints, being an older system, is often run on
        # older servers with older SSL support. The following enables SSL3.0
        # support, which I found is needed for EPrints servers that I tried.
        # C.f. https://docs.python.org/3/library/ssl.html#ssl.SSLContext
        ssl_config = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_config.options &= ~ssl.OP_NO_SSLv3
        timeout = httpx.Timeout(connect = 30, read = 30, write = 30)
        self._client = httpx.Client(timeout = timeout, http2 = True, verify = ssl_config)

        # Do this after the above b/c it needs the network client to be set up.
        self._api_url    = self._canonical_endpoint_url(given_url)

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

    def api_url(self):
        '''Return the canonical REST API URL for this server.'''
        return self._api_url


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


    def top_level_urls(self):
        '''Return a list of the top-level URLs of this EPrints server.

        This returns all URLs found by examining the HTML of the front page
        of the server and then keeping only those located on the server and
        not certain special URLs like CGI, css, relative links, and so on.
        '''
        top_page = self._base_url
        if __debug__: log(f'getting from page from {self._base_url}')
        (response, error) = self._net('get', top_page)
        if error:
            if __debug__: log(f'got {type(error)} error for {top_page}')
            return []
        # Scrape the HTML.
        doc = html.fromstring(response.text)
        doc.make_links_absolute(top_page)
        # Extract unique URLs, filtering out stuff we don't want.
        skip = ['/cgi', '#', 'css']
        keep = lambda u: u and u.startswith(top_page) and not any(x in u for x in skip)
        urls = unique(filter(keep, [x.get('href') for x in doc.cssselect('a')]))
        if __debug__: log(f'found {len(urls)} top-level URLs: {urls}')
        return urls


    def view_urls(self, id_subset = None):
        '''Return a list of URLs corresponding to pages under /view.

        If parameter value "id_subset" is not None, it is taken to be a list
        of EPrint id's that is used to limit the pages under to be
        returned.  The values return will only consist of URLs of the form
        /view/X/N, where X is a subpage under /view and N is the number of a
        record found "id_subset", if such URLs exist on the server.  Otherwise,
        if no "id_subset" list is given, all /view/ids/N pages are returned
        (again, if they exist), along with all other pages found under /view
        and the pages one level below each of those. (E.g., /view/year,
        /view/year/yyyy.html, /view/person-az, /view/person-az/a.html, etc.)
        '''
        # We need /view in any case.
        view_base = self._base_url + '/view/'
        (response, error) = self._net('get', view_base)
        if error:
            if __debug__: log(f'got {type(error)} error for {view_base}')
            return []

        # Scrape the HTML to find the block of links to pages under /view.
        doc = html.fromstring(response.text)
        doc.make_links_absolute(view_base)
        view_urls = set(x.get('href') for x in doc.cssselect('div.ep_view_browse_list li a'))
        if __debug__: log(f'found {len(view_urls)} URLs under /view')

        # Iterate over each page under /view, to get links to their subpages.
        subpage_urls = set()
        for subpage in view_urls:
            (response, error) = self._net('get', subpage)
            if error:
                if __debug__: log(f'got {type(error)} error for {subpage}')
                continue
            doc = html.fromstring(response.text)
            doc.make_links_absolute(subpage)
            subpage_urls |= set(x.get('href') for x in doc.cssselect('div.ep_view_menu li a'))
        if __debug__: log(f'collected {len(subpage_urls)} /view subpage URLs')

        # If id_subset is given, we ONLY keep pages of the form /view/X/N.html
        # where N is an identifier in id_subset.
        if id_subset:
            kept_urls = set()
            for id in id_subset:
                for url in subpage_urls:
                    # Year pages will have the form N.html too.  Skip them.
                    if '/view/year' not in url and url.endswith(f'/{id}.html'):
                        if __debug__: log(f'keeping {id}.html')
                        kept_urls.add(url)
                        break
            if __debug__: log(f'returning subset {len(kept_urls)} /view/X/N.html URLs')
            return list(kept_urls)
        else:
            # No id_subset, so we return everything.
            view_urls |= subpage_urls
            if __debug__: log(f'returning {len(view_urls)} /view subpage URLs')
            return list(view_urls)


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
            (response, error) = self._net('head', url)
            if error:
                if __debug__: log(f'failed to get /id from server for {id_or_record}')
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
            (response, error) = self._net('head', url)
            if error:
                if __debug__: log(f'failed to get /id from server for {id_or_record}')
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
            response = self._get_authenticated(f'/eprint/{eprintid}.xml')
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
                    response = self._get_authenticated(field_url)
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

    def _net(self, method, url):
        '''Make a network call using our preconfigured client.'''
        return net(method, url, client = self._client)


    def _canonical_endpoint_url(self, url):
        '''Return the canonical REST API URL.'''
        # We remove any ending /eprint because we add it separately when needed.
        # For convenience, we add /rest if the user forgot.  Ditto for https://.
        if not scheme(url):
            # Is the server at https://, or http://?
            if __debug__: log(f'trying to add https or http to {url}')
            for prefix in ['https://', 'http://']:
                candidate = prefix + url
                try:
                    (response, error) = self._net('head', candidate)
                except:
                    continue
                url = candidate
                break
        if url.endswith('/'):
            url = url[0 : -1]
        if url.endswith('/eprint'):
            url = url[0 : url.rfind('/eprint')]
        if not url.endswith('/rest'):
            url += '/rest'
        if not validators.url(url):
            alert_fatal(f'The given API URL appears invalid: {url}')
            raise CannotProceed(ExitCode.bad_arg)
        return url


    def _get_authenticated(self, op):
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

        (response, error) = self._net('get', endpoint)
        if response and not error:
            return response
        else:
            if __debug__: log(f'got {type(error)} error for {url}')
            raise error


    def _eprints_raw_index(self):
        if __debug__: log(f'asking {self._hostname} for index of records')
        response = self._get_authenticated('/eprint')
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
