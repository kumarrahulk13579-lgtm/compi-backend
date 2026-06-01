import os
import asyncio
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

AUTH_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8001")
CHAT_URL = os.getenv("CHAT_SERVICE_URL", "http://localhost:8002")

ROUTES = {
    "/auth": AUTH_URL,
    "/chat": CHAT_URL,
}

_HOP_BY_HOP = {"transfer-encoding", "connection", "keep-alive", "content-encoding", "content-length"}


async def _fetch_openapi(url: str) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{url}/openapi.json")
            return r.json()
    except Exception:
        return None


def _merge_specs(specs: list[dict]) -> dict:
    base = {
        "openapi": "3.1.0",
        "info": {"title": "Compi API", "version": "1.0.0"},
        "paths": {},
        "components": {"schemas": {}, "securitySchemes": {}},
    }
    for spec in specs:
        if not spec:
            continue
        for path, methods in spec.get("paths", {}).items():
            base["paths"][path] = methods
        components = spec.get("components", {})
        for name, schema in components.get("schemas", {}).items():
            base["components"]["schemas"][name] = schema
        for name, scheme in components.get("securitySchemes", {}).items():
            base["components"]["securitySchemes"][name] = scheme
    return base


app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/openapi.json", include_in_schema=False)
async def openapi():
    specs = await asyncio.gather(_fetch_openapi(AUTH_URL), _fetch_openapi(CHAT_URL))
    return JSONResponse(_merge_specs(list(specs)))


@app.get("/docs", include_in_schema=False)
async def docs():
    html = """<!DOCTYPE html><html><head><title>Compi API</title>
    <meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    </head><body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script>SwaggerUIBundle({url:"/openapi.json",dom_id:"#swagger-ui",presets:[SwaggerUIBundle.presets.apis,SwaggerUIBundle.SwaggerUIStandalonePreset]})</script>
    </body></html>"""
    from fastapi.responses import HTMLResponse
    return HTMLResponse(html)


def _target(path: str) -> str | None:
    for prefix, url in ROUTES.items():
        if path.startswith(prefix):
            return url
    return None


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    full_path = "/" + path
    target = _target(full_path)
    if not target:
        return Response(content='{"detail":"Not found"}', status_code=404, media_type="application/json")

    url = target + full_path
    headers = {k: v for k, v in request.headers.items() if k.lower() not in ("host", "content-length")}
    body = await request.body()

    client = httpx.AsyncClient(timeout=120.0)
    upstream = await client.send(
        client.build_request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        ),
        stream=True,
    )

    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() not in _HOP_BY_HOP}

    async def body_gen():
        try:
            async for chunk in upstream.aiter_bytes():
                yield chunk
        finally:
            await upstream.aclose()
            await client.aclose()

    return StreamingResponse(
        body_gen(),
        status_code=upstream.status_code,
        headers=resp_headers,
        media_type=upstream.headers.get("content-type"),
    )
