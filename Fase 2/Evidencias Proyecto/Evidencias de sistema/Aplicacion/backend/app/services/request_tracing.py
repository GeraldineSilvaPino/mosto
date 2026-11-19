"""Operational request correlation without recording payloads or credentials."""
import logging
from time import perf_counter
from uuid import uuid4

logger = logging.getLogger('mosto.requests')


class RequestTracing:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        request_id = str(uuid4())  # Never trust an arbitrary client header in logs.
        scope.setdefault('state', {})['request_id'] = request_id
        started, status = perf_counter(), 500

        async def traced_send(message):
            nonlocal status
            if message['type'] == 'http.response.start':
                status = message['status']
                headers = [(k, v) for k, v in message.get('headers', []) if k.lower() != b'x-request-id']
                message = {**message, 'headers': headers + [(b'x-request-id', request_id.encode('ascii'))]}
            await send(message)

        try:
            await self.app(scope, receive, traced_send)
        finally:
            route = getattr(scope.get('route'), 'path', 'unmatched')
            method = scope.get('method')
            if method not in {'GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD', 'OPTIONS'}:
                method = 'OTHER'
            logger.info('request_id=%s method=%s route=%s status=%s duration_ms=%.2f',
                        request_id, method, route, status, (perf_counter()-started)*1000)
