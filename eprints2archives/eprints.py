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
from .network import net
from .ui import warn, alert


# Constants.
# .............................................................................

_EPRINTS_XMLNS = 'http://eprints.org/ep2/data/2.0'
'''XML namespace used in EPrints XML output.'''


# Main functions.
# .............................................................................

def eprints_api(url, op, user, password):
    '''Return a full EPrints API URL, complete with user & password, and ending
    with an operation string given by 'op'.'''
    if not url:
        return ''
    start = url.find('//')
    if start < 0:
        raise BadURL('Unable to parse "{}" as a normal URL'.format(url))
    if user and password:
        return url[:start + 2] + user + ':' + password + '@' + url[start + 2:] + op
    elif user and not password:
        return url[:start + 2] + user + '@' + url[start + 2:] + op
    else:
        return url[:start + 2] + url[start + 2:] + op


def eprints_raw_index(base_url, user, password):
    url = eprints_api(base_url, '/eprint', user, password)
    (response, error) = net('get', url)
    if not error and response and response.text:
        if response.text.startswith('<?xml'):
            return response.content
    return None


def eprints_records_list(raw_list):
    if not raw_list:
        # This shouldn't happen.
        raise InternalError('Internal error processing server response')
    xml = etree.fromstring(raw_list)
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
    numbers = []
    for node in xml.findall('.//{http://www.w3.org/1999/xhtml}a'):
        if 'href' in node.attrib and node.attrib['href'].endswith('xml'):
            numbers.append(node.attrib['href'].split('.')[0])
    return numbers


def eprints_xml(number, base_url, user, password, missing_ok):
    url = eprints_api(base_url, '/eprint/{}.xml'.format(number), user, password)
    (response, error) = net('get', url)
    if error:
        if isinstance(error, NoContent):
            if missing_ok:
                warn('Server has no contents for record number {}', number)
                return None
            else:
                raise error
        elif isinstance(error, ServiceFailure) or isinstance(error, AuthenticationFailure):
            # Our EPrints server sometimes returns with access forbidden for
            # specific records.  When ignoring missing entries, I guess it
            # makes sense to just flag them and move on.
            if missing_ok:
                alert(str(error) + ' for record number {}'.format(number))
                return None
            else:
                raise error
        else:
            raise error
    return etree.fromstring(response.content)


def eprints_lastmod(xml):
    lastmod_elem = xml.find('.//{' + _EPRINTS_XMLNS + '}lastmod')
    return parse_datetime(lastmod_elem.text)


def eprints_status(xml):
    status = xml.find('.//{' + _EPRINTS_XMLNS + '}eprint_status')
    return status.text if status != None else ''


def eprints_documents(xml):
    files = []
    # Ignore documents that are derived versions of original docs. These are
    # thumbnails and the indexcodes.txt file.
    for document in xml.findall('.//{' + _EPRINTS_XMLNS + '}document'):
        url = document.find('.//{' + _EPRINTS_XMLNS + '}url')
        if url == None:
            if hasattr(document, 'attrib'):
                if __debug__: log('Ignoring doc with no file: {}', document.attrib['id'])
            else:
                if __debug__: log('Ignoring document {}', document)
            continue
        if eprints_derived_file(document):
            if __debug__: log('Ignoring derived file {}', url.text)
        else:
            files.append(url.text)
    return files


def eprints_derived_file(document):
    for rel in document.findall('.//{' + _EPRINTS_XMLNS + '}relation'):
        for type in rel.findall('.//{' + _EPRINTS_XMLNS + '}type'):
            if type.text == 'http://eprints.org/relation/isVolatileVersionOf':
                return True
    return False


def eprints_record_id(xml):
    node = xml.find('.//{' + _EPRINTS_XMLNS + '}eprint')
    return node.attrib['id'] if 'id' in node.attrib else ''


def eprints_official_url(xml):
    node = xml.find('.//{' + _EPRINTS_XMLNS + '}official_url')
    # Do not remove the explicit test for None below.
    return node.text if node != None else ''


def write_record(number, xml, dir_prefix, dir_path):
    xml_file_name = dir_prefix + str(number) + '.xml'
    encoded = etree.tostring(xml, encoding = 'UTF-8', method = 'xml')
    file_path = path.join(dir_path, xml_file_name)
    if __debug__: log('Writing file {}', file_path)
    with codecs.open(file_path, 'w', 'utf-8') as file:
        file.write("<?xml version='1.0' encoding='utf-8'?>\n")
        file.write(encoded.decode().rstrip() + '\n')
