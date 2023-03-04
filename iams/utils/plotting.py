#!/usr/bin/python
# ex:set fileencoding=utf-8:

"""
Helper to plot simulated data
"""

from abc import ABC
from abc import abstractmethod
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd


class PlotInterface(ABC):
    """
    main class
    """

    def __init__(self, directory, workers=None, save=None):  # pylint: disable=too-many-branches
        self.data = []
        self.dataframe = None
        names = {}
        if save:
            save = Path(save)
            if save.is_file():
                self.dataframe = pd.read_csv(save).set_index("basename")
                names = set(self.dataframe.index.values)
            elif save.exists():
                raise ValueError(f"{save} already exists and is not a file")

        with ProcessPoolExecutor(max_workers=workers) as executor:
            for path in Path(directory).iterdir():
                if not path.is_file():
                    continue
                parameters = self.parameters(path.name)
                if not isinstance(parameters, dict) or self.basename(path) in names:
                    continue
                executor.submit(self.load_dataframe, path, parameters).add_done_callback(self.handler)

        if self.data:
            columns = tuple(self.data[0].keys())
            new_data = pd.DataFrame(
                self.generate(columns),
                columns=columns,
            ).set_index("basename")

            if self.dataframe is None:
                self.dataframe = new_data
            else:
                self.dataframe = self.dataframe.append(new_data)

            self.dataframe = self.dataframe.sort_values(['basename'])

            if save is not None:
                self.dataframe.to_csv(save)

        if self.dataframe is not None:
            self.dataframe = self.prepare_aggregated_dataframe(self.dataframe)
            with ProcessPoolExecutor(max_workers=workers) as executor:
                try:
                    for function in self.iterator_aggregated_plots():
                        executor.submit(function, self.dataframe).add_done_callback(self.handler_aggregated)
                except TypeError:
                    pass

    @abstractmethod
    def parameters(self, name):
        """
        get parameters from name
        """

    @staticmethod
    @abstractmethod
    def iterator_individual_plots():
        """
        return functions to draw individual plots
        """

    @staticmethod
    @abstractmethod
    def iterator_aggregated_plots():
        """
        return functions to draw aggregated plots
        """

    @staticmethod
    def basename(path):
        """
        returns the path to the read file without the files extension
        """
        return str(path).rsplit('.', 1)[0]

    @classmethod
    def load_dataframe(cls, path, parameters):
        """
        load the pandas dataframe for path
        """
        dataframe = cls.prepare_individual_dataframe(pd.read_csv(path))
        basename = cls.basename(path)
        data = {}

        # load individual plots and plot them
        for function in cls.iterator_individual_plots():
            result = function(basename, parameters, dataframe)
            if isinstance(result, dict):  # pragma: no branch
                data.update(result)

        # update commona parameters
        data.update(parameters)
        data["basename"] = basename
        return data

    def generate(self, columns):
        """
        generate data
        """
        for row in self.data:
            yield tuple([row[column] for column in columns])  # pylint: disable=consider-using-generator

    def handler(self, future):
        """
        callback from process
        """
        self.data.append(future.result())

    @staticmethod
    def handler_aggregated(future):
        """
        callback from aggregated process
        """
        future.result()

    @staticmethod
    def prepare_aggregated_dataframe(dataframe):
        """
        Pre-process the aggregated dataframe
        """
        return dataframe

    @staticmethod
    def prepare_individual_dataframe(dataframe):
        """
        Pre-process the individual dataframe
        """
        return dataframe
