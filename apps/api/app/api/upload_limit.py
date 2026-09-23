"""Bound multipart requests before Starlette starts parsing uploaded files."""
from starlette.responses import JSONResponse

MAX_IMPORT_BYTES = 42 * 1024 * 1024


class ImportBodyLimit:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope['path'].rstrip('/') != '/api/v1/datasets/import':
            return await self.app(scope, receive, send)
        headers = dict(scope.get('headers', []))
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = -1
        if declared < 0:
            return await JSONResponse({'detail': 'Invalid Content-Length'}, status_code=400)(scope, receive, send)
        async def too_large():
            await JSONResponse({'detail': 'Import request exceeds 42 MiB'}, status_code=413,
                               headers={'Cache-Control': 'no-store'})(scope, receive, send)
        if declared > MAX_IMPORT_BYTES:
            return await too_large()
        body = bytearray()
        while True:
            message = await receive()
            if message['type'] == 'http.disconnect':
                return
            body.extend(message.get('body', b''))
            if len(body) > MAX_IMPORT_BYTES:
                return await too_large()
            if not message.get('more_body', False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {'type': 'http.request', 'body': bytes(body), 'more_body': False}
            return await receive()
        await self.app(scope, replay, send)
