'''
eprints2archives -- send EPrints pages to Internet Archive and other archives

Authors
-------

Michael Hucka <mhucka@caltech.edu> -- Caltech Library

Copyright
---------

Copyright (c) 2020 by the California Institute of Technology.  This code
is open-source software released under a 3-clause BSD license.  Please see the
file "LICENSE" for more information.
'''

from os import path
import sys

# Set module-level dunder variables like __version__
# .............................................................................
# The following code reads from either ../setup.cfg (if running from a source
# directory) or data/setup.cfg (if running from an application created by
# PyInstaller using our PyInstaller configuration scheme), or the installed
# package metadata (if installed normally).  It reads config vars and sets the
# corresponding module-level variables with '__' surrounding their names.

keys = ['version', 'description', 'license', 'url', 'keywords',
        'author', 'author_email', 'maintainer', 'maintainer_email']

this_module = sys.modules[__package__]
module_path = this_module.__path__[0]
setup_cfg = path.join(module_path, 'data/setup.cfg')
if not path.exists(setup_cfg):
    setup_cfg = path.join(path.dirname(__file__), '..', 'setup.cfg')

if path.exists(setup_cfg):
    # If setup.cfg is directly available, use that.
    from setuptools.config import read_configuration
    conf_dict = read_configuration(setup_cfg)
    conf = conf_dict['metadata']
    for name in [key for key in keys if key in conf]:
        variable_name = '__' + name + '__'
        setattr(this_module, variable_name, str(conf[name]))
else:
    # If we are not running from the source directory, we read from the
    # package metadata file created by setuptools.
    import distutils.dist, io, pkg_resources
    pkg = pkg_resources.get_distribution(__package__)
    metadata = distutils.dist.DistributionMetadata()
    metadata.read_pkg_file(io.StringIO(pkg.get_metadata(pkg.PKG_INFO)))
    for name in [key for key in keys if hasattr(metadata, key)]:
        variable_name = '__' + name + '__'
        setattr(this_module, variable_name, getattr(metadata, name))


# Miscellaneous utilities.
# .............................................................................

def print_version():
    this_module = sys.modules[__package__]
    print(f'{this_module.__name__} version {this_module.__version__}')
    print(f'Authors: {this_module.__author__}')
    print(f'URL: {this_module.__url__}')
    print(f'License: {this_module.__license__}')
