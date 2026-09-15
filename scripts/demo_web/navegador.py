"""Controle do Chromium pelo Playwright, pensado para ser gravado.

O Playwright não mexe no mouse do sistema: sem ajuda, a gravação mostraria
botões sendo apertados sozinhos. A página ganha uma seta desenhada que segue
os eventos de mouse do Playwright, e cada clique desliza até o alvo antes de
apertar. Texto é digitado tecla a tecla, e o que importa na narração ganha
um contorno por alguns segundos.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import Locator, Page

CURSOR_JS = r"""
(() => {
  if (window.__eduDemoCursor) return;
  window.__eduDemoCursor = true;
  const iniciar = () => {
    const seta = document.createElement('div');
    seta.innerHTML =
      '<svg width="30" height="30" viewBox="0 0 24 24">' +
      '<path d="M4 2l6.5 18 2.6-7.3L20.5 10z" fill="#111" stroke="#fff"' +
      ' stroke-width="1.6" stroke-linejoin="round"/></svg>';
    Object.assign(seta.style, {
      position: 'fixed', left: '-40px', top: '-40px', zIndex: 2147483647,
      pointerEvents: 'none', transform: 'translate(-4px, -2px)',
    });
    document.documentElement.appendChild(seta);
    document.addEventListener('mousemove', (e) => {
      seta.style.left = e.clientX + 'px';
      seta.style.top = e.clientY + 'px';
    }, true);
    document.addEventListener('mousedown', (e) => {
      const onda = document.createElement('div');
      Object.assign(onda.style, {
        position: 'fixed', left: e.clientX - 18 + 'px', top: e.clientY - 18 + 'px',
        width: '36px', height: '36px', borderRadius: '50%', zIndex: 2147483646,
        pointerEvents: 'none', background: 'rgba(98, 0, 238, 0.35)',
        transition: 'transform 0.45s ease-out, opacity 0.45s ease-out',
      });
      document.documentElement.appendChild(onda);
      requestAnimationFrame(() => {
        onda.style.transform = 'scale(2.2)';
        onda.style.opacity = '0';
      });
      setTimeout(() => onda.remove(), 500);
    }, true);
  };
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', iniciar);
  } else {
    iniciar();
  }
})();
"""

DESTACAR_JS = """
(el, ms) => {
  const caixa = el.getBoundingClientRect();
  const aro = document.createElement('div');
  Object.assign(aro.style, {
    position: 'fixed', left: caixa.left - 6 + 'px', top: caixa.top - 6 + 'px',
    width: caixa.width + 12 + 'px', height: caixa.height + 12 + 'px',
    border: '3px solid #6200ee', borderRadius: '12px', zIndex: 2147483645,
    pointerEvents: 'none', boxShadow: '0 0 0 9999px rgba(20, 16, 40, 0.12)',
    opacity: '0', transition: 'opacity 0.25s ease',
  });
  document.documentElement.appendChild(aro);
  requestAnimationFrame(() => { aro.style.opacity = '1'; });
  setTimeout(() => { aro.style.opacity = '0'; }, Math.max(ms - 250, 0));
  setTimeout(() => aro.remove(), ms);
}
"""


@dataclass
class Navegador:
    pagina: Page
    pausa_segundos: float
    pasta_falhas: Path
    _x: float = 0
    _y: float = 0

    def pausa(self, fator: float = 1.0) -> None:
        time.sleep(self.pausa_segundos * fator)

    # ── mouse e teclado ───────────────────────────────────────────────

    def mover_ate(self, alvo: Locator) -> None:
        alvo.wait_for(state="visible")
        alvo.scroll_into_view_if_needed()
        caixa = alvo.bounding_box()
        if caixa is None:
            raise ValueError(f"alvo sem posição na tela: {alvo}")
        x = caixa["x"] + caixa["width"] / 2
        y = caixa["y"] + caixa["height"] / 2
        # Passos proporcionais à distância: a seta anda na mesma velocidade
        # para perto e para longe, em vez de teleportar.
        passos = max(8, int(math.dist((self._x, self._y), (x, y)) / 22))
        self.pagina.mouse.move(x, y, steps=passos)
        self._x, self._y = x, y

    def clicar(self, alvo: Locator) -> None:
        self.mover_ate(alvo)
        time.sleep(0.2)
        self.pagina.mouse.click(self._x, self._y)

    def digitar(self, alvo: Locator, texto: str, atraso_ms: int = 55) -> None:
        self.clicar(alvo)
        alvo.press_sequentially(texto, delay=atraso_ms)

    def substituir(self, alvo: Locator, texto: str, atraso_ms: int = 90) -> None:
        self.clicar(alvo)
        alvo.press("Control+A")
        alvo.press("Backspace")
        alvo.press_sequentially(texto, delay=atraso_ms)

    def escolher(
        self, select: Locator, rotulo: str | None = None, valor: str | None = None
    ) -> None:
        """Escolhe numa `<select>` nativa. A lista do sistema não abre na
        gravação (o Playwright troca o valor direto), então a seta vai até o
        campo e a troca acontece com ela ali."""
        self.mover_ate(select)
        time.sleep(0.4)
        if rotulo is not None:
            select.select_option(label=rotulo)
        else:
            select.select_option(value=valor)

    def rolar(self, distancia: int, passos: int = 14) -> None:
        for _ in range(passos):
            self.pagina.mouse.wheel(0, distancia / passos)
            time.sleep(0.035)

    # ── leitura ───────────────────────────────────────────────────────

    def destacar(self, alvo: Locator, segundos: float = 2.5) -> None:
        alvo.wait_for(state="visible")
        alvo.scroll_into_view_if_needed()
        alvo.evaluate(DESTACAR_JS, int(segundos * 1000))
        time.sleep(segundos)

    def ir_para(self, item_do_menu: str, titulo: str) -> None:
        """Clica no menu lateral e espera o título da página."""
        self.clicar(self.pagina.locator("a.nav-item", has_text=item_do_menu))
        self.pagina.get_by_role("heading", level=1, name=titulo).wait_for()

    def esperar_sumir(self, texto: str, prazo: float = 30) -> None:
        self.pagina.get_by_text(texto).first.wait_for(state="hidden", timeout=prazo * 1000)

    # ── diagnóstico ───────────────────────────────────────────────────

    def registrar_falha(self, nome: str) -> Path:
        self.pasta_falhas.mkdir(parents=True, exist_ok=True)
        self.pagina.screenshot(path=str(self.pasta_falhas / f"{nome}.png"))
        (self.pasta_falhas / f"{nome}.html").write_text(self.pagina.content())
        return self.pasta_falhas
