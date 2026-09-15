"""As cenas do painel web, na ordem da narração.

Cada cena espera a página mostrar o que precisa antes de agir. Os seletores
são textos visíveis, `aria-label` e as classes dos componentes: o painel não
tem `data-testid`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from playwright.sync_api import Page

from .dados import quantidade_de_reposicao
from .navegador import Navegador

EMAIL_ADMIN = "admin@demo.edu"
PRAZO_DO_RESUMO_MS = 90_000  # o resumo executivo espera a resposta da IA


@dataclass
class Roteiro:
    nav: Navegador
    pedido_curto: str | None
    log: Callable[[str], None] = print

    @property
    def pagina(self) -> Page:
        return self.nav.pagina


def login(r: Roteiro, senha: str) -> None:
    p = r.pagina
    p.locator("#email").wait_for()
    r.nav.pausa()
    r.nav.digitar(p.locator("#email"), EMAIL_ADMIN)
    r.nav.digitar(p.locator("#password"), senha, atraso_ms=45)
    r.nav.pausa(0.5)
    r.nav.clicar(p.get_by_role("button", name="Entrar"))
    p.get_by_role("heading", level=1, name="Dashboard Geral").wait_for()


def dashboard(r: Roteiro) -> None:
    p = r.pagina
    p.get_by_text("Carregando dashboard...").wait_for(state="hidden", timeout=PRAZO_DO_RESUMO_MS)
    p.get_by_role("heading", name="Resumo Executivo").wait_for()
    r.nav.pausa()
    r.nav.destacar(p.locator(".education-cards"), 3)
    r.nav.destacar(p.locator(".chart-card"), 2.5)
    resumo = p.locator(".executive-card")
    r.nav.mover_ate(resumo)
    r.nav.destacar(resumo, 5)
    r.nav.pausa()


def pedidos(r: Roteiro) -> None:
    p = r.pagina
    r.nav.ir_para("Pedidos", "Pedidos")
    r.nav.esperar_sumir("Carregando...")
    r.nav.pausa()
    if r.pedido_curto:
        r.nav.destacar(p.locator("tbody tr", has_text=f"#{r.pedido_curto}"), 3)
    else:
        r.log("  aviso: nenhum pedido para destacar")
    status = p.locator("select").first
    r.nav.escolher(status, rotulo="Entregue")
    r.nav.esperar_sumir("Carregando...")
    r.nav.destacar(p.locator("table"), 2.5)
    r.nav.escolher(status, rotulo="Todos os status")
    r.nav.esperar_sumir("Carregando...")
    r.nav.pausa(0.5)


def parceiros(r: Roteiro) -> None:
    p = r.pagina
    r.nav.ir_para("Parceiros", "Parceiros")
    leroy = p.locator("tbody tr", has_text="Leroy Merlin")
    leroy.first.wait_for()
    r.nav.pausa()
    r.nav.escolher(p.locator("select").first, valor="active")
    r.nav.destacar(leroy.first, 3)


def produtos_e_estoque(r: Roteiro) -> None:
    """Fecha a história da falta: o admin repõe a mesa que faltou."""
    p = r.pagina
    r.nav.ir_para("Produtos e Estoque", "Produtos e Estoque")
    r.nav.esperar_sumir("Carregando estoque...")
    r.nav.pausa()
    r.nav.digitar(p.get_by_placeholder("Filtrar nesta lista..."), "Mesa")
    mesa = p.locator("tbody tr", has_text="Mesa de estudo 120 cm")
    r.nav.destacar(mesa, 2.5)

    minimo = int(mesa.locator("td").nth(3).inner_text().strip() or 0)
    r.nav.clicar(mesa.get_by_role("button", name="Ajustar estoque"))
    dialogo = p.get_by_role("dialog")
    dialogo.get_by_role("heading", name="Ajustar estoque").wait_for()
    r.nav.pausa()
    r.nav.substituir(dialogo.locator('input[type="number"]'), str(quantidade_de_reposicao(minimo)))
    r.nav.escolher(dialogo.locator("select"), rotulo="Recebimento de lote")
    r.nav.digitar(dialogo.locator("textarea"), "Reposição da mesa que faltou na separação")
    r.nav.pausa()
    r.nav.clicar(dialogo.get_by_role("button", name="CONFIRMAR"))
    dialogo.wait_for(state="hidden")
    # O ajuste não mostra aviso: a página recarrega a tabela com o número novo.
    r.nav.esperar_sumir("Carregando estoque...")
    r.nav.pausa(0.5)
    r.nav.destacar(mesa, 3)


def transportadoras(r: Roteiro) -> None:
    p = r.pagina
    r.nav.ir_para("Transportadoras", "Transportadoras")
    p.locator("tbody tr").first.wait_for()
    r.nav.pausa()
    r.nav.clicar(p.get_by_role("button", name="Filtros"))
    r.nav.clicar(p.locator(".filter-popover").get_by_role("button", name="Ativas", exact=True))
    r.nav.destacar(p.locator("table"), 3)


def carregamentos(r: Roteiro) -> None:
    """O carregamento mais recente é o da frota própria que a coleta da Ana
    abriu sozinha."""
    p = r.pagina
    r.nav.ir_para("Carregamentos", "Carregamentos")
    linha = p.locator("tbody tr").first
    linha.wait_for()
    r.nav.pausa()
    r.nav.destacar(linha, 3.5)


def ocorrencias(r: Roteiro) -> None:
    """A falta da Ana já aparece resolvida: a escolha do substituto fecha a
    ocorrência."""
    p = r.pagina
    r.nav.ir_para("Ocorrências", "Gestão de Ocorrências")
    filtros = p.locator("select")
    r.nav.escolher(filtros.nth(1), rotulo="Falta de estoque")
    r.nav.escolher(filtros.nth(2), rotulo="RESOLVIDA")
    linha = p.locator("tbody tr", has_text="Sem estoque na prateleira").first
    r.nav.destacar(linha, 2.5)
    r.nav.clicar(linha.get_by_role("button", name="Ver ocorrência"))
    detalhe = p.locator(".modal")
    detalhe.wait_for()
    r.nav.pausa(2.5)
    r.nav.clicar(detalhe.get_by_role("button", name="Fechar", exact=True))
    detalhe.wait_for(state="hidden")


def encerramento(r: Roteiro) -> None:
    p = r.pagina
    r.nav.ir_para("Dashboard", "Dashboard Geral")
    p.get_by_text("Carregando dashboard...").wait_for(state="hidden", timeout=PRAZO_DO_RESUMO_MS)
    r.nav.pausa(2)


CENAS = [
    "dashboard",
    "pedidos",
    "parceiros",
    "produtos_e_estoque",
    "transportadoras",
    "carregamentos",
    "ocorrencias",
    "encerramento",
]
