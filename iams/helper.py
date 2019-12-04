#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import logging
import os


def get_logging_config(config=[], level=logging.INFO, main=True):

    if isinstance(config, (list, tuple)):
        loggers = {}
        for logger in config:
            loggers[logger] = {}
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
                'formatter': 'debug' if level == logging.DEBUG else "default",
            },
        },
        'loggers': loggers,
        'root': {
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    }

    # FLUENTD plugin
    if os.environ.get('FLUENTD_HOST'):
        conf["formatters"]["fluentd"] = {
            '()': 'fluent.handler.FluentRecordFormatter',
            'format': {
                'level': '%(levelname)s',
                # 'hostname': '%(hostname)s',
                'name': '%(name)s',
                'line': '%(lineno)d',
                'func': '%(funcName)s',
            },
        }
        conf["handlers"]["fluentd"] = {
            'class': 'fluent.handler.FluentHandler',
            'host': os.environ.get('FLUENTD_HOST'),
            'port': int(os.environ.get('FLUENTD_PORT', 24224)),
            'tag': os.environ.get('FLUENTD_TAG', 'ams.container'),
            'level': 'DEBUG',
            'formatter': 'fluentd',
            'nanosecond_precision': True,
        }
        conf["root"]["handlers"].append("fluentd")

    # SENTRY plugin
    if os.environ.get('RAVEN_DSN'):
        conf["handlers"]["sentry"] = {
            'level': 'ERROR',
            'class': 'raven.handlers.logging.SentryHandler',
            'dsn': os.environ.get('RAVEN_DSN'),
        }
        conf["root"]["handlers"].append("sentry")

    return conf
