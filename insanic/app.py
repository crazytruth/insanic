from sanic import Sanic
from sanic_useragent import SanicUserAgent

from insanic.functional import cached_property
from insanic.handlers import ErrorHandler
from insanic.monitor import blueprint_monitor
from insanic.log import LOGGING
from insanic.protocol import InsanicHttpProtocol
from insanic.utils import attach_middleware

LISTENER_TYPES = ("before_server_start", "after_server_start", "before_server_stop", "after_server_stop")

class Insanic(Sanic):
    database = None

    _default_sampling_rules = {
        "version": 1,
        "rules": [
            # {
            #     "description": "Player moves.",
            #     "service_name": "*",
            #     "http_method": "*",
            #     "url_path": "/api/move/*",
            #     "fixed_target": 0,
            #     "rate": 0.05
            # }
        ],
        "default": {
            "fixed_target": 30,
            "rate": 0.05
        }
    }

    _sample_rule = {
        "description": str,
        "service_name": str,
        "http_method": str,
        "url_path": str,
        "fixed_target": int,
        "rate": float
    }

    def __init__(self, name, router=None, error_handler=None, app_config=()):

        if error_handler is None:
            error_handler = ErrorHandler()

        from insanic.conf import settings

        for c in app_config:
            try:
                settings.from_pyfile(c)
            except TypeError:
                settings.from_object(c)
            except FileNotFoundError:
                pass


        super().__init__(name, router, error_handler, log_config=LOGGING)

        self.config = settings

        SanicUserAgent.init_app(self)
        attach_middleware(self)

        from insanic import listeners
        for module_name in dir(listeners):
            for l in LISTENER_TYPES:
                if module_name.startswith(l):
                    self.listeners[l].append(getattr(listeners, module_name))

        self.blueprint(blueprint_monitor)

    def _helper(self, **kwargs):
        """Helper function used by `run` and `create_server`."""
        server_settings = super()._helper(**kwargs)
        server_settings['protocol'] = InsanicHttpProtocol
        server_settings['request_timeout'] = 60
        return server_settings

    @cached_property
    def tracing_service_name(self):
        return "{0}:{1}".format(self.config.MMT_ENV.upper(), self.config.SERVICE_NAME)


    def _validate_sampling_rule(self, rule):
        if not isinstance(rule, dict):
            raise RuntimeError("Invalid sampling rule format. Not valid type.")

        if sorted(rule.keys()) != sorted(self._sample_rule.keys()):
            raise RuntimeError("Invalid sampling rule format. Required fields are {0}.".format(
                ", ".join(self._sample_rule.keys())))

        for k, v in self._sample_rule.items():
            if not isinstance(rule[k], v):
                raise RuntimeError("Invalid sampling rule format. Not valid type for {0}.".format(k))

    def validate_sampling_rules(self, rules):
        if isinstance(rules, list):
            for r in rules:
                self._validate_sampling_rule(r)
        elif isinstance(rules, dict):
            self._validate_sampling_rule(rules)
        else:
            raise RuntimeError("Something wrong with sampling rules. {0}".format(rules))

    @cached_property
    def sampling_rules(self):

        rules = self._default_sampling_rules.copy()
        for uri, route in self.router.routes_all.items():
            route_sampling_rules = self._sample_rule.copy()
            route_sampling_rules.update({"service_name": self.tracing_service_name})
            route_sampling_rules.update({"description": route.name})
            route_sampling_rules.update({"http_method": " ".join(route.methods)})
            route_sampling_rules.update({"url_path": route.uri})
            route_sampling_rules.update({"fixed_target": 1})
            route_sampling_rules.update({"rate": 0.05})

            if not hasattr(route.handler, "view_class"):
                route_sampling_rules.update({"fixed_target": 0})
                route_sampling_rules.update({"rate": 0.0})
            else:
                if hasattr(route.handler.view_class, "sampling_rules"):
                    route_sampling_rules.update(route.handler.view_class.sampling_rules)
                else:
                    route_sampling_rules.update({"fixed_target": 1})
                    route_sampling_rules.update({"rate": 0.05})

            self.validate_sampling_rules(route_sampling_rules)

            if isinstance(route_sampling_rules, list):
                rules['rules'].extend(route_sampling_rules)
            elif isinstance(route_sampling_rules, dict):
                rules['rules'].append(route_sampling_rules)
            else:
                raise RuntimeError("Invalid sampling rules for {0} {1} {2}".format(self.tracing_service_name,
                                                                                   route.name, route.uri))
        return rules


