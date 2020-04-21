#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...exceptions import SkipPlugin
from ...interface import Plugin


logger = logging.getLogger(__name__)


class Sentry(Plugin):

    def label():
        return "iams.plugins.sentry"

    def __init__(self, **kwargs):
        self.sentry = os.environ.get('SENTRY_DSN', None)
        if self.sentry is None:
            logger.debug("SENTRY_DSN is not defined - skip plugin")
            raise SkipPlugin
        super().__init__(**kwargs)

    def get_env(self, **kwargs):
        return {
            'SENTRY_DSN': self.sentry,
        }
