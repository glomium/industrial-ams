#!/usr/bin/python3
# vim: set fileencoding=utf-8 :

import json
import grpc
from functools import wraps


def set_credentials(agent, image, version, groups):
    if groups is None:
        groups = []
    return json.dumps([agent, image, version, groups])


def get_credentials(credentials):
    agent, image, version, groups = json.loads(credentials)
    return agent, image, version, groups


def permissions(function=None, has_agent=False, has_groups=[], is_optional=False):

    def decorator(func):
        @wraps(func)
        def wrapped(self, request, context):
            auth = context.auth_context()

            if not auth:
                if is_optional:
                    context._agent, context._version, context._image, context._groups = None, None, None, set()
                    return func(self, request, context)
                else:
                    message = 'Request is not authenticated'
                    context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

            if "x509_common_name" not in auth:
                message = 'Client certificate is missing'
                context.abort(grpc.StatusCode.PERMISSION_DENIED, message)

            context._agent, context._version, context._image, context._groups = get_credentials(auth["x509_common_name"][0])  # noqa

            if has_agent and not has_groups and context._agent is None:
                message = "Client needs to be an agent"
                context.abort(grpc.StatusCode.UNAUTHENTICATED, message)
            elif has_groups:
                groups = set(has_groups)
                if not groups.issubset(context._groups):
                    message = "Client needs to be in %s" % groups
                    context.abort(grpc.StatusCode.UNAUTHENTICATED, message)

            return func(self, request, context)
        return wrapped

    if function:
        return decorator(function)
    return decorator
