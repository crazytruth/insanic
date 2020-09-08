from collections.abc import Mapping

from insanic.conf import settings
from insanic.functional import LazyObject, empty

from insanic.services import Service


class LazyServiceRegistry(LazyObject):
    def _setup(self):
        self._wrapped = ServiceRegistry()

    def __repr__(self):
        if self._wrapped is empty:
            return "<LazyServiceRegistry> [Unevaluated]"
        return f"<LazyServiceRegistry> {self._wrapped.__class__.__name__}"

    def __getitem__(self, item):
        if self._wrapped is empty:
            self._setup()

        return self._wrapped[item]

    def __len__(self):  # pragma: no cover
        if self._wrapped is empty:
            self._setup()

        return len(self._wrapped)

    def __iter__(self):  # pragma: no cover
        if self._wrapped is empty:
            self._setup()

        return iter(self._wrapped)

    def reset(self):
        self._wrapped = empty


class ServiceRegistry(Mapping):
    def __init__(self):
        for s in self.available_services:
            self.__dict__[s] = None

    @property
    def available_services(self) -> set:
        return set(
            list(settings.SERVICE_CONNECTIONS)
            + list(settings.REQUIRED_SERVICE_CONNECTIONS)
        )

    def __len__(self):  # pragma: no cover
        return len(self.__dict__)

    def __getitem__(self, item):
        try:
            value = self.__dict__[item]
        except KeyError:
            if item not in self.available_services:
                raise RuntimeError(
                    "{0} service does not exist. Only the following: {1}".format(
                        item, ", ".join(self.keys())
                    )
                )
            else:
                raise LookupError(
                    "Settings for either `SERVICE_CONNECTIONS` or "
                    "`REQUIRED_SERVICE_CONNECTIONS` must have been modified after "
                    "initialization."
                )
        else:
            if value is None:
                value = Service(item)
                self.__dict__[item] = value
        return value

    def __iter__(self):
        return iter(self.__dict__)


registry = LazyServiceRegistry()
