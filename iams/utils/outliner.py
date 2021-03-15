#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import numpy as np


def quartiles(x, whiskers=1.5):
    """
    returns array with
    - lower whisker
    - first quartile
    - second quartile (median)
    - third quartile
    - upper whisker

    raises index error if x is empty
    """
    x = np.asarray(x, dtype=float)  # convert x to numpy array

    q1, med, q3 = np.percentile(x, [25, 50, 75])
    iqr = q3 - q1

    # get high extreme
    extrema = np.max(x[x <= q3 + whiskers * iqr])
    if extrema < q3:
        whishi = q3
    else:
        whishi = extrema

    # get low extreme
    extrema = np.min(x[x >= q1 - whiskers * iqr])
    if extrema > q1:
        whislo = q1
    else:
        whislo = extrema

    return whislo, q1, med, q3, whishi
