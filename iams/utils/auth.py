#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auth tools
"""

from functools import wraps
import logging

import grpc


logger = logging.getLogger(__name__)


def permissions(function=None, is_optional=False):
    """
    permission decorator
    """
    # pylint: disable=protected-access

    def decorator(func):
        @wraps(func)
        def wrapped(self, request, context):

            # internal request
            if hasattr(context, "_credential"):
                logger.debug("Context already as a _agent attribute - internal request")
                return func(self, request, context)

            try:
                context._credential = context.auth_context()["x509_common_name"][0]
            except (KeyError, AttributeError):
                logger.debug("Could not assign the _agent attribute")
                context._credential = None

            if is_optional or context._credential is not None:
                return func(self, request, context)

            message = "Client needs to be authentifacted"
            logger.debug(message)
            return context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        return wrapped

    if function:
        return decorator(function)
    return decorator
