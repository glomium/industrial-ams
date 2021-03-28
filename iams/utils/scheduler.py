#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ortools implementation for scheduler
"""

import logging
from ortools.sat.python import cp_model

from iams.exceptions import CanNotSchedule
from iams.interfaces import SchedulerInterface
from iams.interfaces import SchedulerState


logger = logging.getLogger(__name__)


class BufferScheduler(SchedulerInterface):
    """
    Generic scheduler class for buffers
    """
    # pylint: disable=too-many-locals,too-many-statements,too-many-branches

    def __init__(self, horizon, resolution=1.0,  # pylint: disable=keyword-arg-before-vararg,too-many-arguments
                 production_lines=1, buffer_input=1, buffer_output=1,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.horizon = round(horizon * resolution)
        self.production_lines = production_lines
        self.resolution = resolution

        if isinstance(buffer_input, int):  # pragma: no branch
            self.buffer_input = [buffer_input]
        if isinstance(buffer_output, int):  # pragma: no branch
            self.buffer_output = [buffer_output]

    def __repr__(self):
        return "<%s(horizon=%s, buffer_input=%s, buffer_output=%s, production_lines=%s, resolution=%s)>" % (
            self.__class__.__qualname__,
            self.horizon,
            self.buffer_input,
            self.buffer_output,
            self.production_lines,
            self.resolution,
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

    def convert(self, value):
        """
        returns an integer for every seconds with the defined resolution
        """
        return round(value * self.resolution)

    def get_event_variables(self, new_event, now=None):
        """
        get variables from a collection of events
        """
        events = {}
        offset = 0
        for i, event in enumerate(self.get_events(new_event)):
            data = {}
            event.uid = i

            eta = event.get_eta(now)
            eta_min = event.get_eta_min(now)
            eta_max = event.get_eta_max(now)
            etd = event.get_etd(now)
            etd_max = event.get_etd_max(now)
            etd_min = event.get_etd_min(now)

            if eta is not None:
                eta = self.convert(eta)
            if eta_min is not None:
                eta_min = self.convert(eta_min)
            if eta_max is not None:
                eta_max = self.convert(eta_max)
            if etd is not None:
                etd = self.convert(etd)
            if etd_min is not None:
                etd_min = self.convert(etd_min)
            if etd_max is not None:
                etd_max = self.convert(etd_max)

            eta_bound_low = eta_min or eta or 0
            etd_bound_high = etd_max or etd or self.horizon

            etd_bound_low = etd_min or etd or eta_bound_low + event.duration
            eta_bound_high = eta_max or eta or etd_bound_high - event.duration

            if eta_bound_low < offset:
                offset = eta_bound_low  # TODO unittest needed
            if etd_bound_low < offset:
                offset = etd_bound_low  # TODO unittest needed

            # set eta variables
            if event.state in [SchedulerState.NEW, SchedulerState.SCHEDULED]:
                data[('iq', i)] = (eta_bound_low, eta_bound_high)
                data[('il', i)] = None
                data[('eta', i)] = eta

            elif event.state in [SchedulerState.ARRIVED]:
                data[('iq', i)] = (eta, etd_bound_high - event.duration)
                data[('il', i)] = event.eta_lane
                data[('eta', i)] = eta

                if eta < offset:
                    offset = eta  # TODO unittest needed

            # set production variables
            if event.state in [SchedulerState.NEW, SchedulerState.SCHEDULED, SchedulerState.ARRIVED]:
                if not event.canceled:
                    data[('p', i)] = (None, self.convert(event.duration))
            elif event.state in [SchedulerState.STARTED]:
                data[('p', i)] = (self.convert(event.get_start(now)), event.duration)

            # set etd variables
            if event.state in [SchedulerState.FINISHED]:
                finish = event.get_finish(now)
                data[('oq', i)] = (finish, etd_bound_high)
                data[('etd', i)] = etd
                data[('ol', i)] = event.etd_lane
            elif event.state in [SchedulerState.STARTED]:
                start = event.get_start(now)
                data[('oq', i)] = (start + event.duration, etd_bound_high)
                data[('etd', i)] = etd
                data[('ol', i)] = None
            else:
                data[('oq', i)] = (etd_bound_low, etd_bound_high)
                data[('etd', i)] = etd
                data[('ol', i)] = None

            events[event] = data

        return events, offset

    def solve_model(self, new_event, now=None, save=False):
        """
        solve model with linear optimization
        """
        events, offset = self.get_event_variables(new_event, now=None)
        horizon = self.horizon
        # print(offset)  # noqa
        # print(horizon)  # noqa
        # print(events)  # noqa
        events = list(events.keys())  # TODO: OLD
        model = cp_model.CpModel()

        iqs = []  # input queue time
        oqs = []  # output queue time
        idemands = []
        odemands = []
        pdemands = []
        ends = []
        starts = []
        intervals = []

        previous = None
        for i, event in enumerate(events):
            eta = self.convert(event.get_eta(now))
            duration = self.convert(event.duration)

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
        except Exception as exception:  # pragma: no cover
            logger.exception("Solver failed")
            raise CanNotSchedule('Solver failed') from exception

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

        # self.events = events
        return True
