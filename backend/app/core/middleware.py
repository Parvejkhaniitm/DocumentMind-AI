from uuid import uuid4

from starlette.responses import JSONResponse

from app.core.config import settings


class UploadTooLarge(Exception):
    pass


class UploadSizeLimitMiddleware:
    """Bound upload request bodies before multipart parsing spools them to disk."""

    def __init__(self, app) -> None:
        self.app = app
        # Allow a small amount of multipart framing and filename metadata.
        self.max_request_bytes = settings.max_upload_bytes + 1024 * 1024

    async def __call__(self, scope, receive, send) -> None:
        if (
            scope["type"] != "http"
            or scope.get("method") != "POST"
            or not scope.get("path", "").startswith(f"{settings.api_v1_prefix}/workspaces/")
            or not scope.get("path", "").endswith("/documents")
        ):
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_length = int(content_length)
            except ValueError:
                await self._reject(scope, receive, send)
                return
            if declared_length > self.max_request_bytes:
                await self._reject(scope, receive, send)
                return

        bytes_received = 0

        async def bounded_receive():
            nonlocal bytes_received
            message = await receive()
            if message["type"] == "http.request":
                bytes_received += len(message.get("body", b""))
                if bytes_received > self.max_request_bytes:
                    raise UploadTooLarge
            return message

        try:
            await self.app(scope, bounded_receive, send)
        except UploadTooLarge:
            await self._reject(scope, receive, send)

    async def _reject(self, scope, receive, send) -> None:
        request_id = uuid4().hex
        response = JSONResponse(
            status_code=413,
            headers={"X-Request-ID": request_id},
            content={
                "error": {
                    "code": "payload_too_large",
                    "message": "Upload request exceeds the configured size limit.",
                    "request_id": request_id,
                }
            },
        )
        await response(scope, receive, send)
