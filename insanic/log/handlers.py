import asyncio
import logging
import sys

from insanic import mail
from insanic.conf import settings
from insanic.log.reporters import SafeExceptionReporterFilter, ExceptionReporter
from insanic.utils import force_str

default_exception_reporter_filter = None


def get_exception_reporter_filter():
    global default_exception_reporter_filter
    if default_exception_reporter_filter is None:
        # Load the default filter for the first time and cache it.
        default_exception_reporter_filter = SafeExceptionReporterFilter()

    return default_exception_reporter_filter


class AdminEmailHandler(logging.Handler):
    """An exception log handler that emails log entries to site admins.

    If the request is passed as the first argument to the log record,
    request data will be provided in the email report.
    """

    def __init__(self, include_html=True, email_backend=None):
        logging.Handler.__init__(self)
        self.include_html = include_html
        self.email_backend = email_backend

    def emit(self, record):
        try:
            request = record.request
            subject = '%s (%s IP): %s' % (
                record.levelname,
                ('internal' if request.ip[0] in settings.INTERNAL_IPS
                 else 'EXTERNAL'),
                record.getMessage()
            )
            filter = get_exception_reporter_filter()
            request_repr = '\n{0}'.format(force_str(filter.get_request_repr(request)))
        except Exception as e:
            subject = '%s: %s' % (
                record.levelname,
                record.getMessage()
            )
            request = None
            request_repr = "unavailable"
        subject = self.format_subject(subject)

        if record.exc_info:
            exc_info = record.exc_info
        else:
            exc_info = (None, record.getMessage(), None)


        message = "%s\n\nRequest repr(): %s" % (self.format(record), request_repr)
        reporter = ExceptionReporter(request, is_email=True, *exc_info)
        if self.include_html:
            html_message = reporter.get_traceback_html()
        else:
            html_message = None

            # html_message = None
        asyncio.ensure_future(mail.mail_admins(subject, message, fail_silently=True,
                                               html_message=html_message))



    def format_subject(self, subject):
        """
        Escape CR and LF characters, and limit length.
        RFC 2822's hard limit is 998 characters per line. So, minus "Subject: "
        the actual subject must be no longer than 989 characters.
        """
        formatted_subject = subject.replace('\n', '\\n').replace('\r', '\\r')
        return formatted_subject[:989]