#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import grpc
from functools import wraps


logger = logging.getLogger(__name__)


def permissions(function=None, is_optional=False):

    def decorator(func):
        @wraps(func)
        def wrapped(self, request, context):

            # internal request
            if hasattr(context, "_agent"):
                logger.debug("Context already as a _agent attribute - internal request")
                return func(self, request, context)

            try:
                context._agent = context.auth_context()["x509_common_name"][0]
            except (KeyError, AttributeError):
                logger.debug("Could not assign the _agent attribute")
                context._agent = None

            if is_optional or context._agent is not None:
                return func(self, request, context)
            else:
                message = "Client needs to be authentifacted"
                logger.debug(message)
                context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

        return wrapped

    if function:
        return decorator(function)
    return decorator
