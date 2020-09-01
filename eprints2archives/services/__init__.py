'''
eprints2archives interfaces to web archiving services.

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from enum import Enum

from .upload_status import ServiceStatus
from .internetarchive import InternetArchive
from .archivetoday import ArchiveToday


# Constants.
# .............................................................................

KNOWN_SERVICES = {
    'internetarchive' : InternetArchive(),
    'archivetoday'    : ArchiveToday(),
}

# Save this list to avoid recreating it all the time.
SERVICE_NAMES = sorted(KNOWN_SERVICES.keys())
SERVICE_OBJECTS = KNOWN_SERVICES.values()


# Exported functions.
# .............................................................................

def service_names():
    '''Return a list of the known service names.'''
    return SERVICE_NAMES


def service_interfaces():
    '''Return a list of objects that act as interfaces to services.'''
    return SERVICE_OBJECTS


def service_by_name(name):
    '''Return the object corresponding to the given service "name".

    If "name" is is not a known service name, the value None is returned.
    '''
    return KNOWN_SERVICES.get(name.lower(), None)
