"""Decisões do roteiro do painel que não dependem do navegador."""

from __future__ import annotations

import re
from datetime import datetime

REPOSICAO_MINIMA = 20


def _criado_em(pedido: dict) -> datetime:
    return datetime.fromisoformat(str(pedido["created_at"]).replace("Z", "+00:00"))


def pedido_em_destaque(pedidos: list[dict]) -> str | None:
    """Recorte curto ("01A0A1AF") do pedido que o painel destaca.

    É o entregue mais recente — o da Ana, quando o painel roda logo depois da
    demo do celular. Sem nenhum entregue, fica com o mais recente.
    """
    if not pedidos:
        return None
    entregues = [p for p in pedidos if p.get("status") == "ENTREGUE"]
    escolhido = max(entregues or pedidos, key=_criado_em)
    return str(escolhido["id"])[:8].upper()


def ler_tamanho(texto: str) -> tuple[int, int]:
    """`"1920x1080"` → `(1920, 1080)`."""
    achado = re.fullmatch(r"(\d+)[xX](\d+)", texto.strip())
    if not achado or int(achado.group(1)) <= 0 or int(achado.group(2)) <= 0:
        raise ValueError(f"tamanho deve ser LARGURAxALTURA, ex.: 1920x1080 (veio {texto!r})")
    return int(achado.group(1)), int(achado.group(2))


def quantidade_de_reposicao(minimo: int) -> int:
    """Um lote que tira o item de "estoque baixo" com folga."""
    return max(REPOSICAO_MINIMA, minimo * 2)
