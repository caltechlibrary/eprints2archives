'''
timemap.py: parse TimeMaps

This file was originally timemap.py from the Off-Topic Memento Toolkit,
https://github.com/oduwsdl/off-topic-memento-toolkit/blob/master/otmt/timemap.py
retrieved from GitHub on 2020-07-29.  The git commit hash at the time I copied
the file was e714c8ad3c41221b83b24fda1979844d03d83726.

The license for OTMT at the time timemap.py was copied was the MIT license,
https://github.com/oduwsdl/off-topic-memento-toolkit/blob/master/LICENSE.txt

Authors (original)
------------------

Shawn M. Jones <jones.shawn.m@gmail.com> -- Old Dominion University

Authors (subsequent modifications)
----------------------------------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library
'''

from   copy import deepcopy
from   datetime import datetime
import requests

from   ..exceptions import *


def timemap_as_dict(timemap_text, skip_errors = False):
    '''A function to convert the link format TimeMap text into a Python
    dictionary that closely resembles the JSON specified at:
    http://mementoweb.org/guide/timemap-json/

    There is one difference: the value of the datetime attribute is
    an actual Python datetime object.

    One can set skip_errors to True in order to skip errors in processing the
    TimeMap, but use with caution as it can lead to unpredictable behavior.
    '''

    def process_local_dict(local_dict, working_dict):
        first = False
        last = False

        for uri in local_dict:

            relation = local_dict[uri]["rel"]

            if relation == "original":
                working_dict["original_uri"] = uri

            elif relation == "timegate":
                working_dict["timegate_uri"] = uri

            elif relation == "self":
                working_dict["timemap_uri"] = {}
                working_dict["timemap_uri"]["link_format"] = uri

            elif "memento" in relation:
                working_dict.setdefault("mementos", {})

                if "first" in relation:
                    working_dict["mementos"]["first"] = {}
                    working_dict["mementos"]["first"]["uri"] = uri
                    first = True

                if "last" in relation:
                    working_dict["mementos"]["last"] = {}
                    working_dict["mementos"]["last"]["uri"] = uri
                    last = True

                working_dict["mementos"].setdefault("list", [])

                local_memento_dict = {
                    "datetime": None,
                    "uri": uri
                }

            if "datetime" in local_dict[uri]:

                mdt = datetime.strptime(local_dict[uri]["datetime"],
                    "%a, %d %b %Y %H:%M:%S GMT")

                local_memento_dict["datetime"] = mdt

                working_dict["mementos"]["list"].append(local_memento_dict)

                if first:
                    working_dict["mementos"]["first"]["datetime"] = mdt

                if last:
                    working_dict["mementos"]["last"]["datetime"] = mdt

        return working_dict


    dict_timemap = {}

    # current_char = ""
    uri = ""
    key = ""
    value = ""
    local_dict = {}
    state = 0
    charcount = 0

    for character in timemap_text:
        charcount += 1

        if state == 0:

            local_dict = {}
            uri = ""

            if character == '<':
                state = 1
            elif character.isspace():
                pass
            else:
                if not skip_errors:
                    raise CorruptedContent(
                        "issue at character {} while looking for next URI"
                        .format(charcount))

        elif state == 1:

            if character == '>':
                # URI should be saved by this point
                state = 2
                uri = uri.strip()
                local_dict[uri] = {}
            else:
                uri += character

        elif state == 2:

            if character == ';':
                state = 3

            elif character.isspace():
                pass

            else:
                if not skip_errors:
                    raise CorruptedContent(
                        "issue at character {} while looking for relation"
                        .format(charcount))

        elif state == 3:

            if character == '=':
                state = 4
            else:
                key += character

        elif state == 4:

            if character == ';':
                state = 3
            elif character == ',':
                state = 0

                process_local_dict(local_dict, dict_timemap)

            elif character == '"':
                state = 5
            elif character.isspace():
                pass
            else:
                if not skip_errors:
                    raise CorruptedContent(
                        "issue at character {} while looking for value"
                        .format(charcount))

        elif state == 5:

            if character == '"':
                state = 4

                key = key.strip()
                value = value.strip()
                local_dict[uri][key] = value
                key = ""
                value = ""

            else:
                value += character

        else:

            if not skip_errors:
                raise CorruptedContent(
                    "discovered unknown state while processing TimeMap")

    process_local_dict(local_dict, dict_timemap)

    return dict_timemap


def timemap_mementos(timemap_dict):
    '''Take a timemap as dict and return the list of mementos therein.'''
    if not isinstance(timemap_dict, dict):
        raise ValueError(f'Expected a dict but got {type(timemap_dict)}.')
    if 'mementos' in timemap_dict and 'list' in timemap_dict['mementos']:
        return timemap_dict['mementos']['list']
    else:
        return []
