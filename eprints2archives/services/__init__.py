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

from .internetarchive import SendToInternetArchive
from .archivetoday import SendToArchiveToday
from .archivest import SendToArchiveST

KNOWN_SERVICES = {
    'internetarchive' : SendToInternetArchive,
    'archive.st'      : SendToArchiveST,
    'archive.today'   : SendToArchiveToday,
}

# Save this list to avoid recreating it all the time.
SERVICES_LIST = sorted(KNOWN_SERVICES.keys())

def services_list():
    return SERVICES_LIST
