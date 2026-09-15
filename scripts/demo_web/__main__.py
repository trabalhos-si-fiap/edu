"""Roda o roteiro do painel web num Chromium visível, para gravar a tela.

    DEMO_ACCOUNTS_PASSWORD='...' make demo-web
    make demo-web ARGS="--tamanho 1600x900 --pausa 2"

Veja docs/demo-roteiro.md.
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import sync_playwright

from demo_roteiro.preparo import (
    Backend,
    ContasFaltandoError,
    PreparoFalhouError,
    garantir_contas,
    porta_do_gateway,
)
from demo_roteiro.roteiro_dados import validar_senha

from . import cenas
from .dados import ler_tamanho, pedido_em_destaque
from .navegador import CURSOR_JS, Navegador

RAIZ = Path(__file__).resolve().parents[2]


def titulo(texto: str) -> None:
    print(f"\n\033[1;35m▸ {texto}\033[0m", flush=True)


def passo(texto: str) -> None:
    print(f"  \033[0;36m·\033[0m {texto}", flush=True)


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="demo_web", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--url", default="http://localhost:4200", help="painel já rodando (padrão :4200)"
    )
    parser.add_argument(
        "--tamanho",
        type=ler_tamanho,
        default=(1920, 1080),
        help="janela LARGURAxALTURA (padrão 1920x1080)",
    )
    parser.add_argument(
        "--pausa", type=float, default=1.5, help="segundos de respiro para a narração (padrão 1.5)"
    )
    parser.add_argument(
        "--sem-pausa", action="store_true", help="não espera Enter antes do roteiro gravado"
    )
    return parser.parse_args()


def checar_painel(url: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=5):
            pass
    except OSError as exc:
        raise PreparoFalhouError(
            f"o painel não responde em {url} — suba com: cd web-admin && npm start"
        ) from exc


def preparar(backend: Backend, url: str) -> str | None:
    """Confere gateway, painel e conta do admin; devolve o pedido a destacar."""
    try:
        with urllib.request.urlopen(backend.api.removesuffix("/api") + "/health", timeout=5):
            pass
    except OSError as exc:
        raise PreparoFalhouError(
            f"o gateway não responde em {backend.api} — suba o stack: make stack-up"
        ) from exc
    checar_painel(url)
    resultado = garantir_contas(
        ["admin@demo.edu"],
        entrar=lambda email: backend.entrar(email) is not None,
        semear=backend.semear_contas,
    )
    passo("admin@demo.edu " + ("já existe — ignorado" if resultado.existentes else "criado"))
    token = backend.entrar("admin@demo.edu")
    return pedido_em_destaque(backend.pedir("GET", "/admin/orders?limit=50&offset=0", token))


def main() -> int:
    args = argumentos()
    senha = os.environ.get("DEMO_ACCOUNTS_PASSWORD", "")
    try:
        validar_senha(senha)
    except ValueError as exc:
        print(f"DEMO_ACCOUNTS_PASSWORD inválida ou ausente: {exc}", file=sys.stderr)
        return 2

    url = args.url.rstrip("/")
    backend = Backend(RAIZ, f"http://localhost:{porta_do_gateway(RAIZ)}/api", senha)
    pasta_falhas = Path(tempfile.gettempdir()) / f"edu-demo-web-{datetime.now():%Y%m%d-%H%M%S}"

    titulo("Backend e painel")
    try:
        pedido_curto = preparar(backend, url)
    except (PreparoFalhouError, ContasFaltandoError) as exc:
        print(f"\n\033[1;31m✗ {exc}\033[0m", file=sys.stderr)
        return 1
    passo(f"pedido em destaque: #{pedido_curto}" if pedido_curto else "nenhum pedido ainda")

    titulo("Navegador")
    largura, altura = args.tamanho
    with sync_playwright() as pw, tempfile.TemporaryDirectory(prefix="edu-demo-web-") as perfil:
        try:
            contexto = pw.chromium.launch_persistent_context(
                perfil,
                headless=False,
                no_viewport=True,
                # `--app` tira abas e barra de endereço da gravação; sem
                # `--enable-automation` some o aviso de navegador controlado.
                args=[
                    f"--app={url}/login",
                    f"--window-size={largura},{altura}",
                    "--window-position=0,0",
                ],
                ignore_default_args=["--enable-automation"],
            )
        except PlaywrightError as exc:
            print(
                f"\n\033[1;31m✗ o Chromium não abriu: {str(exc).splitlines()[0]}\033[0m\n"
                "  sem o navegador baixado, rode: "
                "uv run --no-project --with playwright==1.61.0 playwright install chromium",
                file=sys.stderr,
            )
            return 1
        contexto.add_init_script(CURSOR_JS)
        pagina = contexto.pages[0] if contexto.pages else contexto.new_page()
        pagina.set_default_timeout(20_000)
        # A janela `--app` carregou antes do script do cursor existir.
        pagina.goto(f"{url}/login")
        roteiro = cenas.Roteiro(
            Navegador(pagina, args.pausa, pasta_falhas), pedido_curto, log=passo
        )

        titulo("Roteiro")
        if not args.sem_pausa:
            input("  Comece a gravar a tela e aperte Enter… ")

        passos = {"login": lambda: cenas.login(roteiro, senha)}
        inicio = time.monotonic()
        for nome in ["login", *cenas.CENAS]:
            passo(nome.replace("_", " "))
            comeco = time.monotonic()
            try:
                passos.get(nome, lambda n=nome: getattr(cenas, n)(roteiro))()
            except (PlaywrightError, ValueError) as exc:
                pasta = roteiro.nav.registrar_falha(nome)
                print(
                    f"\n\033[1;31m✗ cena '{nome}': {str(exc).splitlines()[0]}\033[0m",
                    file=sys.stderr,
                )
                print(f"  print e HTML da página em {pasta}", file=sys.stderr)
                contexto.close()
                return 1
            passo(f"  {time.monotonic() - comeco:.0f}s")

        titulo(f"Pronto em {time.monotonic() - inicio:.0f}s")
        passo("pode parar a gravação")
        time.sleep(3)
        contexto.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
