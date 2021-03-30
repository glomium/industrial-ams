#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ortools implementation for scheduler
"""

import logging
from dataclasses import dataclass
from operator import attrgetter
from ortools.sat.python import cp_model

from iams.exceptions import CanNotSchedule
from iams.interfaces import SchedulerEvent
from iams.interfaces import SchedulerInterface
from iams.interfaces import SchedulerState


logger = logging.getLogger(__name__)


@dataclass
class Interval:
    """
    Interval definitions
    """
    start_name: str
    end_name: str
    duration_name: str
    duration: int = 0
    optional: bool = True


class Event(SchedulerEvent):
    """
    Linear optimized event
    """

    def __init__(self, scheduler, *args, **kwargs):
        self._scheduler = scheduler
        super().__init__(*args, **kwargs)

    def _get_time(self, name, now):
        """
        Prepare value to be stored on event
        """
        seconds = super()._get_time(name, now)
        if seconds is None:
            return None
        return self._scheduler.convert_resolution(seconds)

    def _set_time(self, name, seconds, now):
        """
        This function uses the saved events and a new_event and
        calculates the ranges and values of the variables needed
        for the linear solver.
        """
        return super()._set_time(name, self._scheduler.convert_seconds(seconds), now)

    def get_variables(self, now=None):  # pylint: disable=too-many-statements,too-many-branches
        """
        This function uses the saved events and a new_event and
        calculates the ranges and values of the variables needed
        for the linear solver.
        """
        # read ETA
        eta = self.get_eta(now)
        eta_min = self.get_eta_min(now)
        eta_max = self.get_eta_max(now)
        if eta_min is None:
            eta_min = eta
        if eta_max is None:
            eta_max = eta

        # read ETD
        etd = self.get_etd(now)
        etd_max = self.get_etd_max(now)
        etd_min = self.get_etd_min(now)
        if etd_min is None:
            etd_min = etd
        if etd_max is None:
            etd_max = etd

        # misc variables
        duration = self._scheduler.convert_resolution(self.duration)

        data = {
            "number": self.uid,
            "etd": (etd_min, etd_max),
            "no_upper_limit": set(),
        }
        if etd_max is None:
            data["no_upper_limit"].add('etd')

        if self.state in {SchedulerState.NEW, SchedulerState.SCHEDULED}:
            data["makespan"] = (eta_min, self._scheduler.horizon if etd_max is None else etd_max)
            data["eta"] = (eta_min, eta_max)
            if etd_min is None:
                data["start"] = (eta_max, self._scheduler.horizon)
                data["finish"] = (eta_max, self._scheduler.horizon)
                data["no_upper_limit"].add('start')
                data["no_upper_limit"].add('finish')
            else:
                data["start"] = (eta_min, etd_min - duration)
                data["finish"] = (eta_min, etd_min)
            if etd_max is None:
                data["iqt"] = (0, self._scheduler.horizon)
                data["oqt"] = (0, self._scheduler.horizon)
                data["no_upper_limit"].add('iqt')
                data["no_upper_limit"].add('oqt')
            else:
                data["iqt"] = (0, etd_max - eta_min - duration)
                data["oqt"] = (0, etd_max - eta_min - duration)
            data["interval_i"] = Interval(
                start_name="eta",
                end_name="start",
                duration_name="iqt",
                duration=None,
            )
            data["interval_p"] = Interval(
                start_name="start",
                end_name="finish",
                duration_name="duration",
                duration=duration,
                optional=False,
            )
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
                duration=None,
            )
        elif self.state is SchedulerState.ARRIVED:
            data["makespan"] = (eta, etd_max)
            data["eta"] = (eta, eta)
            if etd_min is None:
                data["start"] = (eta, self._scheduler.horizon)
                data["finish"] = (eta, self._scheduler.horizon)
                data["no_upper_limit"].add('start')
                data["no_upper_limit"].add('finish')
            else:
                data["start"] = (eta, etd_min - duration)
                data["finish"] = (eta, etd_min)
            if etd_max is None:
                data["iqt"] = (0, self._scheduler.horizon)
                data["oqt"] = (0, self._scheduler.horizon)
                data["no_upper_limit"].add('iqt')
                data["no_upper_limit"].add('oqt')
            else:
                data["oqt"] = (0, etd_max - eta - duration)
                data["oqt"] = (0, etd_max - eta - duration)
            data["interval_i"] = Interval(
                start_name="eta",
                end_name="start",
                duration_name="iqt",
            )
            data["interval_p"] = Interval(
                start_name="start",
                end_name="finish",
                duration_name="duration",
                duration=duration,
                optional=self.canceled,
            )
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
            )
            data["il"] = self.eta_lane
        elif self.state is SchedulerState.STARTED:
            start = self.get_start(now)
            finish = start + duration
            data["makespan"] = (start, etd_max)
            data["start"] = (start, start)
            data["finish"] = (finish, finish)
            if etd_max is None:
                data["oqt"] = (0, self._scheduler.horizon)
                data["no_upper_limit"].add('oqt')
            else:
                data["oqt"] = (0, etd_max - finish)
            data["interval_p"] = Interval(
                start_name="start",
                end_name="finish",
                duration_name="duration",
                duration=duration,
                optional=self.canceled,
            )
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
            )
        elif self.state is SchedulerState.FINISHED:
            finish = self.get_finish(now)
            data["makespan"] = (finish, etd_max)
            data["finish"] = (finish, finish)
            if etd_max is None:
                data["oqt"] = (0, self._scheduler.horizon)
                data["no_upper_limit"].add('oqt')
            else:
                data["oqt"] = (0, etd_max - finish)
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
            )
            data["ol"] = self.etd_lane
        else:  # pragma: no cover
            raise NotImplementedError("Implementation of state %s is missing" % self.state)
        return data


class BufferScheduler(SchedulerInterface):
    """
    Generic scheduler class for buffers
    """
    # pylint: disable=too-many-locals,too-many-statements,too-many-branches,too-many-function-args
    event_class = Event

    def __init__(self, horizon, resolution=1,  # pylint: disable=keyword-arg-before-vararg,too-many-arguments
                 buffer_input=1, buffer_output=1,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._horizon = horizon
        self._resolution = resolution

        self.horizon = self.convert_resolution(horizon)

        if isinstance(buffer_input, int):  # pragma: no branch
            buffer_input = [buffer_input]
        self.buffer_input = dict(enumerate(buffer_input, 1))

        if isinstance(buffer_output, int):  # pragma: no branch
            buffer_output = [buffer_output]
        self.buffer_output = dict(enumerate(buffer_output, 1))

    def __call__(self, **kwargs):
        kwargs.update({"scheduler": self})
        return super().__call__(**kwargs)

    def __repr__(self):
        return "<%s(horizon=%s, buffer_input=%s, buffer_output=%s)>" % (
            self.__class__.__qualname__,
            self._horizon,
            list(self.buffer_input.values()),
            list(self.buffer_output.values()),
        )

    def add(self, event, now=None):
        """
        schedule the event
        """
        return self.solve_model(event, now, save=True)

    def can_schedule(self, event, now=None):
        """
        can the new event be scheduled?
        """
        return self.solve_model(event, now, save=False)

    def convert_seconds(self, value):
        """
        Prepare value to be stored on event
        """
        return value * self._resolution

    def convert_resolution(self, value):
        """
        Converts a time to an integer. The solver works only with
        integer values. The parameter resolution is used to
        set the number of seconds per timestep.
        """
        return round(value / self._resolution)

    def get_event_variables(self, events, now=None):
        """
        This function uses the saved events and a new_event and
        calculates the ranges and values of the variables needed
        for the linear solver.
        """
        events_data = {}
        sim_max = None
        sim_min = None
        for event in self.get_events(events):
            data = event.get_variables(now)
            event_min, event_max = data.pop("makespan")

            try:
                if event_min < sim_min:
                    sim_min = event_min
            except TypeError:
                sim_min = event_min

            try:
                if event_max is not None and event_max > sim_max:
                    sim_max = event_max
            except TypeError:
                sim_max = event_max

            events_data[event] = data

        if event_min < 0:
            offset = sim_min
        else:
            offset = 0
        if sim_max is None:
            sim_max = sim_min - offset + self._horizon

        return events_data, (sim_min, sim_max), offset

    @staticmethod
    def build_model(events, makespan, offset):
        """
        Uses the event-list and generates a model for the linear solver

        timelime:
        ---|-----|-----|------|-----------------|------|-----|-----|---
        eta_min eta eta_max start <duration> finish etd_min etd etd_max

        constraints: eta <= start <= finish <= etd
        """
        model = cp_model.CpModel()
        horizon_min, horizon_max = makespan
        makespans = []

        for event, data in events.items():
            new_data = {}
            number = data.pop("number")

            # intervals
            previous = None
            for key, name in {"i": "interval_i", "p": "interval_p", "o": "interval_o"}.items():
                if name not in data:
                    continue
                interval = data[name]
                if interval.start_name not in new_data:
                    var_min, var_max = data.pop(interval.start_name)
                    new_data[interval.start_name] = model.NewIntVar(
                        var_min - offset,
                        var_max - offset,
                        f'{interval.start_name}_{number}',
                    )

                if interval.end_name not in new_data:
                    var_min, var_max = data.pop(interval.end_name)
                    new_data[interval.end_name] = model.NewIntVar(
                        (horizon_min if var_min is None else var_min) - offset,
                        (horizon_max if var_max is None else var_max) - offset,
                        f'{interval.end_name}_{number}',
                    )

                if interval.duration_name not in new_data:
                    if interval.duration_name in data:
                        var_min, var_max = data.pop(interval.duration_name)
                        new_data[interval.duration_name] = model.NewIntVar(
                            var_min,
                            var_max,
                            f'{interval.duration_name}_{number}',
                        )
                    else:
                        new_data[interval.duration_name] = model.NewIntVar(
                            0 if interval.optional else interval.duration,
                            interval.duration,
                            f'{interval.duration_name}_{number}',
                        )

                    new_data[name] = model.NewIntervalVar(
                        new_data[interval.start_name],  # start
                        new_data[interval.duration_name],  # size
                        new_data[interval.end_name],  # end
                        f'int_{key}_{number}',
                    )

                    if previous:
                        model.Add(new_data[previous] <= new_data[interval.start_name])
                    previous = interval.start_name

            # TODO
            # for name, storage in [("ol", self.buffer_output), ("il", self.buffer_input)]:
            #     var = f'{name}_{number}'
            #     if data[name] is None:
            #         new_data[name] = model.NewIntVar(1, len(storage), var)
            #     else:
            #         new_data[name] = model.NewIntVar(data[name], data[name], var)
            events[event] = new_data
        return model, makespans, events

    def optimize_model(self, model, events, offset, now, save):  # pylint: disable=too-many-arguments
        """
        optimizes the model with a CP-solver
        """
        intervals = [data["interval_i"] for data in events.values() if "interval_i" in data]
        model.AddCumulative(intervals, [1] * len(intervals), self.buffer_input[1])
        intervals = [data["interval_p"] for data in events.values() if "interval_p" in data]
        model.AddCumulative(intervals, [1] * len(intervals), 1)
        intervals = [data["interval_o"] for data in events.values() if "interval_o" in data]
        model.AddCumulative(intervals, [1] * len(intervals), self.buffer_input[1])

        model.Minimize(sum([data["finish"] for data in events.values()]) + sum([data["etd"] for data in events.values()]))  # noqa

        solver = cp_model.CpSolver()

        try:
            solver.Solve(model)
        except Exception as exception:  # pragma: no cover
            logger.exception("Solver failed")
            raise CanNotSchedule('Solver failed') from exception

        # log = []
        # log.append(len(events))
        # log.append(solver.StatusName())
        # for event, data in events.items():
        #     log.append(event)
        #     log.append(data)
        #     for name in ["eta", "iqt", "start", "duration", "finish", "oqt", "etd"]:
        #         if name not in data:
        #             continue
        #         # log.append([data[name], solver.Value(data[name])])
        # print('*' * 80)
        # print('\n'.join(["%s" % x for x in log]))

        # solver needs to be optimal to result in a match
        if solver.StatusName() not in ["OPTIMAL"]:
            # raise ValueError('\n'.join(["%s" % x for x in log]))
            raise CanNotSchedule('Solver returned %s' % solver.StatusName())

        for event, data in events.items():
            if event.state == SchedulerState.NEW:
                event.set_eta(solver.Value(data["eta"]) + offset, now)
                event.set_start(solver.Value(data["start"]) + offset, now)
                event.set_finish(solver.Value(data["finish"]) + offset, now)
                event.set_etd(solver.Value(data["etd"]) + offset, now)

        for lane in self.buffer_input:  # pylint: disable=unused-variable
            data = []
            for event in events:
                if event.state not in {SchedulerState.NEW, SchedulerState.SCHEDULED, SchedulerState.ARRIVED}:
                    continue
                # continue if event is not in buffer_input
                data.append(event)
            previous = None
            for event in sorted(data, key=attrgetter('eta', 'etd', 'uid')):
                if previous is None:
                    previous = event
                    continue

                if event.state == SchedulerState.NEW or event.eta_min is None or save:
                    if event.eta_min:
                        event.eta_min = max([previous.eta, event.eta_min])
                    else:
                        event.eta_min = previous.eta

                if previous.state == SchedulerState.NEW or previous.eta_max is None or save:
                    if previous.eta_max:
                        previous.eta_max = min([event.eta, previous.eta_max])
                    else:
                        previous.eta_max = event.eta

                previous = event

        for lane in self.buffer_output:  # pylint: disable=unused-variable
            data = []
            for event in events:
                # continue if event is not in buffer_input
                data.append(event)
            previous = None
            for event in sorted(data, key=attrgetter('etd', 'uid')):

                if event.etd_min is None or (save and event.etd_min < event.schedule_finish):
                    event.etd_min = event.schedule_finish

                if previous is None:
                    previous = event
                    continue

                if event.state == SchedulerState.NEW or event.etd_min is None or save:
                    if event.etd_min:
                        event.etd_min = max([previous.etd, event.etd_min])
                    else:
                        event.etd_min = previous.etd

                if previous.state == SchedulerState.NEW or previous.etd_max is None or save:
                    if previous.etd_max:
                        previous.etd_max = min([event.etd, previous.etd_max])
                    else:
                        previous.etd_max = event.etd

                previous = event

        if save:
            for event in data:
                if event.state == SchedulerState.NEW:
                    event.state = SchedulerState.SCHEDULED

        if not save:
            return True

        # raise ValueError('\n'.join(["%s" % x for x in log]))
        dummy = None
        return dummy

    @staticmethod
    def optimize_eta(events, event):
        """
        optimize event's eta
        """

    @staticmethod
    def optimize_etd(events, event):
        """
        optimize event's etd
        """

    def solve_model(self, new_event, now=None, save=False):
        """
        solve model with linear optimization
        """
        # pylint: disable=unused-variable
        new_events, makespan, offset = self.get_event_variables(new_event, now=now)
        model, makespans, events = self.build_model(new_events, makespan, offset)

        self.optimize_model(model, events, offset, now, save)

        return new_event
