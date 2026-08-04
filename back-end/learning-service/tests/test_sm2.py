"""Testes de caracterização de `atualizar_revisao` (services/sm2.py).

O brief desta task supunha uma assinatura `calcular_proxima_revisao(repeticoes,
facilidade, intervalo, qualidade)` com retorno por atributos (`.intervalo`,
`.repeticoes`, `.facilidade`) — isso não existe no código real. A função real
é `atualizar_revisao(dominio, intervalo_atual_dias, streak) -> tuple[float,
int, datetime]` (novo_intervalo_dias, novo_streak, proxima_revisao), um SM-2
simplificado baseado no nível de domínio calculado do diagnóstico, não nas
repetições/qualidade do algoritmo clássico. Confirmado lendo
`app/services/sm2.py` antes de escrever estes testes — eles travam o
comportamento ATUAL, não o suposto pelo brief.
"""

from datetime import UTC, datetime, timedelta

import pytest

from app.services.sm2 import atualizar_revisao


def test_low_mastery_resets_interval_to_one_day_and_zeroes_the_streak():
    intervalo, streak, _ = atualizar_revisao(dominio=0.2, intervalo_atual_dias=10.0, streak=3)
    assert intervalo == 1.0
    assert streak == 0


def test_mastery_exactly_at_the_low_boundary_is_not_low_anymore():
    # dominio < 0.4 é a faixa baixa; em 0.4 exato cai na faixa média.
    intervalo, streak, _ = atualizar_revisao(dominio=0.4, intervalo_atual_dias=1.0, streak=5)
    assert intervalo == pytest.approx(3.0)  # max(3.0, 1.0 * 1.3)
    assert streak == 0


def test_mid_mastery_stretches_the_interval_but_never_below_the_three_day_floor():
    intervalo, streak, _ = atualizar_revisao(dominio=0.5, intervalo_atual_dias=1.0, streak=0)
    assert intervalo == pytest.approx(3.0)
    assert streak == 0


def test_mid_mastery_uses_the_stretched_interval_once_above_the_floor():
    intervalo, streak, _ = atualizar_revisao(dominio=0.5, intervalo_atual_dias=10.0, streak=2)
    assert intervalo == pytest.approx(13.0)  # 10.0 * 1.3
    assert streak == 0  # faixa média sempre zera o streak, mesmo vindo de 2


def test_high_mastery_grows_the_interval_and_increments_the_streak():
    intervalo, streak, _ = atualizar_revisao(dominio=0.9, intervalo_atual_dias=2.0, streak=0)
    assert intervalo == pytest.approx(3.0)  # fator = 1.5 + 0 * 0.3
    assert streak == 1


def test_high_mastery_growth_accelerates_with_a_longer_streak():
    intervalo, streak, _ = atualizar_revisao(dominio=0.9, intervalo_atual_dias=2.0, streak=3)
    assert intervalo == pytest.approx(4.8)  # fator = 1.5 + 3 * 0.3 = 2.4
    assert streak == 4


def test_boundary_at_seventy_percent_counts_as_high_mastery():
    intervalo, streak, _ = atualizar_revisao(dominio=0.7, intervalo_atual_dias=2.0, streak=0)
    assert intervalo == pytest.approx(3.0)
    assert streak == 1


def test_next_review_is_now_plus_the_new_interval_in_days():
    before = datetime.now(UTC)
    _, _, proxima_revisao = atualizar_revisao(dominio=0.9, intervalo_atual_dias=2.0, streak=0)
    after = datetime.now(UTC)

    assert (before + timedelta(days=3.0)) - timedelta(seconds=2) <= proxima_revisao
    assert proxima_revisao <= (after + timedelta(days=3.0)) + timedelta(seconds=2)
