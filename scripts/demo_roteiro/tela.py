"""Controle da tela do Android por `adb` e `uiautomator2`.

O Flutter publica o texto visível na árvore de acessibilidade, então dá para
achar um botão pelo que ele diz em vez de por coordenada medida num aparelho
só. `ler_elementos`, `achar_em` e `escapar_texto` são puros e testados; `Tela`
é a casca de I/O que o roteiro usa.

A árvore vem do agente do `uiautomator2`, que fica rodando no aparelho e
responde em ~0,2s. O `uiautomator dump` do Android sobe uma JVM e espera a
tela ficar ociosa a cada leitura: ~2,2s, e o roteiro lê a tela centenas de
vezes.
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


def ler_elementos(xml: str, pacote: str | None = None) -> list[Elemento]:
    """Elementos visíveis de uma árvore do uiautomator, na ordem da árvore.

    Os limites de cada elemento são cortados pela área visível dos
    ancestrais, e o que fica fora dela some: o uiautomator2 devolve o
    retângulo inteiro de um botão meio escondido embaixo da área rolável, e o
    centro dele cai fora do app. Com `pacote`, só os do app: a leitura inclui
    a barra do sistema e o teclado, que também têm botões como "Voltar".
    """
    elementos = []
    areas: list[tuple[int, int, int, int]] = []  # dos ancestrais ainda abertos
    for achado in re.finditer(r"<node [^>]*>|</node>", xml):
        no = achado.group(0)
        if no == "</node>":
            if areas:
                areas.pop()
            continue
        numeros = [int(n) for n in re.findall(r"\d+", _atributo(no, "bounds"))]
        valido = len(numeros) == 4
        x1, y1, x2, y2 = numeros if valido else (0, 0, 10**6, 10**6)
        if areas:
            px1, py1, px2, py2 = areas[-1]
            x1, y1, x2, y2 = max(x1, px1), max(y1, py1), min(x2, px2), min(y2, py2)
        if not no.endswith("/>"):
            areas.append((x1, y1, x2, y2))
        if not valido or x2 <= x1 or y2 <= y1:
            continue
        if pacote is not None and _atributo(no, "package") != pacote:
            continue
        elementos.append(
            Elemento(
                texto=_atributo(no, "text") or _atributo(no, "content-desc"),
                classe=_atributo(no, "class").split(".")[-1],
                clicavel=_atributo(no, "clickable") == "true",
                rolavel=_atributo(no, "scrollable") == "true",
                limites=(x1, y1, x2, y2),
            )
        )
    return elementos


def achar_em(
    elementos: list[Elemento],
    texto: str,
    exato: bool = False,
    indice: int = 0,
    clicavel: bool | None = None,
) -> Elemento | None:
    """O `indice`-ésimo elemento com o texto; sem `exato`, basta um trecho."""

    def bate(e: Elemento) -> bool:
        if clicavel is not None and e.clicavel != clicavel:
            return False
        return e.texto == texto if exato else texto.lower() in e.texto.lower()

    achados = [e for e in elementos if bate(e)]
    return achados[indice] if len(achados) > indice else None


def escapar_texto(texto: str) -> str:
    """Argumento de `input text` já pronto para o shell do aparelho.

    `input text` troca `%s` por espaço, e o comando passa por um shell do
    lado do Android — por isso as aspas. Acento não é digitável por esse
    caminho: falha alto em vez de digitar outra coisa.
    """
    if not texto.isascii():
        raise ValueError(f"texto fora de ASCII não é digitável por adb: {texto!r}")
    return shlex.quote(texto.replace(" ", "%s"))


class TelaNaoMostrouError(RuntimeError):
    """O elemento esperado não apareceu no prazo."""


class Tela:
    def __init__(
        self, serial: str, pasta_falhas: Path, pacote: str = "br.com.fiap.estuda_app"
    ) -> None:
        self.serial = serial
        self.pasta_falhas = pasta_falhas
        self.pacote = pacote
        self._agente = None

    def encerrar(self) -> None:
        """Para o agente do uiautomator2 no aparelho, se ele foi ligado."""
        if self._agente is not None:
            self._agente.stop_uiautomator()
            self._agente = None

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

    def garantir_app_em_foco(self) -> None:
        """Reabre o app se um voltar a mais o mandou para o launcher."""
        atividades = self.shell("dumpsys activity activities", check=False)
        topo = next((linha for linha in atividades.splitlines() if "ResumedActivity" in linha), "")
        if self.pacote not in topo:
            self.shell(f"am start -n {self.pacote}/.MainActivity", check=False)
            time.sleep(3)

    def _ler_arvore(self) -> list[Elemento]:
        if self._agente is None:
            try:
                import uiautomator2
            except ImportError as exc:
                raise RuntimeError(
                    "falta o uiautomator2: rode com `make demo`, que o instala pelo uv"
                ) from exc
            self._agente = uiautomator2.connect(self.serial)
        return ler_elementos(self._agente.dump_hierarchy(), self.pacote)

    def elementos(self) -> list[Elemento]:
        """A tela depois de parar de mexer.

        O agente não espera a tela ficar ociosa: uma leitura no meio de uma
        transição ou de uma rolagem acharia o botão fora do lugar. Duas
        leituras seguidas iguais fazem esse papel por uma fração do tempo.
        """
        anterior = self._ler_arvore()
        for _ in range(8):
            time.sleep(0.15)
            atual = self._ler_arvore()
            if atual == anterior:
                return atual
            anterior = atual
        return anterior

    def achar(
        self,
        texto: str,
        exato: bool = False,
        indice: int = 0,
        clicavel: bool | None = None,
    ) -> Elemento | None:
        return achar_em(self.elementos(), texto, exato=exato, indice=indice, clicavel=clicavel)

    def esperar(
        self,
        texto: str,
        prazo: float = 20,
        exato: bool = False,
        indice: int = 0,
        clicavel: bool | None = None,
    ) -> Elemento:
        limite = time.monotonic() + prazo
        while True:
            elemento = self.achar(texto, exato=exato, indice=indice, clicavel=clicavel)
            if elemento:
                return elemento
            if time.monotonic() > limite:
                raise TelaNaoMostrouError(f"não apareceu na tela em {prazo:.0f}s: {texto!r}")
            time.sleep(0.2)

    def esperar_sumir(self, texto: str, prazo: float = 20, exato: bool = False) -> None:
        """Espera a tela que tem `texto` fechar.

        Depois de salvar um formulário, a tela de baixo já aparece na árvore
        enquanto a de cima sai e antes de ela recarregar; esperar só pelo
        texto da tela de baixo passaria cedo demais.
        """
        limite = time.monotonic() + prazo
        while self.achar(texto, exato=exato):
            if time.monotonic() > limite:
                raise TelaNaoMostrouError(f"continuou na tela depois de {prazo:.0f}s: {texto!r}")
            time.sleep(0.2)

    def campos(self) -> list[Elemento]:
        return [e for e in self.elementos() if e.classe == "EditText"]

    def campo_abaixo(self, rotulo: str) -> Elemento:
        """O campo de texto logo abaixo de um rótulo, na mesma coluna."""
        self.fechar_teclado()
        for _ in range(6):
            elementos = self.elementos()
            marcador = next((e for e in elementos if e.texto == rotulo and not e.clicavel), None)
            if marcador:
                x1, _, _, y2 = marcador.limites
                abaixo = [
                    e
                    for e in elementos
                    if e.classe == "EditText"
                    and e.limites[1] >= y2 - 10
                    and e.limites[0] <= x1 + 10 <= e.limites[2]
                ]
                if abaixo:
                    return min(abaixo, key=lambda e: e.limites[1])
            # Rótulo fora da tela, ou o campo ainda abaixo da borda.
            self.rolar(500)
            time.sleep(0.2)
        raise TelaNaoMostrouError(f"nenhum campo abaixo do rótulo {rotulo!r}")

    # ── ação ──────────────────────────────────────────────────────────

    def tocar_xy(self, x: int, y: int) -> None:
        self.shell(f"input tap {x} {y}")

    def tocar(
        self,
        texto: str,
        prazo: float = 20,
        exato: bool = False,
        indice: int = 0,
        clicavel: bool | None = None,
    ) -> None:
        elemento = self.esperar(texto, prazo=prazo, exato=exato, indice=indice, clicavel=clicavel)
        self.tocar_xy(*elemento.centro)

    def tocar_icone(self, canto: str) -> None:
        """Toca o botão sem texto num canto do topo ("esquerda" ou "direita").

        Ícone de perfil, carrinho e sino não publicam texto; o canto é o que
        os distingue, e vale para qualquer largura de tela.
        """
        elementos = self.elementos()
        meio = max((e.limites[2] for e in elementos), default=0) // 2
        botoes = [
            e
            for e in elementos
            if e.clicavel
            and not e.texto
            and e.classe == "Button"
            and e.limites[1] < 300
            and (e.centro[0] < meio if canto == "esquerda" else e.centro[0] > meio)
        ]
        if not botoes:
            raise TelaNaoMostrouError(f"nenhum ícone sem texto no canto {canto} do topo")
        if canto == "esquerda":
            alvo = min(botoes, key=lambda e: e.limites[0])
        else:
            alvo = max(botoes, key=lambda e: e.limites[2])
        self.tocar_xy(*alvo.centro)

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

    def preencher_campo(self, rotulo: str, texto: str) -> None:
        self.preencher(self.campo_abaixo(rotulo), texto)
        self.fechar_teclado()

    def fechar_teclado(self) -> None:
        if "mInputShown=true" in self.shell("dumpsys input_method", check=False):
            self.voltar()
            time.sleep(0.3)

    def voltar(self) -> None:
        self.shell("input keyevent KEYCODE_BACK")

    def rolar(self, distancia: int = 900, de_y: int = 1800, duracao_ms: int = 450) -> None:
        self.shell(f"input swipe 540 {de_y} 540 {de_y - distancia} {duracao_ms}")

    def rolar_para_cima(self) -> None:
        self.shell("input swipe 540 700 540 1900 300")

    def rolar_ate(self, texto: str, tentativas: int = 8, exato: bool = False) -> Elemento:
        for _ in range(tentativas):
            elemento = self.achar(texto, exato=exato)
            if elemento:
                return elemento
            self.rolar()
            time.sleep(0.2)
        raise TelaNaoMostrouError(f"rolei {tentativas} vezes e não achei: {texto!r}")

    # ── notificações ──────────────────────────────────────────────────

    def notificacao_chegou(self, trecho: str, prazo: float = 40) -> bool:
        """Espera uma notificação com `trecho` no título ou no texto."""
        limite = time.monotonic() + prazo
        while time.monotonic() < limite:
            saida = self.shell("dumpsys notification --noredact", check=False)
            if trecho.lower() in saida.lower():
                return True
            time.sleep(1)
        return False

    def mostrar_gaveta(self, segundos: float) -> None:
        self.shell("cmd statusbar expand-notifications", check=False)
        time.sleep(segundos)
        self.shell("cmd statusbar collapse", check=False)
        time.sleep(0.8)

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
