import inspect

import pytest
from sanic import Sanic

from insanic import Insanic, middleware as insanic_middleware
from insanic.app import LISTENER_TYPES, MIDDLEWARE_TYPES
from insanic.conf import LazySettings, settings
from insanic.exceptions import ImproperlyConfigured
from insanic.functional import empty


class TestInsanic:
    def test_insanic_app_basic_initialization(self):
        """
        Just basic Insanic initialization
        :return:
        """

        app = Insanic("taels")

        assert app.initialized_plugins == {}
        assert isinstance(app.config, LazySettings)
        assert app.config.SERVICE_NAME == "taels"
        assert app.config.APPLICATION_VERSION == "UNKNOWN"
        assert "monitor" in app.blueprints

    def test_insanic_dont_attach_monitor_endpoints(self):
        """
        Tests to skip monitor endpoints

        :return:
        """

        app = Insanic("taels", attach_monitor_endpoints=False)

        assert app.metrics is empty
        assert app.blueprints == {}

    def test_insanic_app_config_argument(self):
        """
        Test to make sure the configs get loaded into settings

        :return:
        """

        class SomeConfig:
            SOME_CONFIG = "hello"
            I_STILL_SURVIVE = "!"

        class SomeOtherConfig:
            SOME_CONFIG = "bye"

        Insanic("taels", app_config=(SomeConfig, SomeOtherConfig))

        assert settings.SOME_CONFIG == "bye"
        assert settings.I_STILL_SURVIVE == "!"

    def test_sanic_argument_compatibility(self):
        """
        This test is to ensure the sanic arguments are a subset of
        insanic's arguments. Probably use case would be when a new
        version of sanic gets released with added/modified arguments.

        :return:
        """

        # for __init__
        sanic_args = set(inspect.signature(Sanic).parameters.keys())
        insanic_args = set(inspect.signature(Insanic).parameters.keys())
        # tests arguments are subset
        assert (
            sanic_args <= insanic_args
        ), f"{sanic_args - insanic_args} is/are missing."

        # for Sanic.run
        sanic_run_args = set(inspect.signature(Sanic.run).parameters.keys())
        insanic_run_args = set(inspect.signature(Insanic.run).parameters.keys())
        assert (
            sanic_run_args <= insanic_run_args
        ), f"{sanic_run_args - insanic_run_args} is/are missing."

        # for Sanic._helper
        sanic_helper_args = set(
            inspect.signature(Sanic._helper).parameters.keys()
        )
        insanic_helper_args = set(
            inspect.signature(Insanic._helper).parameters.keys()
        )
        assert (
            sanic_helper_args <= insanic_helper_args
        ), f"{sanic_helper_args - insanic_helper_args} is/are missing."

    def test_version_configuration_not_enforced(self):
        """
        When version configuration is not enforced.

        :return:
        """

        # ENFORCE_APPLICATION_VERSION should be False right now
        app = Insanic("good")
        assert app.config.APPLICATION_VERSION == "UNKNOWN"

        app = Insanic("good", version="1.1.1")
        assert app.config.APPLICATION_VERSION == "1.1.1"

    def test_version_configuration_enforced(self, monkeypatch):
        """
        Test when version is enforced.
        Also checks any fallbacks.

        :param monkeypatch:
        :return:
        """
        monkeypatch.setattr(settings, "ENFORCE_APPLICATION_VERSION", True)

        with pytest.raises(ImproperlyConfigured):
            Insanic("bad")

        with pytest.raises(ImproperlyConfigured):
            Insanic("bad", version=None)

        app = Insanic("good", version="2.2.2")
        assert app.config.APPLICATION_VERSION == "2.2.2"
        assert settings.APPLICATION_VERSION == "2.2.2"

    def test_version_configuration_from_settings(self, monkeypatch):
        """
        Tests version precedence.

        :param monkeypatch:
        :return:
        """
        monkeypatch.setattr(settings, "ENFORCE_APPLICATION_VERSION", True)
        monkeypatch.setattr(settings, "APPLICATION_VERSION", "1.1.1")

        app = Insanic("good")
        assert app.config.APPLICATION_VERSION == "1.1.1"
        assert settings.APPLICATION_VERSION == "1.1.1"

        app = Insanic("good", version="2.2.2")
        assert app.config.APPLICATION_VERSION == "2.2.2"
        assert settings.APPLICATION_VERSION == "2.2.2"

    @staticmethod
    def get_attached_listeners(app: Insanic) -> set:

        initialized_listener_list = set()
        for _type, func_list in app.listeners.items():
            for func in func_list:
                initialized_listener_list.add(func.__name__)
        return initialized_listener_list

    @staticmethod
    def get_attached_middlewares(app: Insanic) -> set:
        return set([f.__name__ for f in app.request_middleware]).union(
            set([f.__name__ for f in app.response_middleware])
        )

    def test_initialize_listeners(self) -> None:
        """
        Tests if the default listeners for insanic were initialized
        :return:
        """

        app = Insanic("good")

        from insanic import listeners

        listener_list = set()
        for attribute in dir(listeners):
            for listener in LISTENER_TYPES:
                if attribute.startswith(listener):
                    listener_list.add(attribute)

        initialized_listener_list = self.get_attached_listeners(app)
        assert listener_list == initialized_listener_list

    def test_dont_initialize_listener(self):

        app = Insanic("good", initialize_insanic_listeners=False)

        initialized_listener_list = self.get_attached_listeners(app)
        assert initialized_listener_list == set()

    def test_initialize_middlewares(self):
        """
        This may not work in debug mode because of Sanic's
        `asgi_client` property. Because debug will evaluate all
        attributes and while evaluating asgi_client,
        the SanicASGITestClient attaches it's own middleware.

        :return:
        """

        app = Insanic("good")

        middleware_list = set()

        for attrib in dir(insanic_middleware):
            for middleware in MIDDLEWARE_TYPES:
                if attrib.startswith(middleware):
                    middleware_list.add(attrib)

        initialized_middleware_list = self.get_attached_middlewares(app)

        assert middleware_list == initialized_middleware_list

    def test_dont_initialize_middlewares(self):
        """
        Same condition as test_initialize_middlewares.

        :return:
        """
        app = Insanic("good", initialize_insanic_middlewares=False)
        initialized_middleware_list = self.get_attached_middlewares(app)
        assert initialized_middleware_list == set()
