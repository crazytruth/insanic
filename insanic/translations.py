import os
import gettext

from insanic.conf import settings
from insanic.functional import LazyObject

__all__ = ['Translations']


class Translations(LazyObject):
    def _setup(self):
        self._wrapped = _Translations()


class _Translations(dict):

    def __init__(self):
        self._domain = settings.SERVICE_NAME

        # the number 3 is the directory of mmt-server from project root
        for i in range(0, min(settings.PROJECT_ROOT.count('/'), 3)):
            search_path = os.path.join(settings.PROJECT_ROOT, '/'.join([".."] * i), "translations")
            translation_path = gettext.find(self._domain, search_path)

            if translation_path is not None:
                self._localedir = search_path
                break
        else:
            self._localedir = settings.PROJECT_ROOT

        super().__init__()

    def __getitem__(self, item):
        if self.get(item, None) is None:
            self[item] = gettext.translation(self._domain, self._localedir, languages=[item], fallback=True)
        return super().__getitem__(item)
