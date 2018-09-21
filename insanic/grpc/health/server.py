import asyncio

from grpclib.const import Status

from .health_pb2 import HealthCheckResponse
from .health_grpc import HealthBase

from ..utils import _service_name


def _status(checks):
    statuses = {check.__status__() for check in checks}
    if statuses == {None}:
        return HealthCheckResponse.UNKNOWN
    elif statuses == {True}:
        return HealthCheckResponse.SERVING
    else:
        return HealthCheckResponse.NOT_SERVING


def _reset_waits(events, waits):
    new_waits = {}
    for event in events:
        wait = waits.get(event)
        if wait is None or wait.done():
            event.clear()
            wait = asyncio.ensure_future(event.wait())
        new_waits[event] = wait
    return new_waits


class Health(HealthBase):
    """Health-checking service
    Example:
    .. code-block:: python
        from grpclib.health.service import Health
        auth = AuthService()
        billing = BillingService()
        health = Health({
            auth: [redis_status],
            billing: [db_check],
        })
        server = Server([auth, billing, health], loop=loop)
    """

    def __init__(self, checks):
        self._checks = {_service_name(s): list(check_list)
                        for s, check_list in checks.items()}

    async def Check(self, stream):
        """Implements synchronous periodic checks"""
        request = await stream.recv_message()
        checks = self._checks.get(request.service)
        if checks is None:
            await stream.send_trailing_metadata(status=Status.NOT_FOUND)
        elif len(checks) == 0:
            await stream.send_message(HealthCheckResponse(
                status=HealthCheckResponse.SERVING,
            ))
        else:
            for check in checks:
                await check.__check__()
            await stream.send_message(HealthCheckResponse(
                status=_status(checks),
            ))

    async def Watch(self, stream):
        request = await stream.recv_message()
        checks = self._checks.get(request.service)
        if checks is None:
            await stream.send_message(HealthCheckResponse(
                status=HealthCheckResponse.SERVICE_UNKNOWN,
            ))
            while True:
                await asyncio.sleep(3600)
        elif len(checks) == 0:
            await stream.send_message(HealthCheckResponse(
                status=HealthCheckResponse.SERVING,
            ))
            while True:
                await asyncio.sleep(3600)
        else:
            events = []
            for check in checks:
                events.append(await check.__subscribe__())
            waits = _reset_waits(events, {})
            try:
                await stream.send_message(HealthCheckResponse(
                    status=_status(checks),
                ))
                while True:
                    await asyncio.wait(waits.values(),
                                       return_when=asyncio.FIRST_COMPLETED)
                    waits = _reset_waits(events, waits)
                    await stream.send_message(HealthCheckResponse(
                        status=_status(checks),
                    ))
            finally:
                for check, event in zip(checks, events):
                    await check.__unsubscribe__(event)
                for wait in waits.values():
                    if not wait.done():
                        wait.cancel()
