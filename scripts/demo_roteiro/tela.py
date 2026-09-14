"""Controle da tela do Android por `adb` e `uiautomator`.

O Flutter publica o texto visível na árvore de acessibilidade, então dá para
achar um botão pelo que ele diz em vez de por coordenada medida num aparelho
só. `ler_elementos` e `escapar_texto` são puros e testados; `Tela` é a casca
de I/O que o roteiro usa.
"""

from __future__ import annotations

import html
import re
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Elemento:
    texto: str
    classe: str
    clicavel: bool
    rolavel: bool
    limites: tuple[int, int, int, int]

    @property
    def centro(self) -> tuple[int, int]:
        x1, y1, x2, y2 = self.limites
        return (x1 + x2) // 2, (y1 + y2) // 2


def _atributo(no: str, nome: str) -> str:
    achado = re.search(rf' {nome}="([^"]*)"', no)
    return html.unescape(achado.group(1)) if achado else ""


def ler_elementos(xml: str) -> list[Elemento]:
    """Elementos de um `uiautomator dump`, na ordem da árvore."""
    elementos = []
    for achado in re.finditer(r"<node [^>]*>", xml):
        no = achado.group(0)
        numeros = [int(n) for n in re.findall(r"\d+", _atributo(no, "bounds"))]
        if len(numeros) != 4:
            continue
        elementos.append(
            Elemento(
                texto=_atributo(no, "text") or _atributo(no, "content-desc"),
                classe=_atributo(no, "class").split(".")[-1],
                clicavel=_atributo(no, "clickable") == "true",
                rolavel=_atributo(no, "scrollable") == "true",
                limites=(numeros[0], numeros[1], numeros[2], numeros[3]),
            )
        )
    return elementos


def escapar_texto(texto: str) -> str:
    """Argumento de `input text` já pronto para o shell do aparelho.

    `input text` troca `%s` por espaço, e o comando passa por um shell do
    lado do Android — por isso as aspas. Acento não é digitável por esse
    caminho: falha alto em vez de digitar outra coisa.
    """
    if not texto.isascii():
        raise ValueError(f"texto fora de ASCII não é digitável por adb: {texto!r}")
    return shlex.quote(texto.replace(" ", "%s"))


class TelaNaoMostrou(RuntimeError):
    """O elemento esperado não apareceu no prazo."""


class Tela:
    def __init__(self, serial: str, pasta_falhas: Path) -> None:
        self.serial = serial
        self.pasta_falhas = pasta_falhas

    # ── adb ───────────────────────────────────────────────────────────

    def adb(self, *args: str, check: bool = True) -> str:
        resultado = subprocess.run(
            ["adb", "-s", self.serial, *args],
            capture_output=True,
            text=True,
            check=check,
        )
        return resultado.stdout

    def shell(self, comando: str, check: bool = True) -> str:
        return self.adb("shell", comando, check=check)

    # ── leitura ───────────────────────────────────────────────────────

    def elementos(self) -> list[Elemento]:
        for _ in range(3):
            self.shell("uiautomator dump /sdcard/edu-demo-ui.xml", check=False)
            xml = self.shell("cat /sdcard/edu-demo-ui.xml", check=False)
            if "<node" in xml:
                return ler_elementos(xml)
            time.sleep(0.5)
        return []

    def achar(
        self, texto: str, exato: bool = False, indice: int = 0
    ) -> Elemento | None:
        def bate(e: Elemento) -> bool:
            return e.texto == texto if exato else texto.lower() in e.texto.lower()

        achados = [e for e in self.elementos() if bate(e)]
        return achados[indice] if len(achados) > indice else None

    def esperar(
        self, texto: str, prazo: float = 20, exato: bool = False, indice: int = 0
    ) -> Elemento:
        limite = time.monotonic() + prazo
        while True:
            elemento = self.achar(texto, exato=exato, indice=indice)
            if elemento:
                return elemento
            if time.monotonic() > limite:
                raise TelaNaoMostrou(f"não apareceu na tela em {prazo:.0f}s: {texto!r}")
            time.sleep(0.5)

    def campos(self) -> list[Elemento]:
        return [e for e in self.elementos() if e.classe == "EditText"]

    # ── ação ──────────────────────────────────────────────────────────

    def tocar_xy(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}")

    def tocar(
        self, texto: str, prazo: float = 20, exato: bool = False, indice: int = 0
    ) -> None:
        x, y = self.esperar(texto, prazo=prazo, exato=exato, indice=indice).centro
        self.tocar_xy(x, y)

    def digitar(self, texto: str) -> None:
        self.shell(f"input text {escapar_texto(texto)}")

    def preencher(self, campo: Elemento, texto: str) -> None:
        """Toca o campo, apaga o que houver e digita."""
        self.tocar_xy(*campo.centro)
        time.sleep(0.4)
        self.shell("input keyevent KEYCODE_MOVE_END")
        self.shell("input keyevent " + " ".join(["67"] * 60))
        self.digitar(texto)
        time.sleep(0.3)

    def fechar_teclado(self) -> None:
        if "mInputShown=true" in self.shell("dumpsys input_method", check=False):
            self.voltar()
            time.sleep(0.6)

    def voltar(self) -> None:
        self.shell("input keyevent KEYCODE_BACK")

    def rolar(
        self, distancia: int = 900, de_y: int = 1800, duracao_ms: int = 450
    ) -> None:
        self.shell(f"input swipe 540 {de_y} 540 {de_y - distancia} {duracao_ms}")

    def rolar_ate(
        self, texto: str, tentativas: int = 8, exato: bool = False
    ) -> Elemento:
        for _ in range(tentativas):
            elemento = self.achar(texto, exato=exato)
            if elemento:
                return elemento
            self.rolar()
            time.sleep(0.8)
        raise TelaNaoMostrou(f"rolei {tentativas} vezes e não achei: {texto!r}")

    # ── diagnóstico ───────────────────────────────────────────────────

    def registrar_falha(self, nome: str) -> Path:
        """Salva print e árvore da tela atual; devolve a pasta."""
        self.pasta_falhas.mkdir(parents=True, exist_ok=True)
        png = subprocess.run(
            ["adb", "-s", self.serial, "exec-out", "screencap", "-p"],
            capture_output=True,
            check=False,
        ).stdout
        (self.pasta_falhas / f"{nome}.png").write_bytes(png)
        (self.pasta_falhas / f"{nome}.txt").write_text(
            "\n".join(f"{e.classe} {e.texto!r} {e.limites}" for e in self.elementos())
        )
        return self.pasta_falhas
