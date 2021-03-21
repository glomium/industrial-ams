#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging

from ortools.sat.python import cp_model
from operator import attrgetter

from iams.exceptions import CanNotSchedule
from iams.interfaces.scheduler import SchedulerInterface


logger = logging.getLogger(__name__)


class BufferScheduler(SchedulerInterface):
    def __init__(self, ceiling, resolution=1.0,
                 production_lines=1, buffer_input=1, buffer_output=1,
                 *args, **kwargs):
        """
        """
        super().__init__(*args, **kwargs)
        self.ceiling = ceiling
        self.production_lines = production_lines
        self.resolution = resolution

        if isinstance(buffer_input, int):  # pragma: no branch
            self.buffer_input = [buffer_input]
        if isinstance(buffer_output, int):  # pragma: no branch
            self.buffer_output = [buffer_output]

    def __repr__(self):
        return "<%s(buffer_input=%s, buffer_output=%s, ceiling=%s, production_lines=%s, resolution=%s)>" % (
            self.__class__.__qualname__,
            self.buffer_input,
            self.buffer_output,
            self.ceiling,
            self.production_lines,
            self.resolution,
        )

    def schedule(self, event, now=None):
        return self.solve_model(event, now, save=True)

    def can_schedule(self, event, now=None):
        return self.solve_model(event, now, save=False)

    def convert(self, value):
        return round(value * self.resolution)

    def solve_model(self, new_event, now=None, save=False):
        events = self.events + [new_event]
        events = sorted(events, key=attrgetter('eta', 'etd'))

        offset = min(self.convert(node.get_eta(now)) for node in events)
        horizon = max(self.convert(node.get_etd(now) or (self.ceiling + offset)) for node in events) - offset

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
        for i, event in enumerate(events):
            eta = self.convert(event.get_eta(now))
            duration = self.convert(event.get_duration())

            etd = event.get_etd(now)
            if etd is None:
                # time in input queue
                iqs.append(model.NewIntVar(eta, horizon - duration, 'iq_%i' % i))
                # time in output queue
                oqs.append(model.NewIntVar(eta + duration, horizon, 'oq_%i' % i))

                # production
                starts.append(model.NewIntVar(eta, horizon - duration, 'ps_%i' % i))
                ends.append(model.NewIntVar(eta + duration, horizon, 'pe_%i' % i))
                intervals.append(model.NewIntervalVar(starts[i], duration, ends[i], 'pi_%i' % i))

                idemands.append((eta, 1))
                idemands.append((starts[i], -1))
                pdemands.append(1)
                # odemands.append((ends[i], 1))
                # odemands.append((ends[i], -1))

                model.Add(eta <= starts[i])
                model.Add(horizon >= ends[i])
            else:
                # time in input queue
                iqs.append(model.NewIntVar(eta, etd - duration - offset, 'iq_%i' % i))
                # time in output queue
                oqs.append(model.NewIntVar(eta + duration, etd - offset, 'oq_%i' % i))

                # production
                starts.append(model.NewIntVar(eta, etd - duration - offset, 'ps_%i' % i))
                ends.append(model.NewIntVar(eta + duration, etd - offset, 'pe_%i' % i))
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
            self.buffer_input[0],
        )
        model.AddReservoirConstraint(
            [x[0] for x in odemands],
            [x[1] for x in odemands],
            0,
            self.buffer_output[0],
        )
        model.Minimize(sum(starts))

        solver = cp_model.CpSolver()
        try:
            solver.Solve(model)
        except Exception:  # pragma: no cover
            logger.exception("Solver failed")
            raise CanNotSchedule('Solver failed')

        # solver needs to be optimal to result in a match
        if solver.StatusName() not in ["OPTIMAL"]:
            raise CanNotSchedule('Solver returned %s' % solver.StatusName())

        if not save:
            return True

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

                # self.schedule_eta_min = solver.Value(ends[i]) / event.resolution
                # previous.schedule_etd_max = solver.Value(ends[i]) / event.resolution
            # event.set_schedule_start(solver.Value(starts[i]) + offset)
            # event.set_schedule_end(solver.Value(ends[i]) + offset)

        self.events = events
        return True
