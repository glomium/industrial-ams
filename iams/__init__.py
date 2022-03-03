#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Industrial agent management system
"""

from functools import lru_cache

VERSION = ((0, 6, 4), ('b', 0))


@lru_cache(maxsize=8)
def get_version(dev=True, short=False):
    """
    return a version number consistent with PEP386
    """
    assert len(VERSION) == 2
    assert VERSION[1][0] in ('a', 'b', 'rc', 'final')

    branch = None
    version = '.'.join(map(str, VERSION[0]))

    if VERSION[1][0] == "final":  # pragma: no cover
        return version, None

    version += VERSION[1][0] + str(VERSION[1][1])

    if VERSION[1][1] == 0 and (dev or short):  # pragma: no cover
        import os  # pylint: disable=import-outside-toplevel
        import subprocess  # pylint: disable=import-outside-toplevel
        import datetime  # pylint: disable=import-outside-toplevel

        # get version information from git
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        with subprocess.Popen(
            'git rev-parse --abbrev-ref HEAD',
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=True,
            cwd=repo_dir,
            universal_newlines=True,
        ) as proc:
            branch = proc.communicate()[0].strip()

        if dev:
            with subprocess.Popen(
                'git log --pretty=format:%ct --quiet -1 HEAD',
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=True,
                cwd=repo_dir,
                universal_newlines=True,
            ) as proc:
                timestamp = proc.communicate()[0]

            try:
                timestamp = datetime.datetime.utcfromtimestamp(int(timestamp))
                version += '.dev' + timestamp.strftime('%Y%m%d%H%M%S')
            except ValueError:  # pragma: no cover
                pass

    return version, branch


__version__, __branch__ = get_version(dev=False)
