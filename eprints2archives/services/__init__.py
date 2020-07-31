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

from .internetarchive import InternetArchive
from .archivetoday import ArchiveToday
from .archivest import ArchiveST

KNOWN_SERVICES = {
    'internetarchive' : InternetArchive(),
    'archive.st'      : ArchiveST(),
    'archive.today'   : ArchiveToday(),
}

# Save this list to avoid recreating it all the time.
SERVICE_NAMES = sorted(KNOWN_SERVICES.keys())
SERVICE_OBJECTS = KNOWN_SERVICES.values()

def service_names():
    return SERVICES_NAMES

def service_interfaces():
    return SERVICE_OBJECTS

def service_by_name(name):
    if name.lower() in SERVICE_NAMES:
        return KNOWN_SERVICES[name.lower()]
    else:
        return None
