'''
data_helpers: data manipulation utilities
'''

import dateparser
import datetime


# Constants.
# .............................................................................

DATE_FORMAT = '%b %d %Y %H:%M:%S %Z'
'''Format in which lastmod date is printed back to the user. The value is used
with datetime.strftime().'''


# Functions.
# .............................................................................

# Based on http://stackoverflow.com/a/10824484/743730
def flatten(iterable):
    '''Flatten a list produced by an iterable.  Non-recursive.'''
    iterator, sentinel, stack = iter(iterable), object(), []
    while True:
        value = next(iterator, sentinel)
        if value is sentinel:
            if not stack:
                break
            iterator = stack.pop()
        elif isinstance(value, str):
            yield value
        else:
            try:
                new_iterator = iter(value)
            except TypeError:
                yield value
            else:
                stack.append(iterator)
                iterator = new_iterator


def ordinal(n):
    '''Print a number followed by "st" or "nd" or "rd", as appropriate.'''
    # Spectacular algorithm by user "Gareth" at this posting:
    # http://codegolf.stackexchange.com/a/4712
    return '{}{}'.format(n, 'tsnrhtdd'[(n/10%10!=1)*(n%10<4)*n%10::4])


def expand_range(text):
    '''Return individual numbers for a range expressed as X-Y.'''
    # This makes the range 1-100 be 1, 2, ..., 100 instead of 1, 2, ..., 99
    if '-' in text:
        range_list = text.split('-')
        range_list.sort(key = int)
        return [*map(str, range(int(range_list[0]), int(range_list[1]) + 1))]
    else:
        return text


def parse_datetime(string):
    '''Parse a human-written time/date string using dateparser's parse()
function with predefined settings.'''
    return dateparser.parse(string, settings = {'RETURN_AS_TIMEZONE_AWARE': True})
