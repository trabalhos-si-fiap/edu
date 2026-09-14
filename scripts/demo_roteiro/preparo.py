"""Preparo idempotente: contas de staff, checagens do backend e o app no
aparelho. Nada aqui sobe ou derruba o stack."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from .roteiro_dados import Questao


class ContasFaltandoError(RuntimeError):
    def __init__(self, faltando: list[str]) -> None:
        super().__init__("contas que continuam sem entrar depois do seed: " + ", ".join(faltando))
        self.faltando = faltando


@dataclass
class ResultadoContas:
    existentes: list[str] = field(default_factory=list)
    criadas: list[str] = field(default_factory=list)


def garantir_contas(
    emails: list[str], entrar: Callable[[str], bool], semear: Callable[[], None]
) -> ResultadoContas:
    """Confere cada conta pelo login; só semeia se faltar alguma.

    O seed de contas de demo já é idempotente, mas conferir antes evita um
    `docker compose exec` a cada execução e deixa claro o que já existia.
    """
    resultado = ResultadoContas(existentes=[e for e in emails if entrar(e)])
    faltando = [e for e in emails if e not in resultado.existentes]
    if not faltando:
        return resultado

    semear()
    continuam = [e for e in faltando if not entrar(e)]
    if continuam:
        raise ContasFaltandoError(continuam)
    resultado.criadas = faltando
    return resultado


# ── I/O: backend ──────────────────────────────────────────────────────


CONTAS_STAFF = {
    "separador@demo.edu": "Fila de Separação",
    "entregador@demo.edu": "Fila de Coleta",
    "admin@demo.edu": "Painel Administrativo",
}


class PreparoFalhouError(RuntimeError):
    """Algo que o roteiro precisa não está pronto; a mensagem diz o que fazer."""


@dataclass
class Backend:
    raiz: Path
    api: str
    senha: str

    @property
    def compose(self) -> list[str]:
        return [
            "docker",
            "compose",
            "-f",
            str(self.raiz / "back-end" / "docker-compose.yml"),
        ]

    def pedir(
        self,
        metodo: str,
        caminho: str,
        token: str | None = None,
        corpo: dict | None = None,
    ):
        dados = json.dumps(corpo).encode() if corpo is not None else None
        requisicao = urllib.request.Request(self.api + caminho, data=dados, method=metodo)
        requisicao.add_header("Content-Type", "application/json")
        if token:
            requisicao.add_header("Authorization", f"Bearer {token}")
        with urllib.request.urlopen(requisicao, timeout=15) as resposta:
            return json.loads(resposta.read() or b"null")

    def entrar(self, email: str) -> str | None:
        """Access token, ou `None` quando a conta não entra."""
        try:
            corpo = self.pedir(
                "POST", "/auth/login", corpo={"email": email, "password": self.senha}
            )
        except urllib.error.HTTPError:
            return None
        tokens = corpo["tokens"]
        return tokens.get("access") or tokens.get("access_token")

    def semear_contas(self) -> None:
        # `-e NOME` sem valor repassa a variável do ambiente: a senha não
        # aparece na linha de comando nem no `ps` do host.
        subprocess.run(
            [
                *self.compose,
                "exec",
                "-T",
                "-e",
                "DEMO_ACCOUNTS_PASSWORD",
                "auth-users-service",
                "uv",
                "run",
                "python",
                "-m",
                "app.seeds.demo_accounts",
            ],
            env={**os.environ, "DEMO_ACCOUNTS_PASSWORD": self.senha},
            check=True,
            capture_output=True,
        )

    def psql(self, banco: str, sql: str) -> list[list[str]]:
        saida = subprocess.run(
            [
                *self.compose,
                "exec",
                "-T",
                "postgres",
                "psql",
                "-U",
                "edu",
                "-d",
                banco,
                "-tA",
                "-F",
                "\x1f",
                "-c",
                sql,
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [linha.split("\x1f") for linha in saida.splitlines() if linha]

    def env_do_commerce(self, nome: str) -> str:
        return subprocess.run(
            [*self.compose, "exec", "-T", "commerce-service", "printenv", nome],
            capture_output=True,
            text=True,
            check=False,
        ).stdout.strip()


def checar_backend(backend: Backend, avisar: Callable[[str], None]) -> None:
    try:
        with urllib.request.urlopen(backend.api.removesuffix("/api") + "/health", timeout=5):
            pass
    except OSError as exc:
        raise PreparoFalhouError(
            f"o gateway não responde em {backend.api} — suba o stack: make stack-up"
        ) from exc

    token = backend.entrar("admin@demo.edu")
    if not token:
        return  # sem admin ainda; `garantir_contas` roda antes de checar o catálogo

    produtos = backend.pedir("GET", "/products?limit=100", token)["items"]
    por_sku = {p.get("sku"): p for p in produtos if p.get("active")}
    estoque = {
        e["produto_id"]: e["quantidade"]
        for e in backend.pedir("GET", "/admin/inventory?limit=200", token)
    }
    for sku in ("LM-MESA-120", "LM-MESA-90"):
        produto = por_sku.get(sku)
        if not produto:
            raise PreparoFalhouError(
                f"o produto {sku} não está no catálogo — rode: make services-seed"
            )
        if estoque.get(produto["id"], 0) <= 0:
            raise PreparoFalhouError(f"o produto {sku} está sem estoque — ajuste no painel web")

    questoes = backend.psql(
        "learning_db",
        "select count(*) from questao q join subtema s on s.id = q.subtema_id "
        "join tema t on t.id = s.tema_id where t.nome = 'Genética Básica'",
    )
    if int(questoes[0][0]) < 12:
        raise PreparoFalhouError(
            "Genética Básica tem menos de 12 questões — aplique o seed "
            "seed_biologia_genetica.sql (ver docs/demo-roteiro.md)"
        )

    if backend.env_do_commerce("CONFIRMAR_PAGAMENTO_AUTOMATICO").lower() != "true":
        avisar(
            "pagamento automático desligado no commerce: o pedido não chega ao separador sozinho"
        )
    if backend.env_do_commerce("AVANCO_AUTOMATICO_SEGUNDOS") in ("", "0"):
        avisar("avanço automático desligado no commerce (sem a rede de segurança de 3 min)")


def ler_gabarito(backend: Backend) -> tuple[list[Questao], set[int]]:
    """Gabarito de Genética Básica e o subtema a acertar (Leis de Mendel)."""
    linhas = backend.psql(
        "learning_db",
        "select q.subtema_id, s.nome, q.gabarito, regexp_replace(q.enunciado, '\\s+', ' ', 'g') "
        "from questao q join subtema s on s.id = q.subtema_id join tema t on t.id = s.tema_id "
        "where t.nome = 'Genética Básica'",
    )
    gabarito = [Questao(int(sub), gab, enun) for sub, _nome, gab, enun in linhas]
    acertar = {int(sub) for sub, nome, _gab, _enun in linhas if nome == "Leis de Mendel"}
    return gabarito, acertar


# ── I/O: aparelho ─────────────────────────────────────────────────────

PACOTE = "br.com.fiap.estuda_app"


def achar_flutter() -> str:
    candidatos = [os.environ.get("FLUTTER"), shutil.which("flutter")]
    candidatos += [
        str(Path.home() / sub / "flutter" / "bin" / "flutter")
        for sub in ("", "Documents", "development")
    ]
    for caminho in candidatos:
        if caminho and Path(caminho).exists():
            return caminho
    raise PreparoFalhouError("flutter não encontrado — exporte FLUTTER=/caminho/para/flutter")


def achar_aparelho() -> str:
    saida = subprocess.run(["adb", "devices"], capture_output=True, text=True, check=True).stdout
    aparelhos = [linha.split()[0] for linha in saida.splitlines()[1:] if linha.endswith("\tdevice")]
    if not aparelhos:
        raise PreparoFalhouError("nenhum Android autorizado no adb (confira: adb devices)")
    return aparelhos[0]


def instalar_app(raiz: Path, serial: str, porta: str) -> None:
    front = raiz / "front-end-flutter"
    subprocess.run(
        [
            achar_flutter(),
            "build",
            "apk",
            "--debug",
            f"--dart-define=API_BASE_URL=http://localhost:{porta}/api",
            "--dart-define=DEMO_MULTI_SESSAO=true",
        ],
        cwd=front,
        check=True,
        capture_output=True,
    )
    apk = front / "build" / "app" / "outputs" / "flutter-apk" / "app-debug.apk"
    subprocess.run(
        ["adb", "-s", serial, "install", "-r", str(apk)],
        check=True,
        capture_output=True,
    )
