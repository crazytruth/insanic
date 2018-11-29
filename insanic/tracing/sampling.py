import copy

from insanic.functional import cached_property


class Sampler:

    _sample_rule = {
        "description": str,
        "service_name": str,
        "http_method": str,
        "url_path": str,
        "fixed_target": int,
        "rate": float
    }

    def __init__(self, app):
        self.app = app

    @cached_property
    def tracing_service_name(self):
        return f"{self.app.config.MMT_ENV.upper()}:{self.app.config.SERVICE_NAME}"

    # def _validate_sampling_rule(self, rule):
    #     if not isinstance(rule, dict):
    #         raise RuntimeError("Invalid sampling rule format. Not valid type.")
    #
    #     if sorted(rule.keys()) != sorted(self._sample_rule.keys()):
    #         raise RuntimeError("Invalid sampling rule format. Required fields are {0}.".format(
    #             ", ".join(self._sample_rule.keys())))
    #
    #     for k, v in self._sample_rule.items():
    #         if not isinstance(rule[k], v):
    #             raise RuntimeError("Invalid sampling rule format. Not valid type for {0}.".format(k))
    #
    # def validate_sampling_rules(self, rules):
    #     if isinstance(rules, list):
    #         for r in rules:
    #             self._validate_sampling_rule(r)
    #     elif isinstance(rules, dict):
    #         self._validate_sampling_rule(rules)
    #     else:
    #         raise RuntimeError("Something wrong with sampling rules. {0}".format(rules))

    @cached_property
    def sampling_rules(self):
        rules = copy.deepcopy(self.app.config.SAMPLING_RULES)
        if not self.app.config.TRACING_ENABLED:
            rules.update({"rules": []})
            rules.update({"default": {"fixed_target": 0, "rate": 0}})

        return rules
