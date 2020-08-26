import importlib
import sys

from sanic.config import Config

from insanic.conf import global_settings
from insanic.log import logger

INSANIC_PREFIX = "INSANIC_"

INSANIC_LOGO = """
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


class InsanicConfig(Config):
    def __init__(
        self,
        settings_module: str = "",
        defaults: dict = None,
        load_env: bool = True,
        keep_alive=None,
    ):
        """
        Load order:
        1. Sanic DEFAULT_CONFIG
        2. defaults sent in through argument
        3. SANIC_PREFIX environment variables
        4. Insanic global_settings (insanic.conf.global_settings)
        5. Service configs loaded from INSANIC_SETTINGS_MODULE env variable
        6. INSANIC_PREFIX environment variables

        Sequentially loaded variables overwrite settings declared in
        previous steps.

        :param settings_module:
        :param defaults:
        :param load_env:
        :param keep_alive:
        """
        super().__init__(
            defaults=defaults, load_env=load_env, keep_alive=keep_alive
        )

        self.SETTINGS_MODULE = None

        self.from_object(global_settings)

        if settings_module:
            self.SETTINGS_MODULE = settings_module
            self.load_from_service()

        if load_env:
            prefix = INSANIC_PREFIX if load_env is True else load_env
            self.load_environment_vars(prefix=prefix)

    def __setitem__(self, key, value):
        if key in self:
            logger.debug(
                f"{key} setting is already declared. "
                f"Overwriting setting {key} "
                f"from value: [{self[key]}] to [{value}] "
            )
        super().__setitem__(key, value)

    def load_from_service(self):
        """
        Loads a config from defined settings module.

        If the module doesn't exist raise exception

        :return:
        """

        try:
            config_module = importlib.import_module(self.SETTINGS_MODULE)
            self.from_object(config_module)
        except ImportError as e:
            logger.debug(
                "Could not import settings '%s' (Is it on sys.path? Is there an import "
                "error in the settings file?): %s %s"
                % (self.SETTINGS_MODULE, e, sys.path)
            )
            raise e
