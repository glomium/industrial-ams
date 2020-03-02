#!/usr/bin/env python3
# vim: set fileencoding=utf-8 :

from iams.interface import Agent


class Simple(Agent):

    def _loop(self):
        while not self._stop_event.is_set():
            self._stop_event.wait(10)
            logger.debug("loop")


if __name__ == "__main__":
    run = Simple()
    run()
