import importlib
import os
import types
import sys

from sanic.config import DEFAULT_CONFIG

from insanic.conf import global_settings
from insanic.functional import empty
from insanic.log import logger

INSANIC_PREFIX = 'INSANIC_'


class BaseConfig:
    LOGO = """
                                      ***********.
                                  **********************
                                          *******./@@@&(@@@@@@((((@/ (
                                              ** @@#&@%@@@@/@@@#@@@*@@@       __________________________
                             *****,             @@@@@,   % @@@@&@,,*@@@.     /                           \\
                         *******************  #@ /. @@@ @@&&@@@ @@@@@@@*(   |   Gotta go insanely fast !  |
                         *,  ,************** @@/@ , @@@@@&  @@@@ @@@@ @@@   | ____________________________/
                             ,,****,      .** ,&@# &@/%  &/@@@.(*@@@..*@ @  |/
                     ,*****************         @@@ @   . @@@.@&&@(&   @,
                                ,************   .@@@@ @@%@@,         ./@
                     ,                   .*******  @@%@@. #@ @@ @ &  %@@
                          *********,          .****   #@*@@&&&&&@@*@@@
                                 ,******,           * *** #@@@@@@@@@@@@@
                                         .*,          * ******
                             ,***************,   ,****************               *********,
                         ********************* *************************,     **       *****
                      *************     ********************************** *             ****
                    ********,,************ ***********&&&&&&&&&(***********                **,
                   ****** *******    ***************,&&&&&&&&&&&&&&%*******              ,@@@@@@
             %@@,,@#.*************,******.**********&&&&&&&&&&&&&&&&*******            @@@@@@#
             @@@@@@@@@@@@@*************************,&&&&&&&&&&&&&&&*******
            @@@@@@@@@@@@@@   **, ,*****************#&&&&&&&&&&&&&&********
             @@@@@@@@@@@@%      *******,***********#&&&&&&&&&&&&&,********
              @@@@@@@@@@@            ****,********* &&&&&&&&&&&&,*******,
                 &@@@@@                   **********&&&&&&&&&&*********
                                         * ***************************
                                            ************************
                                       *****,*,***************,**
                                    *******,   ***************, ***
                                 *******         ***********,   ***
                              *****                              ***
                            ****,                                 **,
                          ****,                                   ***
                        ,****                                      ***
                        *****                                       *****
                        **                                            ********    ******
             ****************,                                          ,**************
             ,***************
                  ,******

        """

    def __init__(self, load_env=True, keep_alive=True, settings_module=None):

        self.from_dict(DEFAULT_CONFIG)
        self.from_object(global_settings)

        if self.SERVICE_NAME is None:
            self.SERVICE_NAME = empty

        # self.REQUEST_MAX_SIZE = 100000000  # 100 megabytes
        # self.REQUEST_TIMEOUT = 60  # 60 seconds
        # self.RESPONSE_TIMEOUT = 60  # 60 seconds
        # self.KEEP_ALIVE = keep_alive
        # self.KEEP_ALIVE_TIMEOUT = 5  # 5 seconds
        # self.WEBSOCKET_MAX_SIZE = 2 ** 20  # 1 megabytes
        # self.WEBSOCKET_MAX_QUEUE = 32
        # self.WEBSOCKET_READ_LIMIT = 2 ** 16
        # self.WEBSOCKET_WRITE_LIMIT = 2 ** 16
        # self.GRACEFUL_SHUTDOWN_TIMEOUT = 15.0  # 15 sec
        # self.ACCESS_LOG = True

        if load_env:
            prefix = INSANIC_PREFIX if load_env is True else load_env
            self.load_environment_vars(prefix=prefix)

        self.load_from_service(settings_module)

    def from_envvar(self, variable_name):
        """Load a configuration from an environment variable pointing to
        a configuration file.

        :param variable_name: name of the environment variable
        :return: bool. ``True`` if able to load config, ``False`` otherwise.
        """
        config_file = os.environ.get(variable_name)
        if not config_file:
            raise RuntimeError('The environment variable %r is not set and '
                               'thus configuration could not be loaded.' %
                               variable_name)
        return self.from_pyfile(config_file)

    def from_pyfile(self, filename):
        """Update the values in the config from a Python file.
        Only the uppercase variables in that module are stored in the config.

        :param filename: an absolute path to the config file
        """
        module = types.ModuleType('config')
        module.__file__ = filename
        try:
            with open(filename) as config_file:
                exec(compile(config_file.read(), filename, 'exec'),
                     module.__dict__)
        except IOError as e:
            e.strerror = 'Unable to load configuration file (%s)' % e.strerror
            raise
        self.from_object(module)
        return True

    def from_object(self, obj):
        """Update the values from the given object.
        Objects are usually either modules or classes.

        Just the uppercase variables in that object are stored in the config.
        Example usage::

            from yourapplication import default_config
            app.config.from_object(default_config)

        You should not use this function to load the actual configuration but
        rather configuration defaults. The actual config should be loaded
        with :meth:`from_pyfile` and ideally from a location not within the
        package because the package might be installed system wide.

        :param obj: an object holding the configuration
        """
        for key in dir(obj):
            if key.isupper():
                try:
                    setattr(self, key, getattr(obj, key))
                except AttributeError:
                    pass

    def from_dict(self, settings):

        for key, value in settings.items():
            if key.isupper():
                try:
                    setattr(self, key, value)
                except AttributeError:
                    pass

    def load_environment_vars(self, prefix=INSANIC_PREFIX):
        """
        Looks for prefixed environment variables and applies
        them to the configuration if present.
        """
        for k, v in os.environ.items():
            if k.startswith(prefix):
                _, config_key = k.split(prefix, 1)
                try:
                    setattr(self, config_key, int(v))
                except ValueError:
                    try:
                        setattr(self, config_key, float(v))

                    except ValueError:
                        setattr(self, config_key, v)

    def load_from_service(self, settings_module=None):
        def load_settings():
            try:
                config_module = importlib.import_module(self.SETTINGS_MODULE)
                self.from_object(config_module)
            except (ImportError, ModuleNotFoundError) as e:
                logger.debug(
                    "Could not import settings '%s' (Is it on sys.path? Is there an import "
                    "error in the settings file?): %s %s"
                    % (self.SETTINGS_MODULE, e, sys.path)
                )
                raise e

        if settings_module is not None:
            self.SETTINGS_MODULE = settings_module
            load_settings()
        elif self.SERVICE_NAME != "insanic" and self.SERVICE_NAME is not empty:
            self.SETTINGS_MODULE = "{0}.config".format(self.SERVICE_NAME)
            load_settings()
        else:
            raise EnvironmentError("Couldn't evaluate where to find settings module")

    @property
    def SERVICE_NAME(self):
        return self._service_name

    @SERVICE_NAME.setter
    def SERVICE_NAME(self, val):
        self._service_name = val
