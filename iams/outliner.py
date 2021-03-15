#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

import numpy as np


def boxplot(x, whis=1.5):
    """
    returns array with
    - lower whisker
    - first quartile
    - second quartile (median)
    - third quartile
    - upper whisker

    raises index error if x is empty
    """
    x = np.asarray(x, dtype=np.float)  # convert x to numpy array

    q1, med, q3 = np.percentile(x, [25, 50, 75])
    iqr = q3 - q1

    # get high extreme
    tmp = x[x <= q3 + whis * iqr]
    if len(tmp) == 0:
        whishi = q3
    else:
        extrema = np.max(tmp)
        if extrema < q3:
            whishi = q3
        else:
            whishi = extrema

    # get low extreme
    tmp = x[x >= q1 - whis * iqr]
    if len(tmp) == 0:
        whislo = q1
    else:
        extrema = np.min(tmp)
        if extrema > q1:
            whislo = q1
        else:
            whislo = extrema

    return whislo, q1, med, q3, whishi
