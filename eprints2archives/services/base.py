'''
base.py: base class definition for archive services.

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''


# Class definitions.
# .............................................................................
# Basics for the __eq__ etc. methods came from
# https://stackoverflow.com/questions/1061283/lt-instead-of-cmp

class TextRecognition(object):

    # The following methods need to be overridden by subclasses.
    # .........................................................................

    def __init__(self):
        pass


    def name(self):
        '''Returns the canonical internal name for this service.'''
        pass


    def name_color(self):
        '''Returns a color code for this service.  See the color definitions
        in messages.py.'''
        pass


    def send(self, url):
        '''Send the "url" to the service to be archived.'''
        pass


    # The rest of these methods are generic and don't need to be overridden.
    # .........................................................................

    def __str__(self):
        return self.name()


    def __repr__(self):
        return self.name()


    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not self.name() < other.name() and not other.name() < self.name()


    def __ne__(self, other):
        return not __eq__(self, other)


    def __lt__(self, other):
        return self.name() < other.name()


    def __gt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return other.name() < self.name()


    def __le__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not other.name() < self.name()


    def __ge__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not self.name() < other.name()
