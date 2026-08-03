import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from app.config import settings
from app.routing import resolver_destino

app = FastAPI(title="Edu API Gateway")

# CORS liberado para o MVP (Flutter Web / apps de terceiros de demo).
# Em produção, restrinjam allow_origins aos domínios reais do app.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    destino = resolver_destino(path)
    if destino is None:
        raise HTTPException(
            status_code=404,
            detail=f"Nenhum serviço mapeado para '/{path}'. Verifique app/routing.py.",
        )

    base_url, path_final = destino
    url = f"{base_url}{path_final}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in _HEADERS_PARA_REMOVER_NA_IDA
    }
    body = await request.body()

    async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
        try:
            resposta = await client.request(
                request.method,
                url,
                params=request.query_params,
                headers=headers,
                content=body,
            )
        except httpx.ConnectError:
            raise HTTPException(
                status_code=503,
                detail=f"Serviço indisponível ao processar '/{path}'",
            )
        except httpx.TimeoutException:
            raise HTTPException(
                status_code=504,
                detail=f"Tempo limite excedido ao processar '/{path}'",
            )

    headers_resposta = {
        k: v
        for k, v in resposta.headers.items()
        if k.lower() not in _HEADERS_PARA_REMOVER_NA_VOLTA
    }

    return Response(
        content=resposta.content,
        status_code=resposta.status_code,
        headers=headers_resposta,
        media_type=resposta.headers.get("content-type"),
    )
