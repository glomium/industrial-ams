#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...exceptions import SkipPlugin
from ...interface import Plugin


logger = logging.getLogger(__name__)


class Sentry(Plugin):
    label = "iams.plugin.sentry"

    def __init__(self, **kwargs):
        self.sentry = os.environ.get('RAVEN_DSN', None)
        if self.sentry is None:
            raise SkipPlugin

    def get_env(self, **kwargs):
        return {
            'RAVEN_DSN': self.sentry,
        }
