import logging
import time
import socket
import ujson as json

from insanic import __version__
from insanic.conf import settings


class JSONFormatter(logging.Formatter):

    converter = time.gmtime
    default_msec_format = '%s.%03d'

    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(None, datefmt)

        if not fmt:
            self._fmt_dict = {
                'sys_host': '%(hostname)s',
                'sys_name': '%(name)s',
                'sys_module': '%(module)s',
            }
        else:
            self._fmt_dict = fmt

        self.hostname = socket.gethostname()
        self.extra_fields = {"service": settings.SERVICE_NAME, "environment": settings.MMT_ENV,
                             "insanic_version": __version__, "service_version": "0.0.1"}

        for k,v in self.extra_fields.items():
            setattr(self, k, v)

    def formatTime(self, record, datefmt=None):
        s = super().formatTime(record, datefmt)

        try:
            s = s % record.__dict__
        except KeyError:
            pass

        return s

    def format(self, record):

        # Compute attributes handled by parent class.
        super().format(record)
        # Add ours
        record.hostname = self.hostname
        for k,v in self.extra_fields.items():
            setattr(record, k, v)

        # Apply format
        data = {}
        for key, value in self._fmt_dict.items():
            try:
                value = value % record.__dict__
            except KeyError as exc:
                value = None
                # raise exc

            data[key] = value

        self._structuring(data, record)
        return json.dumps(data, sort_keys=True)



    def usesTime(self):
        return any([value.find('%(asctime)') >= 0
                    for value in self._fmt_dict.values()])

    def _structuring(self, data, record):
        """ Melds `msg` into `data`.

        :param data: dictionary to be sent to fluent server
        :param msg: :class:`LogRecord`'s message to add to `data`.
          `msg` can be a simple string for backward compatibility with
          :mod:`logging` framework, a JSON encoded string or a dictionary
          that will be merged into dictionary generated in :meth:`format.
        """
        msg = record.msg

        if isinstance(msg, dict):
            self._add_dic(data, msg)
        elif isinstance(msg, (str, bytes)):
            try:
                json_msg = json.loads(str(msg))
                if isinstance(json_msg, dict):
                    self._add_dic(data, json_msg)
                else:
                    self._add_dic(data, {'message': str(json_msg)})
            except ValueError:
                msg = record.getMessage()
                self._add_dic(data, {'message': msg})
        else:
            self._add_dic(data, {'message': msg})

    @staticmethod
    def _add_dic(data, dic):
        for key, value in dic.items():
            if isinstance(key, (str, bytes)):
                data[str(key)] = value