import aiobotocore

import logging
import traceback

from base64 import b64encode
from inspect import isawaitable


from email.message import EmailMessage
from email.headerregistry import Address

from insanic.conf import settings

logger = logging.getLogger('sanic')


async def mail_admins(subject, message, fail_silently=False, connection=None,
                html_message=None):
    if isawaitable(html_message):
        html_message = await html_message

    if not settings.ADMINS:
        return
    mail = EmailMessage()
    mail['Subject'] = '{0}{1}'.format(settings.EMAIL_SUBJECT_PREFIX, subject)

    to = []
    for _name, _email in settings.ADMINS:
        _username, _domain = _email.split('@')
        to.append((_name, _username, _domain))
    mail['To'] = [Address(_name, _username, _domain) for _name, _username, _domain in set(to)]

    username, domain = settings.SERVER_ERROR_EMAIL.split('@')
    mail['From'] = Address('MMT SERVER OVERLORD', username, domain)
    mail.set_content(message)



    if html_message:
        try:
            mail.add_alternative(html_message, 'html')
        except Exception as e:
            tb = traceback.format_exc()
            logger.info(tb)
            raise e


    session = aiobotocore.get_session()
    logger.debug("Create boto client")
    try:
        async with session.create_client('ses', region_name=settings.AWS_SES_REGION,
                                         aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                                         aws_access_key_id=settings.AWS_ACCESS_KEY_ID) as client:

            logger.debug("Created boto client")

            response = await client.send_raw_email(RawMessage={"Data": mail.as_string().encode('utf-8')})
            logger.debug(response)
    except:
        tb=traceback.format_exc()
        logger.info(tb)
