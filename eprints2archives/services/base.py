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

class Service(object):

    label = ''
    name = ''
    color = ''

    def save(self, url):
        '''Send the "url" to the service to save it.'''
        pass


    def newest(self, url):
        '''Return the newest saved version of the content at "url".'''
        pass


    def oldest(self, url):
        '''Return the oldest saved version of the content at "url".'''
        pass


    def nearest(self, url):
        '''Return the closest saved version of the content at "url".'''
        pass


    # The rest of these methods are generic and don't need to be overridden.
    # .........................................................................

    def __str__(self):
        return self.name


    def __repr__(self):
        return self.name


    def __eq__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not self.name < other.name and not other.name < self.name


    def __ne__(self, other):
        return not __eq__(self, other)


    def __lt__(self, other):
        return self.name < other.name


    def __gt__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return other.name < self.name


    def __le__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not other.name < self.name


    def __ge__(self, other):
        if not isinstance(other, type(self)):
            return NotImplemented
        else:
            return not self.name < other.name
