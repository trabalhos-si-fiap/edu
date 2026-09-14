"""Roda a demonstração inteira num Android conectado.

    DEMO_ACCOUNTS_PASSWORD='...' make demo
    cd scripts && python3 -m demo_roteiro --skip-build --pausa 3

Veja docs/demo-roteiro.md.
"""

from __future__ import annotations

import argparse
import atexit
import os
import subprocess
import sys
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

from . import cenas
from .preparo import (
    CONTAS_STAFF,
    PACOTE,
    Backend,
    ContasFaltandoError,
    PreparoFalhouError,
    achar_aparelho,
    checar_backend,
    garantir_contas,
    instalar_app,
    ler_gabarito,
)
from .roteiro_dados import validar_senha
from .tela import Tela, TelaNaoMostrouError

RAIZ = Path(__file__).resolve().parents[2]


def titulo(texto: str) -> None:
    print(f"\n\033[1;35m▸ {texto}\033[0m", flush=True)


def passo(texto: str) -> None:
    print(f"  \033[0;36m·\033[0m {texto}", flush=True)


def aviso(texto: str) -> None:
    print(f"  \033[1;33m! {texto}\033[0m", flush=True)


def porta_do_gateway() -> str:
    env = RAIZ / "back-end" / ".env"
    if env.exists():
        for linha in env.read_text().splitlines():
            if linha.startswith("GATEWAY_PORT_EXTERNAL="):
                return linha.split("=", 1)[1].strip() or "8100"
    return "8100"


def argumentos() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="demo_roteiro",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--skip-build", action="store_true", help="reaproveita o APK instalado")
    parser.add_argument(
        "--pausa", type=float, default=2.0, help="segundos de respiro para a narração (padrão 2)"
    )
    parser.add_argument(
        "--sem-pausa", action="store_true", help="não espera Enter antes do roteiro gravado"
    )
    parser.add_argument(
        "--segundos-de-mapa", type=float, default=20, help="tempo mostrando o mapa (padrão 20)"
    )
    return parser.parse_args()


def preparar_aparelho(tela: Tela, porta: str) -> None:
    tela.adb("reverse", f"tcp:{porta}", f"tcp:{porta}")
    tela.shell(f"am force-stop {PACOTE}", check=False)
    # Dados limpos a cada execução: nenhum atalho ou sessão da gravação
    # anterior aparece na tela de login.
    tela.shell(f"pm clear {PACOTE}", check=False)
    tela.shell(f"pm grant {PACOTE} android.permission.POST_NOTIFICATIONS", check=False)
    tela.shell(f"dumpsys deviceidle whitelist +{PACOTE}", check=False)
    tela.shell(f"cmd appops set {PACOTE} RUN_ANY_IN_BACKGROUND allow", check=False)
    tela.shell("svc power stayon usb", check=False)
    if tela.shell("settings get global zen_mode", check=False).strip() not in ("0", ""):
        aviso("o 'Não perturbar' está ligado: o banner do push não aparece na gravação")
    tela.shell("input keyevent KEYCODE_WAKEUP", check=False)
    tela.shell(f"am start -n {PACOTE}/.MainActivity")


def main() -> int:
    args = argumentos()
    senha = os.environ.get("DEMO_ACCOUNTS_PASSWORD", "")
    try:
        validar_senha(senha)
    except ValueError as exc:
        print(f"DEMO_ACCOUNTS_PASSWORD inválida ou ausente: {exc}", file=sys.stderr)
        return 2

    porta = porta_do_gateway()
    backend = Backend(RAIZ, f"http://localhost:{porta}/api", senha)
    pasta_falhas = Path(tempfile.gettempdir()) / f"edu-demo-{datetime.now():%Y%m%d-%H%M%S}"

    try:
        titulo("Backend")
        checar_backend(backend, aviso)
        resultado = garantir_contas(
            list(CONTAS_STAFF),
            entrar=lambda email: backend.entrar(email) is not None,
            semear=backend.semear_contas,
        )
        for email in resultado.existentes:
            passo(f"{email} já existe — ignorado")
        for email in resultado.criadas:
            passo(f"{email} criado")
        checar_backend(backend, aviso)
        gabarito, acertar = ler_gabarito(backend)
        passo(f"gabarito de Genética: {len(gabarito)} questões")

        titulo("Aparelho")
        serial = achar_aparelho()
        tela = Tela(serial, pasta_falhas, PACOTE)
        # O agente do uiautomator2 segue vivo no aparelho se ninguém o parar;
        # atexit cobre o fim normal, a falha de uma cena e o Ctrl+C.
        atexit.register(tela.encerrar)
        if args.skip_build:
            passo("reaproveitando o APK instalado")
        else:
            passo("compilando e instalando o app de demo (leva ~1 min)")
            instalar_app(RAIZ, serial, porta)
        preparar_aparelho(tela, porta)
        roteiro = cenas.Roteiro(
            tela, backend, gabarito, acertar, pausa_segundos=args.pausa, log=passo
        )
        passo("salvando os atalhos de separador, entregador e admin")
        cenas.salvar_atalhos_de_staff(roteiro, senha)
    except (PreparoFalhouError, ContasFaltandoError) as exc:
        print(f"\n\033[1;31m✗ {exc}\033[0m", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"\n\033[1;31m✗ comando falhou: {' '.join(exc.cmd)}\033[0m", file=sys.stderr)
        return 1

    titulo("Roteiro")
    passo(f"Ana: {roteiro.email_ana}")
    if not args.sem_pausa:
        input("  Comece a gravar a tela e aperte Enter… ")

    passos = {
        "cadastro": lambda: cenas.cadastro(roteiro, senha),
        "onboarding": lambda: cenas.onboarding(roteiro, date.today()),
        "aluna_acompanha": lambda: cenas.aluna_acompanha(roteiro, args.segundos_de_mapa),
    }
    inicio = time.monotonic()
    for nome in cenas.CENAS_GRAVADAS:
        passo(nome.replace("_", " "))
        try:
            passos.get(nome, lambda n=nome: getattr(cenas, n)(roteiro))()
        except (TelaNaoMostrouError, subprocess.CalledProcessError, ValueError) as exc:
            pasta = tela.registrar_falha(nome)
            print(f"\n\033[1;31m✗ cena '{nome}': {exc}\033[0m", file=sys.stderr)
            print(f"  print e árvore da tela em {pasta}", file=sys.stderr)
            return 1

    titulo(f"Pronto em {time.monotonic() - inicio:.0f}s")
    passo(f"pedido #{roteiro.pedido_curto} entregue; pode parar a gravação")
    return 0


if __name__ == "__main__":
    sys.exit(main())
