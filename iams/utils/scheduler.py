#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ortools implementation for scheduler
"""

import logging
from dataclasses import dataclass
# from operator import attrgetter
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

    def eta_constraints(self, now=None):
        low, high = super().eta_constraints(now)
        if low is not None:
            low = self._scheduler.convert_resolution(low)
        if high is not None:
            high = self._scheduler.convert_resolution(low)
        return low, high

    def etd_constraints(self, now=None):
        low, high = super().etd_constraints(now)
        if low is not None:
            low = self._scheduler.convert_resolution(low)
        if high is not None:
            high = self._scheduler.convert_resolution(low)
        return low, high

    def get_variables(self, now=None):  # pylint: disable=too-many-statements,too-many-branches
        """
        This function uses the saved events and a new_event and
        calculates the ranges and values of the variables needed
        for the linear solver.
        """
        data = {
            "number": self.uid,
            "ranges": set(),
        }
        duration = self._scheduler.convert_resolution(self.duration)

        if self.state in {SchedulerState.NEW, SchedulerState.SCHEDULED}:
            data["ranges"].add("eta")
            data["ranges"].add("start")
            data["ranges"].add("finish")
            data["ranges"].add("etd")
            data["eta"] = self.eta_constraints(now)
            data["etd"] = self.etd_constraints(now)
            data["start"] = data["eta"][1], data["etd"][0]
            data["finish"] = data["eta"][1], data["etd"][0]
            data["makespan"] = data["eta"][0], data["etd"][1]

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
            eta = self._scheduler.convert_resolution(self.eta.get(now))
            data["eta"] = (eta, eta)
            data["ranges"].add("eta")
            data["ranges"].add("start")
            data["ranges"].add("finish")
            data["ranges"].add("etd")

            data["etd"] = list(self.etd_constraints(now))
            if data["etd"][0] is None:
                data["etd"][0] = eta
            data["etd"] = tuple(data["etd"])
            data["makespan"] = eta, data["etd"][1]

            data["start"] = eta, data["etd"][1]
            data["finish"] = eta, data["etd"][1]

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
                optional=self.canceled,
            )
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
            )
            data["il"] = self.eta_lane

        elif self.state is SchedulerState.STARTED:
            eta = self._scheduler.convert_resolution(self.eta.get(now))
            start = self._scheduler.convert_resolution(self.get_start(now))
            data["eta"] = (eta, eta)
            data["start"] = (start, start)
            data["finish"] = (start + duration, start + duration)
            data["ranges"].add("eta")
            data["ranges"].add("start")
            data["ranges"].add("finish")
            data["ranges"].add("etd")

            data["etd"] = list(self.etd_constraints(now))
            if data["etd"][0] is None:
                data["etd"][0] = start
            data["etd"] = tuple(data["etd"])
            data["makespan"] = eta, data["etd"][1]

            data["interval_i"] = Interval(
                start_name="eta",
                end_name="start",
                duration_name="iqt",
                duration=start - eta,
                optional=False,
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
                duration=None,
            )
        elif self.state is SchedulerState.FINISHED:
            start = self._scheduler.convert_resolution(self.get_start(now))
            finish = self._scheduler.convert_resolution(self.get_finish(now))
            data["ranges"].add("start")
            data["ranges"].add("finish")
            data["ranges"].add("etd")
            data["start"] = (start, start)
            data["finish"] = (finish, finish)

            data["etd"] = list(self.etd_constraints(now))
            if data["etd"][0] is None:
                data["etd"][0] = finish
            data["etd"] = tuple(data["etd"])
            data["makespan"] = start, data["etd"][1]

            data["interval_p"] = Interval(
                start_name="start",
                end_name="finish",
                duration_name="duration",
                duration=finish - start,
                optional=False,
            )
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
                duration=None,
            )
            data["ol"] = self.etd_lane

        elif self.state is SchedulerState.DEPARTED:
            start = self._scheduler.convert_resolution(self.get_start(now))
            finish = self._scheduler.convert_resolution(self.get_finish(now))
            etd = self._scheduler.convert_resolution(self.etd.get(now))

            data["ranges"].add("start")
            data["ranges"].add("finish")
            data["ranges"].add("etd")
            data["start"] = (start, start)
            data["finish"] = (finish, finish)
            data["etd"] = (etd, etd)
            data["makespan"] = start, etd

            data["interval_p"] = Interval(
                start_name="start",
                end_name="finish",
                duration_name="duration",
                duration=finish - start,
                optional=False,
            )
            data["interval_o"] = Interval(
                start_name="finish",
                end_name="etd",
                duration_name="oqt",
                duration=etd - finish,
                optional=False,
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
        self.max_horizon = self.horizon

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

    def debug(self, events=None, now=None):
        """
        log debug informations
        """
        events, makespan = self.get_event_variables(events or [], now=now)
        logger.warning("Makespan: %s", makespan)
        for key, value in events.items():
            logger.warning("%s: %s", key, value)
        model, events, offset = self.build_model(events, makespan)  # pylint: disable=unused-variable
        logger.warning("Offset: %s", offset)
        for key, value in events.items():
            logger.warning("%s", key)
            for var, val in value.items():
                logger.warning("%s: %r", var, val)

        solver = cp_model.CpSolver()
        solver.Solve(model)
        status = solver.StatusName()
        logger.warning("solved model: %s", status)

        if status not in {'INFEASIBLE'}:
            for event, data in events.items():
                logger.warning("event %s", event)
                for name in ["eta", "iqt", "start", "duration", "finish", "oqt", "etd"]:
                    if name not in data:
                        continue
                    logger.warning("%s(%s) = %s", name, data[name], solver.Value(data[name]))

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

    def validate(self, now=None):
        """
        can the new event be scheduled?
        """
        try:
            self.solve_model([], now, save=False)
        except CanNotSchedule:
            return False
        return True

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
        events_max = []
        events_min = []
        none_max = False
        none_min = False
        sim_max = None
        sim_min = None

        for event in self.get_events(events):
            data = event.get_variables(now)
            event_min, event_max = data.pop("makespan")
            if event_min is None:
                none_min = True
            else:
                events_min.append(event_min)
            if event_max is None:
                none_max = True
            else:
                events_max.append(event_max)
            events_data[event] = data

        if not events_max and not events_min:
            sim_min, sim_max = 0, self.horizon
        elif not events_max:
            sim_max = max(events_min) + self.horizon
            sim_min = min(events_min)
        elif not events_min:
            sim_max = max(events_max)
            sim_min = min(events_max) - self.horizon
        else:
            sim_max = max(events_max)
            sim_min = min(events_min)

            diff = sim_max - sim_min
            if diff < self.horizon:
                if none_min and none_max:
                    diff = round((self.horizon - diff) / 2)
                    sim_max += diff
                    sim_min -= diff
                elif none_min:
                    sim_min = sim_max - self.horizon
                elif none_max:
                    sim_max = sim_min + self.horizon

        self.max_horizon = max([self.max_horizon, sim_max])
        # print(events_min, events_max, sim_min, sim_max, none_min, none_max)
        return events_data, (sim_min, self.max_horizon)

    def build_model(self, events, makespan):
        """
        Uses the event-list and generates a model for the linear solver

        timelime:
        ---|-----|-----|------|-----------------|------|-----|-----|---
        eta_min eta eta_max start <duration> finish etd_min etd etd_max

        constraints: eta <= start <= finish <= etd
        """
        model = cp_model.CpModel()

        offset = makespan[0]
        horizon = makespan[1] - offset

        for event, data in events.items():
            logger.debug("build model for %s", event)
            new_data = {}
            number = data.pop("number")

            # create variables that don't have an upper limit
            for variable in data['ranges']:
                lower, upper = data.pop(variable)
                if lower is None:
                    lower = 0
                else:
                    lower -= offset
                if upper is None:
                    upper = horizon
                else:
                    upper -= offset

                new_data[variable] = model.NewIntVar(
                    lower,
                    upper,
                    f'{variable}_{number}',
                )

            # intervals
            previous = None
            for key, name in {"i": "interval_i", "p": "interval_p", "o": "interval_o"}.items():
                if name not in data:
                    continue

                interval = data[name]

                # load fixed values
                if interval.start_name not in new_data:
                    raise ValueError("Need to set %s" % interval.start_name)

                if interval.end_name not in new_data:
                    raise ValueError("Need to set %s" % interval.end_name)

                if interval.duration_name not in new_data:
                    # pylint: disable=protected-access
                    if interval.duration is None:
                        # lower = new_data[interval.start_name]
                        # # if not isinstance(lower, int):  # extract data from or-tools object
                        # if len(lower._IntVar__var.domain) == 2:
                        #     lower = lower._IntVar__var.domain[0]  # pylint: disable=protected-access
                        # else:
                        #     self.debug()
                        #     raise NotImplementedError("%r(%s) is an invalid variable (%s:%s)" % (
                        #         interval, lower, type(lower._IntVar__var.domain), lower._IntVar__var.domain,
                        #     ))
                        # upper = new_data[interval.end_name]
                        # # if not isinstance(upper, int):  # extract data from or-tools object
                        # if len(upper._IntVar__var.domain) == 2:
                        #     upper = upper._IntVar__var.domain[1]  # pylint: disable=protected-access
                        # else:
                        #     self.debug()
                        #     raise NotImplementedError("%r(%s) is an invalid variable (%s:%s)" % (
                        #         interval, upper, type(upper._IntVar__var.domain), upper._IntVar__var.domain,
                        #     ))
                        # duration = upper - lower
                        duration = horizon
                    else:
                        duration = interval.duration

                    new_data[interval.duration_name] = model.NewIntVar(
                        0 if interval.optional else duration,
                        duration,
                        f'{interval.duration_name}_{number}',
                    )

                new_data[name] = model.NewIntervalVar(
                    new_data[interval.start_name],  # start
                    new_data[interval.duration_name],  # size
                    new_data[interval.end_name],  # end
                    f'int_{key}_{number}',
                )

                # print("add constraint %s <= %s" % (previous, interval.start_name))
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

        previous = None
        states_eta = {SchedulerState.NEW, SchedulerState.SCHEDULED, SchedulerState.ARRIVED}
        for event in sorted(events.keys()):
            logger.debug("%s", event)
            if previous:
                if previous.state in states_eta and event.state in states_eta:
                    model.Add(events[previous]["eta"] <= events[event]["eta"])
                    model.Add(events[previous]["start"] <= events[event]["start"])
                # elif previous.state == SchedulerState.STARTED and event.state == SchedulerState.STARTED:
                #     model.Add(events[previous]["start"] <= events[event]["start"])
                # elif previous.state == SchedulerState.FINISHED and event.state == SchedulerState.FINISHED:
                #     model.Add(events[previous]["finish"] <= events[event]["finish"])
            previous = event

        intervals = [data["interval_i"] for data in events.values() if "interval_i" in data]
        model.AddCumulative(intervals, [1] * len(intervals), self.buffer_input[1])
        intervals = [data["interval_p"] for data in events.values() if "interval_p" in data]
        model.AddCumulative(intervals, [1] * len(intervals), 1)
        intervals = [data["interval_o"] for data in events.values() if "interval_o" in data]
        model.AddCumulative(intervals, [1] * len(intervals), self.buffer_input[1])

        # minimize this
        model.Minimize(sum([data["etd"] for data in events.values()]))  # noqa

        return model, events, offset

    def optimize_model(self, model, events, offset, now, save):  # pylint: disable=too-many-arguments
        """
        optimizes the model with a CP-solver
        """
        solver = cp_model.CpSolver()

        try:
            solver.Solve(model)
        except Exception as exception:  # pragma: no cover
            logger.exception("Solver failed")
            raise CanNotSchedule('Solver failed') from exception

        # solver needs to be optimal to result in a match
        if solver.StatusName() not in ["OPTIMAL"]:
            raise CanNotSchedule('Solver returned %s' % solver.StatusName())

        for event, data in events.items():
            if event.state == SchedulerState.NEW:
                event.eta.set(self.convert_seconds(solver.Value(data["eta"]) + offset), now)
                event.set_start(solver.Value(data["start"]) + offset, now)
                event.set_finish(solver.Value(data["finish"]) + offset, now)
                event.etd.set(self.convert_seconds(solver.Value(data["etd"]) + offset), now)
            elif event.state == SchedulerState.SCHEDULED:
                event.set_start(solver.Value(data["start"]) + offset, now)
                event.set_finish(solver.Value(data["finish"]) + offset, now)
            elif event.state == SchedulerState.ARRIVED:
                event.set_start(solver.Value(data["start"]) + offset, now)
                event.set_finish(solver.Value(data["finish"]) + offset, now)
            elif event.state == SchedulerState.STARTED:
                event.set_finish(solver.Value(data["finish"]) + offset, now)

        # for lane in self.buffer_input:  # pylint: disable=unused-variable
        #     data = []
        #     for event in events:
        #         if event.state not in {SchedulerState.NEW, SchedulerState.SCHEDULED, SchedulerState.ARRIVED}:
        #             continue
        #         # continue if event is not in buffer_input
        #         data.append(event)
        #     previous = None
        #     for event in sorted(data, key=attrgetter('eta', 'etd', 'uid')):
        #         if previous is None:
        #             previous = event
        #             continue

        #         if event.state == SchedulerState.NEW or event.eta_min is None or save:
        #             if event.eta_min:
        #                 event.eta_min = max([previous.eta, event.eta_min])
        #             else:
        #                 event.eta_min = previous.eta

        #         if previous.state == SchedulerState.NEW or previous.eta_max is None or save:
        #             if previous.eta_max:
        #                 previous.eta_max = min([event.eta, previous.eta_max])
        #             else:
        #                 previous.eta_max = event.eta

        #         previous = event

        # for lane in self.buffer_output:  # pylint: disable=unused-variable
        #     data = []
        #     for event in events:
        #         # continue if event is not in buffer_input
        #         data.append(event)
        #     previous = None
        #     for event in sorted(data, key=attrgetter('etd', 'uid')):

        #         if event.etd_min is None or (save and event.etd_min < event.schedule_finish):
        #             event.etd_min = event.schedule_finish

        #         if previous is None:
        #             previous = event
        #             continue

        #         if event.state == SchedulerState.NEW or event.etd_min is None or save:
        #             if event.etd_min:
        #                 event.etd_min = max([previous.etd, event.etd_min])
        #             else:
        #                 event.etd_min = previous.etd

        #         if previous.state == SchedulerState.NEW or previous.etd_max is None or save:
        #             if previous.etd_max:
        #                 previous.etd_max = min([event.etd, previous.etd_max])
        #             else:
        #                 previous.etd_max = event.etd

        #         previous = event

        if not save:
            return True
        return None

        # # raise ValueError('\n'.join(["%s" % x for x in log]))
        # dummy = None
        # return dummy

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
        new_events, makespan = self.get_event_variables(new_event, now=now)
        model, events, offset = self.build_model(new_events, makespan)
        self.optimize_model(model, events, offset, now, save)

        return new_event
