#!/user/bin/env python
"""Extension for the `Sphinx`_ documentation engine. Programatically generates
tables describing command-line arguments for `Python`_ modules that use
:class:`~argparse.ArgumentParser` to parse arguments. These tables are then
inserted into descriptions generated by the ``:automodule:`` directive used by
the Sphinx `autodoc`_ extension.
"""

__author__ = "Joshua Griffin Dunn"
__date__ = "2015-06-09"
__version__ = "0.1.3"

#===============================================================================
# INDEX: extension setup
#===============================================================================
import types
import sphinx
from sphinxcontrib.argdoc.ext import noargdoc, post_process_automodule

_REQUIRED = ['sphinx.ext.autodoc',
             'sphinx.ext.autosummary',
            ]

def setup(app):
    """Set up :data:`sphinxcontrib.argdoc` extension and register it with `Sphinx`_
    
    Parameters
    ----------
    app
        Sphinx application instance
    """
    if isinstance(app,types.ModuleType):
        return

    metadata = { "version" : __version__
               }

    for ext in _REQUIRED:
        app.setup_extension(ext)
    
    app.connect("autodoc-process-docstring",post_process_automodule)
    app.add_config_value("argdoc_main_func","main","env")
    app.add_config_value("argdoc_save_rst",False,"env")
    app.add_config_value("argdoc_prefix_chars","-","env")

    app.add_event("argdoc-process-docstring")

    if sphinx.version_info >= (1,3,):
        return metadata
