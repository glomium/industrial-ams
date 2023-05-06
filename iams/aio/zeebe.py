#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
zeebe mixin for agents
"""

import asyncio
import logging
import os

from iams.aio.interfaces import Coroutine

logger = logging.getLogger(__name__)

NAME = os.environ.get('ZEEBE_NAME', None)
HOST = os.environ.get('ZEEBE_HOST', None)
PORT = int(os.environ.get('ZEEBE_PORT', 26500))

try:
    from pyzeebe import Job
    from pyzeebe import ZeebeClient
    from pyzeebe import ZeebeWorker
    from pyzeebe import create_insecure_channel
    from pyzeebe.errors import InvalidJSONError
    from pyzeebe.errors import MessageAlreadyExistsError
    from pyzeebe.errors import ProcessDefinitionHasNoStartEventError
    from pyzeebe.errors import ProcessDefinitionNotFoundError
    from pyzeebe.errors import ProcessInstanceNotFoundError
    from pyzeebe.errors import UnkownGrpcStatusCodeError
    from pyzeebe.errors import ZeebeBackPressureError
    from pyzeebe.errors import ZeebeGatewayUnavailableError
    from pyzeebe.errors import ZeebeInternalError
except ImportError:  # pragma: no branch
    logger.exception("Could not import opcua library")
    ENABLE = False
else:
    ENABLE = True

if HOST is None:
    logger.info("ZEEBE_HOST is not specified")
    ENABLE = False


class ZeebeCoroutine(Coroutine):
    """
    Zeebe Coroutine
    """

    # pylint: disable=too-many-arguments,dangerous-default-value
    def __init__(self, parent, host: str, port: int = 26500, channel_options: dict = {}, task_type: str = None):
        logger.debug("Initialize Zeebe coroutine")
        self._adapter = None
        self._channel = None
        self._channel_kwargs = {
            'hostname': host,
            'port': port,
            'channel_options': channel_options,
        }
        self._client = None
        self._parent = parent
        self._task_type = task_type or f'agent:{self._parent.iams.agent}'
        self._worker = None

    async def setup(self, executor):
        """
        setup method is awaited one at the start of the coroutines
        """
        logger.debug(
            "Create zeebe worker client with address=%s",
            self._channel_kwargs['hostname'],
        )
        self._channel = create_insecure_channel(**self._channel_kwargs)
        self._client = ZeebeClient(self._channel)
        self._worker = ZeebeWorker(self._channel, name=NAME)

        @self._worker.task(task_type=self._task_type, single_value=True, variable_name="agent_data")
        async def callback(job: Job, agent_data: dict):
            await self._parent.zeebe_update_process(job.process_instance_key, agent_data, job.custom_headers, False)
            await self._parent.zeebe_callback(job, agent_data)

    async def start_process(self, process_id: str, variables: dict, version: int = -1):
        """
        Start a process in zeebe gateway
        """
        variables['task_type'] = self._task_type
        if "agent_data" not in variables:
            variables['agent_data'] = None

        wait = 0
        while True:
            try:
                instance_key = await self._client.run_process(process_id, variables, version)
                break
            except (ProcessDefinitionNotFoundError, InvalidJSONError, ProcessDefinitionHasNoStartEventError):
                logger.exception("Zeebe process error")
                return False
            except (ZeebeBackPressureError, ZeebeGatewayUnavailableError, ZeebeInternalError, UnkownGrpcStatusCodeError) as exc:  # noqa: E501
                wait = min(60, wait + 1)
                logger.info("Waiting Zeebe got an error: '%s' - wait %s seconds to retry", exc, wait)
                await asyncio.sleep(wait)

        logger.debug("New process started with id=%s and agent_data=%s", instance_key, variables['agent_data'])
        await self._parent.zeebe_update_process(instance_key, variables['agent_data'], {}, True)
        return True

    async def cancel_process(self, instance_key: int) -> None:
        """
        Cancel a running process instance

        returns True on success and False on failure
        """
        wait = 0
        while True:
            try:
                await self._client.cancel_process_instance(instance_key)
                return
            except ProcessInstanceNotFoundError:
                return
            except (ZeebeBackPressureError, ZeebeGatewayUnavailableError, ZeebeInternalError, UnkownGrpcStatusCodeError) as exc:  # noqa: E501
                wait = min(60, wait + 1)
                logger.info("Waiting Zeebe got an error: '%s' - wait %s seconds to retry", exc, wait)
                await asyncio.sleep(wait)

    # pylint: disable=too-many-arguments
    async def send_message(self, name: str, variables: dict, message_id: str, ttl: int, correlation_key: str):
        """
        send message to zeebe gateway
        """
        if not correlation_key:
            correlation_key = self._task_type

        wait = 0
        while True:
            try:
                await self._client.publish_message(
                    name=name,
                    correlation_key=correlation_key,
                    variables=variables,
                    time_to_live_in_milliseconds=ttl,
                    message_id=message_id,
                )
                return True
            except MessageAlreadyExistsError:
                return False
            except (ZeebeBackPressureError, ZeebeGatewayUnavailableError, ZeebeInternalError, UnkownGrpcStatusCodeError) as exc:  # noqa: E501
                wait = min(60, wait + 1)
                logger.info("Waiting Zeebe got an error: '%s' - wait %s seconds to retry", exc, wait)
                await asyncio.sleep(wait)

    async def loop(self):
        await self._worker.work()

    async def stop(self):
        """
        stop method is called after the coroutine was canceled
        """
        if self._worker is not None:
            await self._worker.stop()


class ZeebeMixin:
    """
    Mixin to add Zeebe functionality to agents
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if ENABLE:
            self._zeebe = ZeebeCoroutine(self, host=HOST, port=PORT, channel_options=self.zeebe_channel_options())
        else:
            self._zeebe = None

    def _setup(self):
        super()._setup()
        if self._zeebe is not None:
            self.aio_manager.register(self._zeebe)

    def zeebe_channel_options(self) -> dict:  # pylint: disable=no-self-use
        """
        returns the grpc channel options for zeebe gateway
        """
        return {}

    async def zeebe_start_process(self, process_id: str, variables: dict, version: int = -1) -> bool:
        """
        starts a zeebe process, returns true when the process was started or false when it was not started
        """
        if self._zeebe is None:
            return False
        return await self._zeebe.start_process(process_id, variables, version)

    async def zeebe_callback(self, job: Job, data: dict):
        """
        implements a zeebe worker for this agent. gets the job and the state of the BPMN diagram
        returns the new state of the BPMN diagram
        """

    # pylint: disable=no-self-use,unused-argument
    async def zeebe_update_process(self, instance_key, agent_data, headers, created):
        """
        callback that can be used to update the process data. Gets the instance key, agent_data, headers
        and the info if the process was created or updated.
        returns True on success and False on failure
        """
        return True

    async def zeebe_cancel_process(self, instance_key):
        """
        Cancels a process with by instance_key
        returns True on success and False on failure
        """
        if self._zeebe is None:
            return False
        return await self._zeebe.cancel_process(instance_key)

    # pylint: disable=too-many-arguments
    async def zeebe_send_message(self, name: str, variables: dict = None, message_id: str = None, ttl: int = 60000, correlation_key: str = None):  # noqa: E501
        """
        Sends a message to zeebe.
        returns True on success and False on failure
        """
        if self._zeebe is None:
            return False
        return await self._zeebe.send_message(name, variables or {}, message_id, ttl, correlation_key)
