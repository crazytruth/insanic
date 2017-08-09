import pkg_resources
__version__ = pkg_resources.get_distribution('insanic').version

from .app import Insanic
__all__ = ['__version__', 'Insanic']

