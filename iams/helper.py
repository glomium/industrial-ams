#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
helper functions
"""

import logging
import os

try:
    import fluent  # noqa  # pylint: disable=unused-import
    FLUENTD = True
except ImportError:
    FLUENTD = False

try:
    import sentry_sdk  # noqa
    SENTRY = True
except ImportError:
    SENTRY = False


def get_logging_config(config=None, level=logging.INFO, main=True):  # pragma: no cover
    """
    generate a loggin config
    """

    if isinstance(config, (list, tuple)):
        loggers = {}
        for key in config:
            loggers[key] = {}
    elif isinstance(config, dict):
        loggers = config

    if main and "__main__" not in loggers:
        loggers["__main__"] = {}

    conf = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'default': {
                'format': "[%(asctime)s.%(msecs)03d] %(levelname).1s %(message)s",
                'datefmt': "%H:%M:%S",
            },
            'logfile': {
                'format': "%(message)s",
            },
            'debug': {
                'format': "[%(asctime)s.%(msecs)03d] %(levelname)s [%(name)s:%(lineno)s] %(message)s",
                'datefmt': "%H:%M:%S",
            },
        },
        'handlers': {
            'console': {
                'class': "logging.StreamHandler",
                'level': level,
                'formatter': 'debug' if level <= logging.INFO else "default",
            },
        },
        'loggers': loggers,
        'root': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    }

    # FLUENTD plugin
    if FLUENTD and os.environ.get('FLUENTD_HOST') and os.environ.get('FLUENTD_TAG'):  # pragma: no branch
        conf["formatters"]["fluentd"] = {
            '()': 'fluent.handler.FluentRecordFormatter',
            'format': {
                'level': '%(levelname)s',
                'name': '%(name)s',
                'line': '%(lineno)d',
                'func': '%(module)s.%(funcName)s',
            },
        }
        conf["handlers"]["fluentd"] = {
            'class': "fluent.handler.FluentHandler",
            'host': os.environ.get('FLUENTD_HOST'),
            'port': int(os.environ.get('FLUENTD_PORT', 24224)),
            'tag': os.environ.get('FLUENTD_TAG'),
            'level': os.environ.get('FLUENTD_LEVEL', 'INFO'),
            'formatter': 'fluentd',
            'nanosecond_precision': True,
        }
        conf["root"]["handlers"].append("fluentd")

    # SENTRY plugin
    if SENTRY and os.environ.get('SENTRY_DSN'):  # pragma: no branch
        sentry_sdk.init(
            os.environ.get('SENTRY_DSN'),
            server_name=os.environ.get('IAMS_AGENT', None),
        )

    return conf
