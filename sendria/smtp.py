__all__ = []

import email.message
from typing import Optional

import aiosmtpd.controller
import aiosmtpd.handlers
import aiosmtpd.smtp
from passlib.apache import HtpasswdFile

from . import db
from . import logger


class AsyncMessage(aiosmtpd.handlers.AsyncMessage):
    def __init__(self, *args, smtp_auth=None, **kwargs):
        self._smtp_auth = smtp_auth

        super().__init__(*args, **kwargs)

    async def handle_message(self, message: email.message.Message):
        body = message.get_payload()
        logger.get().msg("message received",
            envelope_from=message['X-MailFrom'],
            envelope_to=message['X-RcptTo'],
            peer=':'.join([i.strip(" '()")for i in message['X-Peer'].split(',')]),
            length=len(body)
        )
        db.add_message(message['X-MailFrom'], message['X-RcptTo'], message, message['X-Peer'])


class SMTP(aiosmtpd.smtp.SMTP):
    def __init__(self, handler, smtp_auth, debug, *args, **kwargs):
        self._smtp_auth = smtp_auth
        self._debug_mode = debug
        self._username = None

        super().__init__(
            handler,
            auth_required=smtp_auth is not None,
            auth_require_tls=False,
            auth_callback=self.authenticate,
            *args, **kwargs
        )

    def _debug(self, message, **params):
        if self._debug_mode:
            logger.get().msg('SMTP: ' + message, **params)

    def authenticate(self, mechanism, login, password):
        return self._smtp_auth.check_password(login, password)


class Controller(aiosmtpd.controller.Controller):
    def __init__(self, handler, smtp_auth, debug, *args, **kwargs):
        self.smtp_auth = smtp_auth
        self.debug = debug
        self.ident = kwargs.pop('ident')

        super().__init__(handler, ready_timeout=5.0, *args, **kwargs)

    def factory(self):
        return SMTP(self.handler, self.smtp_auth, self.debug, ident=self.ident)


def run(smtp_host: str, smtp_port: int, smtp_auth: Optional[HtpasswdFile], ident: Optional[str], debug: bool):
    message = AsyncMessage(smtp_auth=smtp_auth)
    controller = Controller(message, smtp_auth, debug, hostname=smtp_host, port=smtp_port, ident=ident)
    controller.start()

    return controller
