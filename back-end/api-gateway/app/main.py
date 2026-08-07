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
    # Teto aplicado ENQUANTO o corpo chega (ver `settings.max_request_body_bytes`).
    # Duas checagens porque `Content-Length` é uma dica do cliente, não um fato:
    # ele pode mentir, vir ausente, ou o corpo pode chegar em chunked. A
    # primeira evita ler qualquer byte quando o cliente é honesto; a segunda
    # é a que realmente vale.
    detalhe_413 = f"Corpo da requisição excede o limite de {settings.max_request_body_bytes} bytes"
    content_length = request.headers.get("content-length")
    if (
        content_length is not None
        and content_length.isdigit()
        and int(content_length) > settings.max_request_body_bytes
    ):
        raise HTTPException(status_code=413, detail=detalhe_413)

    # `await request.body()` acumulava TODOS os pedaços num único `bytes`
    # antes de retornar, e só então o teto era comparado: um POST anônimo
    # com `Transfer-Encoding: chunked` e 500 MB pagava os 500 MB de memória
    # para receber o 413. Somando pedaço a pedaço, o corpo nunca precisa
    # existir inteiro para ser rejeitado — o `async for` para no primeiro
    # que estoura o teto e o resto do stream nunca é puxado
    # (`tests/test_proxy.py::test_the_cap_aborts_the_stream_instead_of_reading_the_whole_body`
    # conta os pedaços cedidos e prova isso).
    #
    # O que isto NÃO fecha: um pedaço isolado maior que o teto ainda é lido
    # inteiro antes da comparação. O tamanho de cada pedaço é escolhido pelo
    # servidor ASGI ao montar a mensagem `http.request`, não pelo cliente
    # (ASGI HTTP spec), então o custo residual é um buffer do servidor e não
    # o corpo da requisição — mas o valor concreto do Granian não foi medido.
    pedacos: list[bytes] = []
    total_recebido = 0
    async for pedaco in request.stream():
        total_recebido += len(pedaco)
        if total_recebido > settings.max_request_body_bytes:
            raise HTTPException(status_code=413, detail=detalhe_413)
        pedacos.append(pedaco)
    body = b"".join(pedacos)

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
