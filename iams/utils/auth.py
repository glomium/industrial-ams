#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import logging
import grpc
from functools import wraps


logger = logging.getLogger(__name__)


def set_credentials(agent=None, image=None, version=None, username=None, groups=None):
    if groups is None:
        groups = []
    if agent is not None:
        return json.dumps([agent, image, version, groups])
    else:
        return json.dumps([username, groups])


def get_credentials(credentials):
    data = json.loads(credentials)
    if len(data) == 2:
        return None, None, None, data[0], set(data[1])
    return data[0], data[1], data[2], data[0], set(data[3])


def permissions(function=None, has_agent=False, has_groups=[], is_optional=False):

    def decorator(func):
        @wraps(func)
        def wrapped(self, request, context):
            auth = context.auth_context()

            if not auth:
                if is_optional:
                    context._agent, context._version, context._image, context._username, context._groups = None, None, None, None, set()  # noqa
                    return func(self, request, context)
                else:
                    message = 'Request is not authenticated'
                    context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

            if "x509_common_name" not in auth:
                message = 'Client certificate is missing'
                context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

            context._agent, context._version, context._image, context._username, context._groups = get_credentials(auth["x509_common_name"][0])  # noqa

            if has_agent and not has_groups and context._agent is None:
                message = "Client needs to be an agent"
                context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
            elif has_groups:
                groups = set(has_groups)
                logger.debug("Check if groups %s has members in %s", groups, context._groups)

                if not groups.intersection(context._groups):
                    message = "Client needs to be in one of %s" % (groups)
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

            return func(self, request, context)
        return wrapped

    if function:
        return decorator(function)
    return decorator
