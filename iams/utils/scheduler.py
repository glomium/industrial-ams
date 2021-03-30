#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ortools implementation for scheduler
"""

import logging
from operator import attrgetter
from ortools.sat.python import cp_model

from iams.exceptions import CanNotSchedule
from iams.interfaces import SchedulerInterface
from iams.interfaces import SchedulerState


logger = logging.getLogger(__name__)


class BufferScheduler(SchedulerInterface):
    """
    Generic scheduler class for buffers
    """
    # pylint: disable=too-many-locals,too-many-statements,too-many-branches,too-many-function-args

    def __init__(self, horizon, resolution=1.0,  # pylint: disable=keyword-arg-before-vararg,too-many-arguments
                 buffer_input=1, buffer_output=1,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.resolution = resolution
        self.horizon = self.convert(horizon)

        if isinstance(buffer_input, int):  # pragma: no branch
            buffer_input = [buffer_input]
        self.buffer_input = dict(enumerate(buffer_input, 1))

        if isinstance(buffer_output, int):  # pragma: no branch
            buffer_output = [buffer_output]
        self.buffer_output = dict(enumerate(buffer_output, 1))

    def __repr__(self):
        return "<%s(horizon=(%s * %s), buffer_input=%s, buffer_output=%s)>" % (
            self.__class__.__qualname__,
            self.horizon,
            self.resolution,
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

    def store(self, value):
        """
        Prepare value to be stored on event
        """
        return value * self.resolution

    def convert(self, value):
        """
        Converts a time to an integer. The solver works only with
        integer values. The parameter resolution is used to
        set the number of seconds per timestep.
        """
        return round(value / self.resolution)

    def get_event_variables(self, events, now=None):
        """
        This function uses the saved events and a new_event and
        calculates the ranges and values of the variables needed
        for the linear solver.
        """
        events_data = {}
        makespan = 0
        offset = 0
        for event in self.get_events(events):
            # read ETA
            eta = event.get_eta(now)
            eta_min = event.get_eta_min(now)
            eta_max = event.get_eta_max(now)
            if eta is not None:
                eta = self.convert(eta)
            if eta_min is not None:
                eta_min = self.convert(eta_min)
            else:
                eta_min = eta
            if eta_max is not None:
                eta_max = self.convert(eta_max)
            else:
                eta_max = eta
            if eta_min is not None and eta_min < offset:
                offset = eta_min

            # read ETD
            etd = event.get_etd(now)
            etd_max = event.get_etd_max(now)
            etd_min = event.get_etd_min(now)
            if etd is not None:
                etd = self.convert(etd)
            if etd_min is not None:
                etd_min = self.convert(etd_min)
            else:
                etd_min = etd
            if etd_max is not None:
                etd_max = self.convert(etd_max)
            else:
                etd_max = etd
            if etd_min is not None and etd_min < offset:
                offset = etd_min

            if etd_max is None:
                makespan = None
            elif makespan is not None and makespan < etd_max:
                makespan = etd_max

            # misc variables
            duration = self.convert(event.duration)
            data = {
                "number": event.uid,
                "etd": (etd_min, etd_max),
            }
            if event.state in {SchedulerState.NEW, SchedulerState.SCHEDULED}:
                data["eta"] = (eta_min, eta_max)
                data["production"] = (eta_max, duration, etd_min)
            elif event.state is SchedulerState.ARRIVED:
                data["canceled"] = event.canceled
                data["eta"] = (eta, eta)
                data["il"] = event.eta_lane
                data["production"] = (eta, duration, etd_min)
            elif event.state is SchedulerState.STARTED:
                start = self.convert(event.get_start(now))
                data["canceled"] = event.canceled
                data["production"] = (start, duration, start + duration)
            elif event.state is SchedulerState.FINISHED:
                finish = self.convert(event.get_finish(now))
                data["finish"] = finish
                data["ol"] = event.etd_lane
            else:  # pragma: no cover
                raise NotImplementedError("Implementation of state %s is missing" % event.state)
            events_data[event] = data
        return events_data, makespan, offset

    def build_model(self, events, offset):
        """
        Uses the event-list and generates a model for the linear solver

        timelime:
        ---|-----|-----|------|-----------------|------|-----|-----|---
        eta_min eta eta_max start <duration> finish etd_min etd etd_max

        constraints: eta <= iq <= oq <= etd
        """
        model = cp_model.CpModel()
        makespans = []

        for event, data in events.items():
            new_data = {}
            intervals = {}
            number = data["number"]

            # first variable
            if "eta" in data:
                value_min, value_max = data["eta"]
                new_data["eta"] = model.NewIntVar(value_min - offset, value_max - offset, f'eta_{number}')
                # TODO: a dataclass to store intervalls would be nice
                intervals['i'] = [
                    ("eta", (value_min - offset)),
                    None,
                    (None, False),
                ]

            # second and third variable
            if "production" in data:
                value_min, duration, value_max = data["production"]
                if value_max is None:
                    new_data["start"] = model.NewIntVar(
                        value_min - offset,
                        self.horizon - offset,
                        f's_{number}',
                    )
                    new_data["finish"] = model.NewIntVar(
                        value_min - offset + duration,
                        self.horizon - offset,
                        f'f_{number}',
                    )
                    try:
                        intervals['i'][1] = ("start", None)
                    except KeyError:
                        pass
                    intervals['p'] = [
                        ("start", value_min),
                        ("finish", None),
                        (duration, event.canceled),
                    ]
                    intervals['o'] = [
                        ("finish", (value_min + duration)),
                        None,
                        (None, False),
                    ]
                    makespans.append(new_data["start"])
                    makespans.append(new_data["finish"])
                else:
                    new_data["start"] = model.NewIntVar(
                        value_min - offset,
                        value_max - offset - duration,
                        f's_{number}',
                    )
                    new_data["finish"] = model.NewIntVar(
                        value_min - offset + duration,
                        value_max - offset,
                        f'f_{number}',
                    )
                    try:
                        intervals['i'][1] = ("start", (value_max - duration))
                    except KeyError:
                        pass
                    intervals['p'] = [
                        ("start", value_min),
                        ("finish", value_max),
                        (duration, event.canceled),
                    ]
                    intervals['o'] = [
                        ("finish", (value_min + duration)),
                        None,
                        (None, False),
                    ]
                    makespans.append(new_data["start"])
                    makespans.append(new_data["finish"])
                finish_min = value_min + duration
            elif "finish" in data:
                new_data["finish"] = model.NewIntVar(data["finish"] - offset, data["finish"] - offset, f'f_{number}')
                intervals['o'] = [
                    ("finish", (data["finish"])),
                    None,
                    (None, False),
                ]
                finish_min = data["finish"]

            # fourth variable
            value_min, value_max = data["etd"]
            if value_min is None:
                value_min = finish_min
            if value_max is None:
                new_data["etd"] = model.NewIntVar(value_min - offset, self.horizon, f'etd_{number}')
                intervals['o'][1] = ("etd", None)
                makespans.append(new_data["etd"])
            else:
                new_data["etd"] = model.NewIntVar(value_min - offset, value_max - offset, f'etd_{number}')
                intervals['o'][1] = ("etd", value_max)

            # intervals
            previous = None
            for key, name in {"i": "itq", "p": "duration", "o": "otq"}.items():
                if key not in intervals:
                    continue
                name_s, range_min = intervals[key][0]
                name_e, range_max = intervals[key][1]
                duration, canceled = intervals[key][2]

                if previous:
                    model.Add(new_data[previous] <= new_data[name_s])
                previous = name_e

                if range_max is None:
                    range_max = self.horizon

                if canceled is True and duration is not None:
                    new_data[name] = model.NewIntVar(0, duration, f'{name}_{number}')
                elif duration is None:
                    new_data[name] = model.NewIntVar(0, range_max - range_min, f'{name}_{number}')
                else:
                    new_data[name] = model.NewIntVar(duration, duration, f'{name}_{number}')

                new_data[f"interval_{key}"] = model.NewIntervalVar(
                    new_data[name_s],  # start
                    new_data[name],  # size
                    new_data[name_e],  # end
                    f'int_{key}_{number}',
                )

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
        # print(len(events))
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
        # solver needs to be optimal to result in a match

        if solver.StatusName() not in ["OPTIMAL"]:
            raise CanNotSchedule('Solver returned %s' % solver.StatusName())

        # log = []
        # log.append(len(events))
        # log.append(solver.StatusName())
        # for event, data in events.items():
        #     log.append(event)
        #     log.append(data)
        #     for name in ["eta", "iqt", "start", "duration", "finish", "oqt", "etd"]:
        #         if name not in data:
        #             continue
        #         log.append([data[name], solver.Value(data[name])])
        # print('*' * 80)
        # print('\n'.join(["%s" % x for x in log]))
        # raise ValueError('\n'.join(["%s" % x for x in log]))

        for event, data in events.items():
            if event.state == SchedulerState.NEW:
                event.set_eta(self.store(solver.Value(data["eta"]) + offset), now)
                event.set_start(self.store(solver.Value(data["start"]) + offset), now)
                event.set_finish(self.store(solver.Value(data["finish"]) + offset), now)
                event.set_etd(self.store(solver.Value(data["etd"]) + offset), now)

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
        model, makespans, events = self.build_model(new_events, offset)

        self.optimize_model(model, events, offset, now, save)

        return new_event
