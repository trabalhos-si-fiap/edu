import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import settings
from app.routing import resolve_destination

app = FastAPI(title="Edu API Gateway")

# Origens liberadas vêm do ambiente (CORS_ORIGINS, lista JSON). Curinga com
# allow_credentials=True é rejeitado pelos browsers e vazaria a API para
# qualquer site — a lista explícita é obrigatória mesmo em dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cabeçalhos que não devem ser repassados adiante (hop-by-hop) ou que o
# httpx recalcula sozinho — repassá-los causa erro de content-length etc.
_HEADERS_PARA_REMOVER_NA_IDA = {"host", "content-length"}
_HEADERS_PARA_REMOVER_NA_VOLTA = {"content-length", "transfer-encoding", "connection"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
)
async def gateway(path: str, request: Request):
    destination = resolve_destination(path)
    if destination is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum serviço mapeado para '/{path}'. Verifique app/routing.py.",
        )

    base_url, final_path = destination
    url = f"{base_url}{final_path}"

    headers = {
        k: v for k, v in request.headers.items() if k.lower() not in _HEADERS_PARA_REMOVER_NA_IDA
    }
    body = await request.body()

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        try:
            response = await client.request(
                request.method,
                url,
                params=request.query_params,
                headers=headers,
                content=body,
            )
        except httpx.ConnectError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Serviço indisponível ao processar '/{path}'",
            ) from exc
        except httpx.TimeoutException as exc:
            raise HTTPException(
                status_code=504,
                detail=f"Tempo limite excedido ao processar '/{path}'",
            ) from exc

    response_headers = {
        k: v for k, v in response.headers.items() if k.lower() not in _HEADERS_PARA_REMOVER_NA_VOLTA
    }

    return Response(
        content=response.content,
        status_code=response.status_code,
        headers=response_headers,
        media_type=response.headers.get("content-type"),
    )
