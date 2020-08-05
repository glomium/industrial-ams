#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

from iams.interfaces import Agent


class Simple(Agent):

    def _loop(self):
        self._stop_event.wait()


if __name__ == "__main__":
    run = Simple()
    run()
