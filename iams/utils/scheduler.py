#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from ortools.sat.python import cp_model
from operator import attrgetter

from iams.exceptions import CanNotSchedule
from iams.interfaces.scheduler import SchedulerInterface


logger = logging.getLogger(__name__)


class BufferScheduler(SchedulerInterface):
    def __init__(self, production_lines=1, buffer_input=1, buffer_output=1, resolution=1.0, *args, **kwargs):
        """
        """
        super().__init__(*args, **kwargs)
        self.buffer_input = buffer_input
        self.buffer_output = buffer_output
        self.production_lines = production_lines
        self.resolution = resolution

    def schedule(self, event, now=None):
        return self.solve_model(event, now, save=True)

    def can_schedule(self, event, now=None):
        return self.solve_model(event, now, save=False)

    def convert(self, value):
        return round(value * self.resolution)

    def solve_model(self, new_event, now=None, save=False):
        events = self.events + [new_event]
        events = sorted(events, key=attrgetter('eta', 'etd'))

        self.offset = min(self.convert(node.get_eta(now)) for node in events)
        self.horizon = max(self.convert(node.get_etd(now)) for node in events) - self.offset

        iqs = []  # input queue time
        oqs = []  # output queue time
        idemands = []
        odemands = []
        pdemands = []
        ends = []
        starts = []
        intervals = []

        model = cp_model.CpModel()
        previous = None
        for i, order in enumerate(events):
            eta = self.convert(order.get_eta(now))
            etd = self.convert(order.get_etd(now))
            duration = self.convert(order.get_duration())

            # time in input queue
            iqs.append(model.NewIntVar(eta, etd - duration - self.offset, 'iq_%i' % i))
            # time in output queue
            oqs.append(model.NewIntVar(eta + duration, etd - self.offset, 'oq_%i' % i))

            # production
            starts.append(model.NewIntVar(eta, etd - duration - self.offset, 'ps_%i' % i))
            ends.append(model.NewIntVar(eta + duration, etd - self.offset, 'pe_%i' % i))
            intervals.append(model.NewIntervalVar(starts[i], duration, ends[i], 'pi_%i' % i))

            idemands.append((eta, 1))
            idemands.append((starts[i], -1))
            pdemands.append(1)
            odemands.append((ends[i], 1))
            odemands.append((etd, -1))

            model.Add(eta <= starts[i])
            model.Add(etd >= ends[i])

            # Precedences inside a job.
            if previous is not None:
                model.Add(starts[i] >= previous)
            previous = starts[i]

        model.AddCumulative(intervals, pdemands, self.production_lines)
        model.AddReservoirConstraint(
            [x[0] for x in idemands],
            [x[1] for x in idemands],
            0,
            self.buffer_input,
        )
        model.AddReservoirConstraint(
            [x[0] for x in odemands],
            [x[1] for x in odemands],
            0,
            self.buffer_output,
        )
        model.Minimize(sum(starts))

        solver = cp_model.CpSolver()
        try:
            solver.Solve(model)
        except Exception:  # pragma: no cover
            logger.exception("Solver failed")
            raise CanNotSchedule

        # solver needs to be optimal to result in a match
        if solver.StatusName() not in ["OPTIMAL"]:
            raise CanNotSchedule

        if not save:
            return False

        previous = None
        for i, event in enumerate(events):
            if i > 0:
                prev_event = events[i - 1]  # noqa

            try:
                next_event = events[i + 1]  # noqa
            except IndexError:
                pass
            else:
                pass  # TODO

                # self.schedule_eta_min = solver.Value(ends[i]) / order.resolution
                # previous.schedule_etd_max = solver.Value(ends[i]) / order.resolution
            # order.set_schedule_start(solver.Value(starts[i]) + self.offset)
            # order.set_schedule_end(solver.Value(ends[i]) + self.offset)

        self.events = events
        return True
