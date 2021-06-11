#!/usr/bin/python
# ex:set fileencoding=utf-8:
"""
System used as a benchmark and modelled according to Pagani et.al. DOI: 10.2195/lj_Proc_pagani_en_201710_01
https://www.logistics-journal.de/proceedings/2017/4591/pagani_en_2017.pdf
"""

import re

from itertools import product

import matplotlib.pyplot as plt

from iams.utils.plotting import PlotInterface


def plot_th(dataframe):
    """
    plot th graph
    """
    fig, ax = plt.subplots()  # pylint: disable=invalid-name
    for selection in product(dataframe.index.unique('version'), dataframe.index.unique('run')):
        data = dataframe.loc[selection]
        ax.plot(data.index, data["th"], lw=0.2)
    ax.set_ylabel('%TH')
    ax.set_xlabel('load and unload time')

    fig.savefig('loadtimes.png', dpi=300)
    plt.close()

    data = dataframe.loc['no', slice(None), 30]['th'] * 100
    print("load times: %.4f +/- %.4f" % (data.median(), data.std()))  # noqa


def plot_distance(dataframe):
    """
    plot th graph
    """
    fig, ax = plt.subplots()  # pylint: disable=invalid-name
    for selection in product(dataframe.index.unique('version'), dataframe.index.unique('run')):
        data = dataframe.loc[selection]
        ax.plot(data.index, data["distance"], lw=0.2)
    ax.set_ylabel('average trip distance')
    ax.set_xlabel('load and unload time')

    fig.savefig('distance.png', dpi=300)
    plt.close()


def plot_buffers(name, parameters, df):
    """
    plot stats for one run
    """
    fig, axes = plt.subplots(nrows=14, ncols=1, sharex=True)
    axes[0].plot(df.time, df.MS1_buffer, lw=0.2)
    axes[1].plot(df.time, df.MD1_buffer, lw=0.2)
    axes[2].plot(df.time, df.MS2_buffer, lw=0.2)
    axes[3].plot(df.time, df.MD2_buffer, lw=0.2)
    axes[4].plot(df.time, df.MS3_buffer, lw=0.2)
    axes[5].plot(df.time, df.MD3_buffer, lw=0.2)
    axes[6].plot(df.time, df.MS4_buffer, lw=0.2)
    axes[7].plot(df.time, df.MD4_buffer, lw=0.2)
    axes[8].plot(df.time, df.MS5_buffer, lw=0.2)
    axes[9].plot(df.time, df.MD5_buffer, lw=0.2)
    axes[10].plot(df.time, df.V1_jobs, lw=0.2)
    axes[11].plot(df.time, df.V2_jobs, lw=0.2)
    axes[12].plot(df.time, df.V3_jobs, lw=0.2)
    axes[13].plot(df.time, df.V4_jobs, lw=0.2)

    axes[0].set_ylabel('S1')
    axes[1].set_ylabel('D2')
    axes[2].set_ylabel('S2')
    axes[3].set_ylabel('D2')
    axes[4].set_ylabel('S3')
    axes[5].set_ylabel('D3')
    axes[6].set_ylabel('S4')
    axes[7].set_ylabel('D4')
    axes[8].set_ylabel('S5')
    axes[9].set_ylabel('D5')
    axes[10].set_ylabel('V1')
    axes[11].set_ylabel('V2')
    axes[12].set_ylabel('V3')
    axes[13].set_ylabel('V4')

    axes[13].set_xlabel('time')
    fig.savefig(name + '.png', dpi=300)
    plt.close()


def get_data(name, parameters, df):
    row = df.tail(1)
    th_out = row.MD1_consumed + row.MD2_consumed + row.MD3_consumed + row.MD4_consumed + row.MD5_consumed
    th_out = th_out.values[0]
    th_lost = row.MD1_missed + row.MD2_missed + row.MD3_missed + row.MD4_missed + row.MD5_missed
    th_lost = th_lost.values[0]
    th = th_out / (th_out + th_lost)

    distance = row.V1_distance + row.V2_distance + row.V3_distance + row.V4_distance
    distance = distance.values[0]

    count = row.V1_count + row.V2_count + row.V3_count + row.V4_count
    count = count.values[0]

    return {"th": th, "distance": distance / count}


class Main(PlotInterface):
    """
    main class
    """
    def __init__(self, *args, **kwargs):
        self.regex = re.compile(r'run([A-Z]?)-([0-9]{2})-([0-9]{2})\.dat')
        super().__init__(*args, **kwargs)

    @staticmethod
    def prepare_aggregated_dataframe(dataframe):
        """
        Pre-process the aggregated dataframe
        """
        return dataframe.set_index(['version', 'run', 'load'])

    def parameters(self, name):
        match = self.regex.match(name)
        if match is None:
            return None
        # read variables from regex groups
        version, run, load = match.groups()
        return {
            "version": version or 'no',
            "run": run,
            "load": int(load),
        }

    @staticmethod
    def iterator_individual_plots():
        yield get_data
        yield plot_buffers

    @staticmethod
    def iterator_aggregated_plots():
        yield plot_distance
        yield plot_th


if __name__ == "__main__":
    main = Main("results", 8, "data.csv")
