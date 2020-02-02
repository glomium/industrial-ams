#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os

from ...interface import Plugin


logger = logging.getLogger(__name__)


class Sentry(Plugin):

    def __init__(self, config):
        self.sentry = os.environ.get('RAVEN_DSN')

    def __call__(self, config, **kwargs):
        logger.debug("calling %s plugin with config %s", self.__class__.__name__, config)

        if self.sentry:
            env = {
                'RAVEN_DSN': self.sentry,
            }
        else:
            env = {}
        return set(), env
