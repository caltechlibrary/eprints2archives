'''
upload_status.py: notification of the current status of an upload task

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code is
open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from enum import Enum

class Status(Enum):
    RUNNING      = 1                    # Currently uploading
    PAUSED_RATE  = 2                    # Paused due to hitting a rate limit
    PAUSED_ERROR = 3                    # Paused due to an error