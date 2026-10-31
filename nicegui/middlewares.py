from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import core
from .version import __version__

# pure ASGI middlewares, because BaseHTTPMiddleware leaves reference cycles behind with every request


class RedirectWithPrefixMiddleware:
    """Prepend the ``X-Forwarded-Prefix`` header to redirect locations within the app."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        prefix = Headers(scope=scope).get('X-Forwarded-Prefix', '')

        async def send_with_prefix(message: Message) -> None:
            if message['type'] == 'http.response.start':
                headers = MutableHeaders(scope=message)
                if headers.get('Location', '').startswith('/'):
                    headers['Location'] = prefix + headers['Location']
            await send(message)

        await self.app(scope, receive, send_with_prefix)


class SetCacheControlMiddleware:
    """Set the configured ``Cache-Control`` directives for NiceGUI's versioned resources, except dynamic ones."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http' \
                or not scope['path'].startswith(f'/_nicegui/{__version__}/') \
                or scope['path'].startswith(f'/_nicegui/{__version__}/dynamic_resources/'):
            await self.app(scope, receive, send)
            return

        async def send_with_cache_control(message: Message) -> None:
            if message['type'] == 'http.response.start':
                MutableHeaders(scope=message)['Cache-Control'] = core.app.config.cache_control_directives
            await send(message)

        await self.app(scope, receive, send_with_cache_control)
