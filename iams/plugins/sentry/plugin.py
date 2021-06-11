#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sentry
"""

import logging
import os

from iams.exceptions import SkipPlugin
from iams.interfaces.plugin import Plugin


logger = logging.getLogger(__name__)


class Sentry(Plugin):
    """
    Sentry
    """

    @classmethod
    def label(cls):
        return "iams.plugins.sentry"

    def __init__(self, **kwargs):
        self.sentry = os.environ.get('SENTRY_DSN', None)
        if self.sentry is None:  # pragma: no branch
            logger.debug("SENTRY_DSN is not defined - skip plugin")
            raise SkipPlugin
        super().__init__(**kwargs)

    def get_env(self, **kwargs):
        return {
            'SENTRY_DSN': self.sentry,
        }
