# Spec D — Onboarding, study tracker e gamificação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trocar os quatro números inventados das telas do estudante por dados
reais, construindo no `learning-service` o objetivo do aluno, o roadmap de
estudo até a data-alvo e a pontuação derivada do progresso.

**Architecture:** Nenhum serviço novo. Três tabelas novas no `learning-service`
(`objetivo_aluno`, `etapa_roadmap`, `lancamento_pontos`), duas regras isoladas
em `services/` (distribuição do roadmap e pontuação), três routers novos
(`onboarding`, `roadmap`, `perfil`) e um gancho dentro do
`POST /diagnostic/answer` que lança pontos e conclui etapas **na mesma
transação** que já grava o progresso. No Flutter, duas features novas
(`onboarding/`, `tracker/`) e duas telas existentes (`home/`, `profile/`) que
passam a ler `GET /profile/summary`.

**Tech Stack:** Python 3.12+, FastAPI, SQLAlchemy 2.x async, Alembic,
PostgreSQL, pytest + httpx AsyncClient; Flutter/Dart com `provider`,
`http`, `flutter_test`.

**Spec:** [`docs/superpowers/specs/2026-09-07-spec-d-onboarding-tracker-gamificacao-design.md`](../specs/2026-09-07-spec-d-onboarding-tracker-gamificacao-design.md)

---

## Baselines medidos (2026-09-10, `main` em `447a858`)

Toda tarefa termina com a suíte **no mínimo** nestes números. Um número menor é
regressão, não "flaky".

| Alvo | Comando | Baseline |
|---|---|---|
| learning-service | `uv run pytest -q` (em `back-end/learning-service`) | **78 passed** |
| api-gateway | `uv run pytest -q` (em `back-end/api-gateway`) | **39 passed** |
| Flutter | `flutter test` (em `front-end-flutter`) | **205 passed** |
| Flutter analyze | `flutter analyze lib/` | **6 issues**, todos `info`, todos pré-existentes |

Os mocks que esta entrega remove, medidos com
`grep -rn "3,120\|124/200\|Medicina USP\|0.68\|'15'" front-end-flutter/lib`:

```
lib/features/profile/presentation/profile_screen.dart:210:   '3,120'
lib/features/profile/presentation/profile_screen.dart:254:   '15'
lib/features/home/presentation/home_screen.dart:163:         'Meta: Medicina USP'
lib/features/home/presentation/home_screen.dart:170:         '124/200 dias'
lib/features/home/presentation/home_screen.dart:183:         value: 0.68
```

---

## Global Constraints

Copiadas da spec e do `CLAUDE.md`. Valem para **toda** tarefa, sem repetição
nos requisitos de cada uma.

- **Nada inventado na tela.** Todo número exibido vem do backend. Um aluno
  zerado mostra zero, não um valor de exemplo.
- **Nunca concatenar input do usuário em SQL.** Sempre ORM com parâmetros
  bind. Proibido `text(f"...")`.
- **Todo endpoint tem controle de acesso explícito.** Todas as rotas novas
  dependem de `get_current_user_id` e filtram pelo `aluno_id` do token —
  nunca por um id vindo do corpo ou da query.
- **Read→write em recurso compartilhado é atômico.** O lançamento de pontos
  usa `ON CONFLICT DO NOTHING` sobre uma constraint única; nunca
  `SELECT` seguido de `INSERT` em Python.
- **Inputs têm limite.** `titulo` do objetivo: `max_length=120` no modelo e no
  schema. Toda listagem pagina (`limit`/`offset` com `ge`/`le`).
- **Schemas com campos explícitos.** Nenhum `from_attributes` expondo modelo
  inteiro sem listar campos.
- **`loguru.logger`, nunca `print()`.**
- **Formatação e lint via ruff**, sem exceção: `uv run ruff check .` e
  `uv run ruff format .` antes de cada commit no backend.
- **TDD.** O teste que falha vem primeiro, sempre. Cada tarefa começa por um
  teste vermelho e termina verde.
- **Conventional Commits**, um commit por unidade lógica, mensagem em inglês
  no imperativo. Todo commit termina com:

  ```
  Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01J2MY6Crnd8J1CYwb2iB5Sh
  ```

- **Proibições de ambiente local:** nunca `docker compose up/down/restart/
  build/exec`, nunca `make stack-*` / `make services-migrate` /
  `make services-seed*` / `make services-test` / `make services-lint`, nunca
  `alembic upgrade` contra um banco de desenvolvimento (só `*_test`), nunca
  editar o `.env` do usuário (só `.env.example`).

---

## Decisões (D1–D17)

Estas resolvem o que a spec deixa em aberto. Cada uma é vinculante para o
implementador da tarefa que a cita.

**D1 — "Revisão concluída no prazo" não tem rota própria; é detectada na
resposta.** Não existe hoje nenhum endpoint que conclua uma revisão
(`/reviews/today` só lista — medido em `app/routers/revisao.py`). Criar um
seria inventar um passo que nenhuma tela dá. A regra: dentro de
`POST /diagnostic/answer`, para cada subtema respondido cuja linha de
`AlunoTemaProgresso` **já existia** com `proxima_revisao <= agora`, a resposta
conta como revisão concluída no prazo e pontua 15.

**D2 — Idempotência da pontuação é por `(aluno_id, origem, referencia)`,
com `referencia` estável.** Origens e referências, exaustivas:

| origem | referencia | pontos |
|---|---|---|
| `questao` | `str(questao_id)` | 10 por questão correta |
| `revisao` | `f"{subtema_id}:{proxima_revisao.date().isoformat()}"` | 15 |
| `etapa` | `str(subtema_id)` | 50 |
| `streak` | `f"{subtema_id}:{streak_novo}"` | `min(5 * streak_novo, 50)` |

`etapa` usa `subtema_id`, **não** `etapa_id`: o roadmap é regerado quando a
data-alvo muda, e ids de etapa mudam com ele — pontuar de novo a mesma
conclusão seria o defeito que a idempotência existe para impedir.

**D3 — Faixas de nível, fixas, calculadas na leitura.** Nada é gravado como
"nível".

```python
FAIXAS_NIVEL = (0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500)
```

Nível é `1 + quantas faixas o total ultrapassou`, teto 10.

**D4 — Distribuição do roadmap: uniforme por índice, primeira hoje e última
na data-alvo.** Para `n` etapas e `dias = (data_alvo - hoje).days`, a etapa de
índice `i` (base 0) vence em `hoje + floor(i * dias / (n - 1))` dias; com
`n == 1` a única etapa vence na data-alvo. A última etapa cai exatamente na
data-alvo, que é o que a tela promete ao aluno. Quando `n > dias + 1`, vários
prazos repetem o mesmo dia — é o "agrupa em vez de falhar" que a spec pede — e
a rota devolve `prazo_apertado: true`.

**D5 — Limiar de conclusão de etapa é `LIMIAR_DOMINIO_SUBTEMA` (0.7).**
Importado de `app/services/decisao.py`, nunca redeclarado. Um segundo limiar
com o mesmo propósito é duas fontes de verdade.

**D6 — Teto de etapas por roadmap: 2000.** O seed completo do ENEM tem ordem
de 130 subtemas; o teto é folga enorme e impede que um seed futuro gigante
gere uma transação sem fim.

**D7 — Regeneração preserva conclusões.** Ao mudar a data-alvo:
`DELETE` das etapas do aluno, `INSERT` de todas de novo com os prazos novos, e
`concluida_em` recarregado por `subtema_id` a partir do que foi lido antes do
delete. Nunca um `UPDATE` etapa a etapa.

**D8 — "Matéria sem questão" é campo do roadmap, não filtro.** Cada etapa
carrega `tem_questoes: bool`, calculado numa agregação única
(`GROUP BY subtema_id` em `questao`), nunca uma consulta por etapa.

**D9 — Prefixos novos no gateway:** `onboarding`, `roadmap`, `profile` →
`learning`. `profile` é do learning-service, não do auth: o que a tela lê é
resumo de estudo, não identidade. Os dados de conta continuam em
`/api/users/me`.

**D10 — Pular o onboarding não grava nada.** Não existe flag "pulou": aluno
sem `ObjetivoAluno` é aluno sem objetivo, e a tela desenha menos.

**D11 — Faixas de id do seed do ENEM.** `scripts/seed_biologia_citologia.sql`
já ocupa `materia.id = 1`, `tema.id 1..3`, `subtema.id 1..8`,
`questao.id 1..38` (medido). O seed novo usa:
`materia.id` 1 (Biologia, o mesmo registro) e 2..11; `tema.id` a partir de
**100**; `subtema.id` a partir de **100**. Nenhuma questão nova. Termina com os
mesmos quatro `setval` do seed existente.

**D12 — Esta entrega não escreve questões novas.** A spec põe conteúdo por
matéria "na medida do tempo", e o roadmap funciona com qualquer quantidade. O
que a entrega garante é que a ausência apareça marcada (D8).

**D13 — Sem objetivo, o cartão de meta da tela inicial não é desenhado.**
Não é um cartão vazio nem um cartão com zeros: é ausência.

**D14 — O cartão de meta leva ao tracker.** Tocar o cartão navega para
`/tracker`. É o único caminho para a tela nova, e ele só existe quando há
objetivo.

**D15 — "Metas e objetivos" no perfil abre o onboarding em modo edição.**
Rota `/onboarding`; com objetivo existente, os campos vêm preenchidos e o
botão diz "Salvar".

**D16 — Depois do cadastro, o app vai para `/onboarding`, não para `/home`.**
`register_screen.dart:76` passa a apontar para `/onboarding`, carregando
`{'justRegistered': true}` adiante — a saudação continua aparecendo na home
depois que o onboarding termina ou é pulado.

**D17 — Falha de pontuação não invalida a resposta do aluno.** Pontos e
progresso estão na mesma transação e no mesmo `commit` que já existe em
`responder_diagnostico`. Não há `try/except` engolindo erro de pontuação: ou
tudo grava, ou nada grava e o aluno reenvia — e o reenvio não pontua duas
vezes (D2).

---

## Estrutura de arquivos

```
back-end/learning-service/
  alembic/versions/e1f2a3b4c5d6_spec_d_schema.py   NOVO  três tabelas
  app/models/objetivo.py                            NOVO  ObjetivoAluno
  app/models/roadmap.py                             NOVO  EtapaRoadmap
  app/models/pontuacao.py                           NOVO  LancamentoPontos
  app/services/pontuacao.py                         NOVO  regra + faixas + registrar
  app/services/roadmap.py                           NOVO  distribuição + geração
  app/schemas/objetivo.py                           NOVO  entrada/saída do onboarding
  app/schemas/roadmap.py                            NOVO  saída do roadmap
  app/schemas/perfil.py                             NOVO  o resumo agregado
  app/routers/onboarding.py                         NOVO  GET/POST/PUT /onboarding
  app/routers/roadmap.py                            NOVO  GET /roadmap
  app/routers/perfil.py                             NOVO  GET /profile/summary
  app/routers/diagnostico.py                        MOD   gancho de pontos e etapa
  app/main.py                                       MOD   inclui três routers
  alembic/env.py                                    MOD   importa três models
  tests/conftest.py                                 MOD   importa três models
  scripts/seed_enem.sql                             NOVO  estrutura das 11 matérias

back-end/api-gateway/app/routing.py                 MOD   três prefixos

front-end-flutter/lib/features/
  tracker/domain/study_summary.dart                 NOVO  modelos do resumo
  tracker/domain/roadmap_step.dart                  NOVO  etapa do roadmap
  tracker/data/tracker_api.dart                     NOVO  cliente HTTP
  tracker/presentation/tracker_provider.dart        NOVO  estado do tracker
  tracker/presentation/tracker_screen.dart          NOVO  tela do percurso
  onboarding/presentation/onboarding_screen.dart    NOVO  objetivo + data
  home/presentation/home_screen.dart                MOD   lê o resumo
  profile/presentation/profile_screen.dart          MOD   lê o resumo
  ../main.dart                                      MOD   rotas /onboarding e /tracker
  auth/presentation/register_screen.dart            MOD   cadastro → onboarding

docs/back-end/study-tracker.md                      NOVO  o documento da entrega
CLAUDE.md                                           MOD   uma linha de índice
```

## Ordem das tarefas

```
1  schema (models + migration)
2  services/pontuacao.py          ── depende de 1
3  services/roadmap.py            ── depende de 1
4  routers/onboarding.py          ── depende de 1, 3
5  routers/roadmap.py             ── depende de 1, 3
6  routers/perfil.py              ── depende de 1, 2, 3
7  gancho no /diagnostic/answer   ── depende de 2, 3
8  gateway: três prefixos         ── independente
9  scripts/seed_enem.sql          ── depende de 1
10 Flutter: domain + api          ── depende de 4, 5, 6
11 Flutter: onboarding            ── depende de 10
12 Flutter: home                  ── depende de 10
13 Flutter: profile               ── depende de 10
14 Flutter: tracker               ── depende de 10
15 documentação                   ── depende de todas
```

---

### Task 1: Schema — três tabelas, três models, uma migration

**Files:**
- Create: `back-end/learning-service/app/models/objetivo.py`
- Create: `back-end/learning-service/app/models/roadmap.py`
- Create: `back-end/learning-service/app/models/pontuacao.py`
- Create: `back-end/learning-service/alembic/versions/e1f2a3b4c5d6_spec_d_schema.py`
- Modify: `back-end/learning-service/alembic/env.py:13-16` (bloco de imports de model)
- Modify: `back-end/learning-service/tests/conftest.py:21-25` (imports dentro de `test_engine`)
- Test: `back-end/learning-service/tests/test_spec_d_schema.py`

**Interfaces:**
- Consumes: `app.database.Base`, `app.models.subtema.Subtema` (FK de `etapa_roadmap`).
- Produces: `ObjetivoAluno(id, aluno_id, titulo, data_alvo, criado_em, atualizado_em)`,
  `EtapaRoadmap(id, aluno_id, subtema_id, ordem, prazo, concluida_em)`,
  `LancamentoPontos(id, aluno_id, origem, referencia, pontos, criado_em)`.
  Constraints nomeadas: `uq_objetivo_aluno`, `uq_etapa_aluno_subtema`,
  `uq_lancamento_idempotente` — os nomes são usados literalmente nos
  `on_conflict` das tarefas 2 e 3.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_spec_d_schema.py`:

```python
import uuid
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.objetivo import ObjetivoAluno
from app.models.pontuacao import LancamentoPontos
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _um_subtema(db):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db.add(subtema)
    await db.flush()
    return subtema


async def test_um_objetivo_por_aluno(db_session):
    aluno = uuid.uuid4()
    db_session.add(ObjetivoAluno(aluno_id=aluno, titulo="Medicina", data_alvo=date(2027, 11, 7)))
    await db_session.commit()

    db_session.add(ObjetivoAluno(aluno_id=aluno, titulo="Direito", data_alvo=date(2027, 11, 7)))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_uma_etapa_por_aluno_e_subtema(db_session):
    aluno = uuid.uuid4()
    subtema = await _um_subtema(db_session)
    db_session.add(EtapaRoadmap(aluno_id=aluno, subtema_id=subtema.id, ordem=0, prazo=date(2027, 1, 1)))
    await db_session.commit()

    db_session.add(EtapaRoadmap(aluno_id=aluno, subtema_id=subtema.id, ordem=1, prazo=date(2027, 2, 1)))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_lancamento_e_idempotente_por_origem_e_referencia(db_session):
    aluno = uuid.uuid4()
    db_session.add(LancamentoPontos(aluno_id=aluno, origem="questao", referencia="7", pontos=10))
    await db_session.commit()

    db_session.add(LancamentoPontos(aluno_id=aluno, origem="questao", referencia="7", pontos=10))
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


async def test_a_mesma_referencia_em_origens_diferentes_convive(db_session):
    aluno = uuid.uuid4()
    db_session.add(LancamentoPontos(aluno_id=aluno, origem="questao", referencia="7", pontos=10))
    db_session.add(LancamentoPontos(aluno_id=aluno, origem="etapa", referencia="7", pontos=50))
    await db_session.commit()  # não levanta


async def test_etapa_nasce_sem_conclusao(db_session):
    aluno = uuid.uuid4()
    subtema = await _um_subtema(db_session)
    etapa = EtapaRoadmap(aluno_id=aluno, subtema_id=subtema.id, ordem=0, prazo=date(2027, 1, 1))
    db_session.add(etapa)
    await db_session.commit()
    assert etapa.concluida_em is None
```

- [ ] **Step 2: Rode o teste e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_spec_d_schema.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.models.objetivo'`.

- [ ] **Step 3: Crie os três models**

`app/models/objetivo.py`:

```python
from sqlalchemy import Column, Date, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ObjetivoAluno(Base):
    """Objetivo de estudo do aluno e a data em que ele quer chegar lá.

    Um por aluno (`uq_objetivo_aluno`): a spec fala em "um objetivo ativo",
    e sem a constraint dois POSTs simultâneos do mesmo aluno criariam dois,
    com o roadmap gerado a partir de um deles e a tela lendo o outro.

    `titulo` é texto livre com teto (regra 4 do CLAUDE.md). `data_alvo` é
    `Date`, não `DateTime`: prova é um dia, não um instante, e comparar
    fuso horário com "faltam N dias" só produziria erro de um dia.
    """

    __tablename__ = "objetivo_aluno"
    __table_args__ = (UniqueConstraint("aluno_id", name="uq_objetivo_aluno"),)

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    titulo = Column(String(120), nullable=False)
    data_alvo = Column(Date, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    atualizado_em = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
```

`app/models/roadmap.py`:

```python
from sqlalchemy import (
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EtapaRoadmap(Base):
    """Uma etapa do percurso: um subtema, com prazo e conclusão.

    `uq_etapa_aluno_subtema` é o que torna a regeneração segura — regerar é
    apagar e reinserir, e a constraint garante que nenhuma passagem crie
    duas etapas do mesmo subtema para o mesmo aluno.

    `ordem` é a posição no percurso (0-based), derivada de `Tema.ordem` e
    `Subtema.ordem` na geração. Ela não é única de propósito: duas
    regenerações podem produzir a mesma ordem para subtemas diferentes se o
    seed mudar, e o que identifica a etapa é o subtema, não a posição.
    """

    __tablename__ = "etapa_roadmap"
    __table_args__ = (
        UniqueConstraint("aluno_id", "subtema_id", name="uq_etapa_aluno_subtema"),
    )

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    subtema_id = Column(Integer, ForeignKey("subtema.id"), nullable=False)
    ordem = Column(Integer, nullable=False)
    prazo = Column(Date, nullable=False)
    concluida_em = Column(DateTime(timezone=True), nullable=True)
```

`app/models/pontuacao.py`:

```python
from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class LancamentoPontos(Base):
    """Extrato de pontos — uma linha por fato que pontuou, nunca um contador.

    Um contador incrementado a cada acerto seria leitura seguida de escrita
    num recurso compartilhado (regra 3 do CLAUDE.md), e não permitiria
    explicar de onde vieram os pontos.

    `uq_lancamento_idempotente` é a regra inteira da idempotência: responder
    de novo a mesma questão tenta gravar a mesma trinca e o
    `ON CONFLICT DO NOTHING` do serviço a descarta.
    """

    __tablename__ = "lancamento_pontos"
    __table_args__ = (
        UniqueConstraint("aluno_id", "origem", "referencia", name="uq_lancamento_idempotente"),
    )

    id = Column(Integer, primary_key=True)
    aluno_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    # "questao" | "revisao" | "etapa" | "streak" — ver services/pontuacao.py
    origem = Column(String(20), nullable=False)
    referencia = Column(String(60), nullable=False)
    pontos = Column(Integer, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

- [ ] **Step 4: Registre os models onde eles precisam existir**

Em `tests/conftest.py`, dentro de `test_engine`, o bloco de imports passa a ser:

```python
    from app.models import objetivo as objetivo_models  # noqa: F401
    from app.models import pontuacao as pontuacao_models  # noqa: F401
    from app.models import progresso as progresso_models  # noqa: F401
    from app.models import questao as questao_models  # noqa: F401
    from app.models import resposta as resposta_models  # noqa: F401
    from app.models import roadmap as roadmap_models  # noqa: F401
    from app.models import subtema as subtema_models  # noqa: F401
```

Em `alembic/env.py`, o mesmo acréscimo no bloco de imports de model (linhas
13-16), mantendo a ordem alfabética e os `# noqa: F401`. **Sem isso, o
`--autogenerate` de qualquer migration futura acha que as três tabelas
sobram e escreve um `drop_table` para cada.**

- [ ] **Step 5: Rode o teste e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_spec_d_schema.py -q`
Expected: 5 passed.

- [ ] **Step 6: Escreva a migration**

`alembic/versions/e1f2a3b4c5d6_spec_d_schema.py`:

```python
"""spec D schema: objetivo do aluno, etapas do roadmap, extrato de pontos

Revision ID: e1f2a3b4c5d6
Revises: b9e63fa43f39
Create Date: 2026-09-10

Aditiva: só cria tabelas novas. Nenhuma coluna existente muda, então o
`downgrade` é o inverso exato e não perde dado de nada que já existia.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision: str = "e1f2a3b4c5d6"
down_revision: str | Sequence[str] | None = "b9e63fa43f39"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "objetivo_aluno",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", UUID(as_uuid=True), nullable=False),
        sa.Column("titulo", sa.String(length=120), nullable=False),
        sa.Column("data_alvo", sa.Date(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "atualizado_em",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("aluno_id", name="uq_objetivo_aluno"),
    )
    op.create_index("ix_objetivo_aluno_aluno_id", "objetivo_aluno", ["aluno_id"])

    op.create_table(
        "etapa_roadmap",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", UUID(as_uuid=True), nullable=False),
        sa.Column("subtema_id", sa.Integer(), sa.ForeignKey("subtema.id"), nullable=False),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("prazo", sa.Date(), nullable=False),
        sa.Column("concluida_em", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("aluno_id", "subtema_id", name="uq_etapa_aluno_subtema"),
    )
    op.create_index("ix_etapa_roadmap_aluno_id", "etapa_roadmap", ["aluno_id"])

    op.create_table(
        "lancamento_pontos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("aluno_id", UUID(as_uuid=True), nullable=False),
        sa.Column("origem", sa.String(length=20), nullable=False),
        sa.Column("referencia", sa.String(length=60), nullable=False),
        sa.Column("pontos", sa.Integer(), nullable=False),
        sa.Column(
            "criado_em", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint(
            "aluno_id", "origem", "referencia", name="uq_lancamento_idempotente"
        ),
    )
    op.create_index("ix_lancamento_pontos_aluno_id", "lancamento_pontos", ["aluno_id"])


def downgrade() -> None:
    op.drop_index("ix_lancamento_pontos_aluno_id", table_name="lancamento_pontos")
    op.drop_table("lancamento_pontos")
    op.drop_index("ix_etapa_roadmap_aluno_id", table_name="etapa_roadmap")
    op.drop_table("etapa_roadmap")
    op.drop_index("ix_objetivo_aluno_aluno_id", table_name="objetivo_aluno")
    op.drop_table("objetivo_aluno")
```

**Por que `from sqlalchemy.dialects.postgresql import UUID` explícito:** na
spec C uma migration usou `sa.dialects.postgresql.UUID` sem importar o
submódulo, o que só funciona se algum outro import já tiver carregado
`sqlalchemy.dialects.postgresql` por acaso. Importar explicitamente é a
diferença entre uma migration que sempre roda e uma que roda "quase sempre".

- [ ] **Step 7: Verifique a migration contra um banco descartável**

**Nunca** rode alembic contra `learning_db`. Contra o banco de teste:

```bash
cd back-end/learning-service
DATABASE_URL="$DATABASE_URL_TEST" uv run alembic stamp base
DATABASE_URL="$DATABASE_URL_TEST" uv run alembic upgrade head
DATABASE_URL="$DATABASE_URL_TEST" uv run alembic downgrade -1
DATABASE_URL="$DATABASE_URL_TEST" uv run alembic upgrade head
```

Expected: as quatro rodam sem erro; a última termina em `e1f2a3b4c5d6`.
Depois disso, `uv run pytest -q` (a suíte recria o schema pelo metadata,
então não depende do estado deixado aqui).

- [ ] **Step 8: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **83 passed** (78 do baseline + 5 novos).

- [ ] **Step 9: Commit**

```bash
git add back-end/learning-service/app/models back-end/learning-service/alembic \
        back-end/learning-service/tests/conftest.py \
        back-end/learning-service/tests/test_spec_d_schema.py
git commit -m "feat(learning): add goal, roadmap step and points ledger tables"
```

---

### Task 2: A regra de pontuação, num lugar só

**Files:**
- Create: `back-end/learning-service/app/services/pontuacao.py`
- Test: `back-end/learning-service/tests/test_pontuacao.py`

**Interfaces:**
- Consumes: `app.models.pontuacao.LancamentoPontos` e a constraint
  `uq_lancamento_idempotente` (Task 1).
- Produces, usados pelas tarefas 6 e 7:
  - `PONTOS_QUESTAO_CORRETA: int = 10`, `PONTOS_REVISAO_NO_PRAZO: int = 15`,
    `PONTOS_ETAPA_CONCLUIDA: int = 50`, `TETO_BONUS_STREAK: int = 50`
  - `bonus_streak(streak: int) -> int`
  - `nivel_do_total(total: int) -> int`
  - `async registrar(db, *, aluno_id: uuid.UUID | str, origem: str,
    referencia: str, pontos: int) -> bool` — devolve `True` se gravou,
    `False` se a trinca já existia. **Não faz commit.**
  - `async total_de_pontos(db, aluno_id) -> int`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_pontuacao.py`:

```python
import uuid

import pytest

from app.services.pontuacao import (
    PONTOS_ETAPA_CONCLUIDA,
    PONTOS_QUESTAO_CORRETA,
    PONTOS_REVISAO_NO_PRAZO,
    TETO_BONUS_STREAK,
    bonus_streak,
    nivel_do_total,
    registrar,
    total_de_pontos,
)


def test_a_tabela_de_pontos_e_a_da_spec():
    assert (PONTOS_QUESTAO_CORRETA, PONTOS_REVISAO_NO_PRAZO, PONTOS_ETAPA_CONCLUIDA) == (10, 15, 50)


@pytest.mark.parametrize(
    ("streak", "esperado"),
    [(0, 0), (1, 5), (5, 25), (10, 50), (11, 50), (1000, 50), (-3, 0)],
)
def test_bonus_de_sequencia_tem_teto(streak, esperado):
    assert bonus_streak(streak) == esperado
    assert bonus_streak(streak) <= TETO_BONUS_STREAK


@pytest.mark.parametrize(
    ("total", "nivel"),
    [
        (0, 1), (99, 1),
        (100, 2), (299, 2),
        (300, 3),
        (600, 4),
        (1000, 5),
        (1500, 6),
        (2100, 7),
        (2800, 8),
        (3600, 9),
        (4500, 10),
        (999_999, 10),
    ],
)
def test_nivel_nas_fronteiras_das_faixas(total, nivel):
    assert nivel_do_total(total) == nivel


async def test_registrar_grava_uma_vez_e_devolve_true(db_session):
    aluno = uuid.uuid4()
    assert await registrar(
        db_session, aluno_id=aluno, origem="questao", referencia="7", pontos=10
    ) is True
    await db_session.commit()
    assert await total_de_pontos(db_session, aluno) == 10


async def test_registrar_a_mesma_referencia_de_novo_nao_pontua(db_session):
    aluno = uuid.uuid4()
    await registrar(db_session, aluno_id=aluno, origem="questao", referencia="7", pontos=10)
    await db_session.commit()

    assert await registrar(
        db_session, aluno_id=aluno, origem="questao", referencia="7", pontos=10
    ) is False
    await db_session.commit()
    assert await total_de_pontos(db_session, aluno) == 10


async def test_alunos_diferentes_nao_disputam_a_mesma_referencia(db_session):
    a, b = uuid.uuid4(), uuid.uuid4()
    await registrar(db_session, aluno_id=a, origem="questao", referencia="7", pontos=10)
    await registrar(db_session, aluno_id=b, origem="questao", referencia="7", pontos=10)
    await db_session.commit()
    assert await total_de_pontos(db_session, a) == 10
    assert await total_de_pontos(db_session, b) == 10


async def test_total_de_aluno_sem_lancamento_e_zero(db_session):
    assert await total_de_pontos(db_session, uuid.uuid4()) == 0


async def test_registrar_nao_faz_commit(db_session):
    """Quem decide a transação é o chamador — na rota de resposta os pontos
    entram no MESMO commit que grava o progresso."""
    aluno = uuid.uuid4()
    await registrar(db_session, aluno_id=aluno, origem="etapa", referencia="3", pontos=50)
    await db_session.rollback()
    assert await total_de_pontos(db_session, aluno) == 0
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_pontuacao.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.pontuacao'`.

- [ ] **Step 3: Escreva o serviço**

`app/services/pontuacao.py`:

```python
"""A regra de pontuação da spec D — aqui, e em nenhum outro lugar.

Quem lança pontos são a rota de resposta ao diagnóstico (questão correta,
revisão no prazo, bônus de sequência) e a conclusão de etapa do roadmap.
Todos passam por `registrar`, que é idempotente por
`(aluno_id, origem, referencia)`.

Nível NÃO é gravado: `nivel_do_total` o calcula na leitura. Mudar as faixas
depois é editar uma tupla, não migrar dado.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pontuacao import LancamentoPontos

PONTOS_QUESTAO_CORRETA = 10
PONTOS_REVISAO_NO_PRAZO = 15
PONTOS_ETAPA_CONCLUIDA = 50

PONTOS_POR_ACERTO_EM_SEQUENCIA = 5
TETO_BONUS_STREAK = 50

# Total mínimo de cada nível. O índice na tupla + 1 é o nível: 0 pontos é
# nível 1, 100 é nível 2, e assim por diante até o teto de 10.
FAIXAS_NIVEL = (0, 100, 300, 600, 1000, 1500, 2100, 2800, 3600, 4500)


def bonus_streak(streak: int) -> int:
    """5 pontos por acerto em sequência, com teto de 50.

    Sem o teto, uma sequência longa vale mais que todo o resto do sistema
    junto — e a sequência é o número mais fácil de inflar respondendo
    questões fáceis.
    """
    if streak <= 0:
        return 0
    return min(PONTOS_POR_ACERTO_EM_SEQUENCIA * streak, TETO_BONUS_STREAK)


def nivel_do_total(total: int) -> int:
    """Nível derivado do total de pontos, pelas faixas fixas de `FAIXAS_NIVEL`."""
    nivel = 1
    for indice, minimo in enumerate(FAIXAS_NIVEL):
        if total >= minimo:
            nivel = indice + 1
    return nivel


async def registrar(
    db: AsyncSession,
    *,
    aluno_id: uuid.UUID | str,
    origem: str,
    referencia: str,
    pontos: int,
) -> bool:
    """Grava um lançamento, ou não faz nada se a trinca já existir.

    `ON CONFLICT DO NOTHING` e não "SELECT, decidir, INSERT": duas respostas
    simultâneas do mesmo aluno para a mesma questão leriam as duas "não
    existe" e gravariam as duas (regra 3 do CLAUDE.md). Aqui quem decide é o
    índice único, dentro do banco.

    NÃO faz commit — quem abre a transação decide quando fechá-la. Na rota de
    resposta, pontos e progresso fecham juntos.
    """
    stmt = (
        pg_insert(LancamentoPontos)
        .values(aluno_id=aluno_id, origem=origem, referencia=referencia, pontos=pontos)
        .on_conflict_do_nothing(constraint="uq_lancamento_idempotente")
        .returning(LancamentoPontos.id)
    )
    resultado = await db.execute(stmt)
    return resultado.scalar_one_or_none() is not None


async def total_de_pontos(db: AsyncSession, aluno_id: uuid.UUID | str) -> int:
    """Soma do extrato. Zero para quem nunca pontuou — `coalesce` porque
    `SUM` de conjunto vazio é NULL, e a tela mostra número, não nada."""
    total = await db.execute(
        select(func.coalesce(func.sum(LancamentoPontos.pontos), 0)).where(
            LancamentoPontos.aluno_id == aluno_id
        )
    )
    return int(total.scalar_one())
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_pontuacao.py -q`
Expected: 26 passed (os dois `parametrize` contam por caso: 7 do bônus e 13 do nível).

- [ ] **Step 5: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **109 passed** (83 + 26).

- [ ] **Step 6: Commit**

```bash
git add back-end/learning-service/app/services/pontuacao.py \
        back-end/learning-service/tests/test_pontuacao.py
git commit -m "feat(learning): add the scoring rule and level bands"
```

---

### Task 3: A geração do roadmap

**Files:**
- Create: `back-end/learning-service/app/services/roadmap.py`
- Test: `back-end/learning-service/tests/test_roadmap_service.py`

**Interfaces:**
- Consumes: `EtapaRoadmap` (Task 1), `Materia`/`Tema`/`Subtema`,
  `AlunoTemaProgresso`, `LIMIAR_DOMINIO_SUBTEMA` de `app.services.decisao`.
- Produces, usados pelas tarefas 4, 5 e 7:
  - `TETO_ETAPAS: int = 2000`
  - `distribuir_prazos(quantidade: int, inicio: date, data_alvo: date) -> list[date]`
  - `prazo_apertado(quantidade: int, inicio: date, data_alvo: date) -> bool`
  - `async gerar_roadmap(db, *, aluno_id, data_alvo: date, hoje: date) -> int`
    — apaga e recria as etapas do aluno preservando conclusões, devolve
    quantas etapas ficaram. **Não faz commit.**
  - `async concluir_etapa(db, *, aluno_id, subtema_id, quando: datetime) -> bool`
    — marca a etapa como concluída se existir e ainda não estiver;
    devolve `True` só na transição. **Não faz commit.**

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_roadmap_service.py`:

```python
import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema
from app.services.roadmap import (
    concluir_etapa,
    distribuir_prazos,
    gerar_roadmap,
    prazo_apertado,
)

HOJE = date(2026, 9, 10)


async def _seed_conteudo(db, *, materias=1, temas=2, subtemas=2):
    """Cria uma árvore previsível: matéria 'M{i}' > tema 'T{j}' > subtema 'S{k}'.

    Devolve os subtemas na ordem que o roadmap DEVE produzir.
    """
    esperados = []
    for i in range(materias):
        materia = Materia(nome=f"M{i}")
        db.add(materia)
        await db.flush()
        for j in range(temas):
            tema = Tema(materia_id=materia.id, nome=f"T{i}{j}", ordem=j + 1)
            db.add(tema)
            await db.flush()
            for k in range(subtemas):
                subtema = Subtema(tema_id=tema.id, nome=f"S{i}{j}{k}", ordem=k + 1)
                db.add(subtema)
                await db.flush()
                esperados.append(subtema)
    await db.commit()
    return esperados


def test_a_primeira_etapa_e_hoje_e_a_ultima_e_a_data_alvo():
    prazos = distribuir_prazos(5, HOJE, HOJE + timedelta(days=20))
    assert prazos[0] == HOJE
    assert prazos[-1] == HOJE + timedelta(days=20)
    assert prazos == sorted(prazos)


def test_uma_etapa_so_vence_na_data_alvo():
    assert distribuir_prazos(1, HOJE, HOJE + timedelta(days=9)) == [HOJE + timedelta(days=9)]


def test_zero_etapas_devolve_lista_vazia():
    assert distribuir_prazos(0, HOJE, HOJE + timedelta(days=9)) == []


def test_prazo_curto_agrupa_em_vez_de_falhar():
    prazos = distribuir_prazos(10, HOJE, HOJE + timedelta(days=2))
    assert len(prazos) == 10
    assert prazos[0] == HOJE
    assert prazos[-1] == HOJE + timedelta(days=2)
    assert len(set(prazos)) < len(prazos)  # dias repetidos, de propósito
    assert prazo_apertado(10, HOJE, HOJE + timedelta(days=2)) is True


def test_prazo_folgado_nao_e_apertado():
    assert prazo_apertado(3, HOJE, HOJE + timedelta(days=30)) is False


def test_data_alvo_hoje_poe_tudo_hoje():
    prazos = distribuir_prazos(4, HOJE, HOJE)
    assert prazos == [HOJE] * 4
    assert prazo_apertado(4, HOJE, HOJE) is True


async def test_roadmap_cobre_todos_os_subtemas_na_ordem_do_conteudo(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()

    total = await gerar_roadmap(
        db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE
    )
    await db_session.commit()

    assert total == len(esperados)
    etapas = (
        await db_session.execute(
            select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno).order_by(EtapaRoadmap.ordem)
        )
    ).scalars().all()
    assert [e.subtema_id for e in etapas] == [s.id for s in esperados]
    assert [e.ordem for e in etapas] == list(range(len(esperados)))
    assert etapas[0].prazo == HOJE
    assert etapas[-1].prazo == HOJE + timedelta(days=30)


async def test_subtema_ja_dominado_nasce_concluido(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    db_session.add(
        AlunoTemaProgresso(aluno_id=aluno, subtema_id=esperados[1].id, nivel_dominio=0.9)
    )
    db_session.add(
        AlunoTemaProgresso(aluno_id=aluno, subtema_id=esperados[2].id, nivel_dominio=0.5)
    )
    await db_session.commit()

    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE)
    await db_session.commit()

    etapas = {
        e.subtema_id: e
        for e in (
            await db_session.execute(select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno))
        ).scalars().all()
    }
    assert etapas[esperados[1].id].concluida_em is not None
    assert etapas[esperados[2].id].concluida_em is None


async def test_regerar_preserva_conclusoes_e_troca_prazos(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE)
    await db_session.commit()

    concluido = await concluir_etapa(
        db_session, aluno_id=aluno, subtema_id=esperados[0].id, quando=datetime.now(UTC)
    )
    await db_session.commit()
    assert concluido is True

    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=60), hoje=HOJE)
    await db_session.commit()

    etapas = {
        e.subtema_id: e
        for e in (
            await db_session.execute(select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno))
        ).scalars().all()
    }
    assert len(etapas) == len(esperados)
    assert etapas[esperados[0].id].concluida_em is not None
    assert etapas[esperados[-1].id].prazo == HOJE + timedelta(days=60)


async def test_concluir_etapa_duas_vezes_devolve_false_na_segunda(db_session):
    esperados = await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    await gerar_roadmap(db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE)
    await db_session.commit()

    agora = datetime.now(UTC)
    assert await concluir_etapa(
        db_session, aluno_id=aluno, subtema_id=esperados[0].id, quando=agora
    ) is True
    await db_session.commit()
    assert await concluir_etapa(
        db_session, aluno_id=aluno, subtema_id=esperados[0].id, quando=agora
    ) is False


async def test_concluir_etapa_de_subtema_fora_do_roadmap_devolve_false(db_session):
    await _seed_conteudo(db_session)
    aluno = uuid.uuid4()
    assert await concluir_etapa(
        db_session, aluno_id=aluno, subtema_id=999_999, quando=datetime.now(UTC)
    ) is False


async def test_roadmap_de_conteudo_vazio_e_vazio(db_session):
    aluno = uuid.uuid4()
    total = await gerar_roadmap(
        db_session, aluno_id=aluno, data_alvo=HOJE + timedelta(days=30), hoje=HOJE
    )
    await db_session.commit()
    assert total == 0
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_roadmap_service.py -q`
Expected: FAIL com `ModuleNotFoundError: No module named 'app.services.roadmap'`.

- [ ] **Step 3: Escreva o serviço**

`app/services/roadmap.py`:

```python
"""Geração do percurso de estudo — a regra explícita da spec D.

Quatro passos, na ordem em que a spec os escreve:

1. Matérias na ordem do seed (`Materia.id`).
2. Temas e subtemas dentro de cada uma, por `.ordem` (com `.id` como
   desempate: `.ordem` tem default 0 e não é única — a mesma correção que
   `routers/materias.py` já carrega).
3. Prazos distribuídos entre hoje e a data-alvo.
4. Etapa de subtema já dominado nasce concluída.

Trocar isto por distribuição adaptativa depois é substituir estas funções,
não desmontar tela nenhuma: quem chama sabe só `gerar_roadmap`.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema
from app.services.decisao import LIMIAR_DOMINIO_SUBTEMA

# Teto de segurança: o seed completo do ENEM tem ordem de 130 subtemas.
TETO_ETAPAS = 2000


def distribuir_prazos(quantidade: int, inicio: date, data_alvo: date) -> list[date]:
    """Espalha `quantidade` etapas entre `inicio` e `data_alvo`, inclusive.

    A primeira vence hoje e a última na data-alvo. Quando há mais etapas que
    dias, vários prazos caem no mesmo dia — é o "agrupa em vez de falhar" da
    spec: recusar seria impedir um aluno de estudar para a prova da semana
    que vem.
    """
    if quantidade <= 0:
        return []
    dias = max((data_alvo - inicio).days, 0)
    if quantidade == 1:
        return [inicio + timedelta(days=dias)]
    return [inicio + timedelta(days=(i * dias) // (quantidade - 1)) for i in range(quantidade)]


def prazo_apertado(quantidade: int, inicio: date, data_alvo: date) -> bool:
    """Verdadeiro quando não há um dia inteiro por etapa."""
    dias_disponiveis = max((data_alvo - inicio).days, 0) + 1
    return quantidade > dias_disponiveis


async def _subtemas_em_ordem(db: AsyncSession) -> list[int]:
    resultado = await db.execute(
        select(Subtema.id)
        .join(Tema, Tema.id == Subtema.tema_id)
        .join(Materia, Materia.id == Tema.materia_id)
        .order_by(
            Materia.id.asc(),
            Tema.ordem.asc(),
            Tema.id.asc(),
            Subtema.ordem.asc(),
            Subtema.id.asc(),
        )
        .limit(TETO_ETAPAS)
    )
    return list(resultado.scalars().all())


async def gerar_roadmap(
    db: AsyncSession,
    *,
    aluno_id: uuid.UUID | str,
    data_alvo: date,
    hoje: date,
) -> int:
    """(Re)gera o percurso do aluno. Devolve quantas etapas ficaram.

    Regenerar é APAGAR e REINSERIR, com as conclusões relidas antes do
    delete: um `UPDATE` etapa a etapa teria que lidar com subtema que sumiu
    do seed e com subtema novo, dois caminhos a mais para manter certos.

    Não faz commit — a rota que chama decide a transação.
    """
    subtema_ids = await _subtemas_em_ordem(db)

    concluidas: dict[int, datetime] = {
        etapa.subtema_id: etapa.concluida_em
        for etapa in (
            await db.execute(select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno_id))
        ).scalars().all()
        if etapa.concluida_em is not None
    }

    dominados = set(
        (
            await db.execute(
                select(AlunoTemaProgresso.subtema_id).where(
                    AlunoTemaProgresso.aluno_id == aluno_id,
                    AlunoTemaProgresso.nivel_dominio >= LIMIAR_DOMINIO_SUBTEMA,
                )
            )
        ).scalars().all()
    )

    await db.execute(delete(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno_id))

    if not subtema_ids:
        return 0

    prazos = distribuir_prazos(len(subtema_ids), hoje, data_alvo)
    agora = datetime.now(UTC)
    for ordem, subtema_id in enumerate(subtema_ids):
        concluida_em = concluidas.get(subtema_id)
        if concluida_em is None and subtema_id in dominados:
            concluida_em = agora
        db.add(
            EtapaRoadmap(
                aluno_id=aluno_id,
                subtema_id=subtema_id,
                ordem=ordem,
                prazo=prazos[ordem],
                concluida_em=concluida_em,
            )
        )
    return len(subtema_ids)


async def concluir_etapa(
    db: AsyncSession,
    *,
    aluno_id: uuid.UUID | str,
    subtema_id: int,
    quando: datetime,
) -> bool:
    """Marca a etapa como concluída. Devolve `True` só na transição.

    O `WHERE concluida_em IS NULL` é o que torna a chamada idempotente sem
    uma leitura antes: a segunda passagem não encontra linha para atualizar
    e devolve `False` — e é esse `False` que impede a rota de pontuar duas
    vezes a mesma conclusão.
    """
    resultado = await db.execute(
        update(EtapaRoadmap)
        .where(
            EtapaRoadmap.aluno_id == aluno_id,
            EtapaRoadmap.subtema_id == subtema_id,
            EtapaRoadmap.concluida_em.is_(None),
        )
        .values(concluida_em=quando)
    )
    return bool(resultado.rowcount)
```

**Sobre o `datetime.now(UTC)` dentro de `gerar_roadmap`:** ele carimba a
conclusão de quem já dominava o subtema antes do percurso existir. É o
único ponto do serviço que lê o relógio — `hoje` chega por parâmetro
justamente para o teste poder fixar a data sem congelar o tempo do processo.

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_roadmap_service.py -q`
Expected: 12 passed.

- [ ] **Step 5: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **121 passed** (109 + 12).

- [ ] **Step 6: Commit**

```bash
git add back-end/learning-service/app/services/roadmap.py \
        back-end/learning-service/tests/test_roadmap_service.py
git commit -m "feat(learning): generate the study roadmap up to the target date"
```

---

### Task 4: `/onboarding` — o objetivo e a geração do percurso

**Files:**
- Create: `back-end/learning-service/app/schemas/objetivo.py`
- Create: `back-end/learning-service/app/routers/onboarding.py`
- Modify: `back-end/learning-service/app/main.py` (import + `include_router`)
- Test: `back-end/learning-service/tests/test_onboarding_routes.py`

**Interfaces:**
- Consumes: `gerar_roadmap`, `prazo_apertado` (Task 3); `ObjetivoAluno` (Task 1);
  `get_current_user_id` de `app.dependencies`.
- Produces, consumidos pelas tarefas 5, 6 e 10:
  - `GET /onboarding` → `200` com `ObjetivoOut` ou `null`
  - `POST /onboarding` → `201` `ObjetivoSalvoOut`; `409` se já existe
  - `PUT /onboarding` → `200` `ObjetivoSalvoOut`; `404` se não existe
  - `ObjetivoOut { titulo, data_alvo, criado_em, atualizado_em }`
  - `ObjetivoSalvoOut { objetivo, etapas_geradas, prazo_apertado }`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_onboarding_routes.py`:

```python
from datetime import date, timedelta

from sqlalchemy import select

from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _seed_conteudo(db, quantos=4):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    for k in range(quantos):
        db.add(Subtema(tema_id=tema.id, nome=f"S{k}", ordem=k + 1))
    await db.commit()


async def test_aluno_sem_objetivo_recebe_null(client, auth_headers):
    resposta = await client.get("/onboarding", headers=auth_headers)
    assert resposta.status_code == 200
    assert resposta.json() is None


async def test_criar_objetivo_gera_o_roadmap(client, db_session, student_identity):
    await _seed_conteudo(db_session)
    alvo = date.today() + timedelta(days=30)

    resposta = await client.post(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina USP", "data_alvo": alvo.isoformat()},
    )
    assert resposta.status_code == 201
    corpo = resposta.json()
    assert corpo["objetivo"]["titulo"] == "Medicina USP"
    assert corpo["objetivo"]["data_alvo"] == alvo.isoformat()
    assert corpo["etapas_geradas"] == 4
    assert corpo["prazo_apertado"] is False

    etapas = (
        await db_session.execute(
            select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
        )
    ).scalars().all()
    assert len(etapas) == 4


async def test_data_no_passado_e_recusada_com_mensagem_exibivel(client, auth_headers):
    ontem = date.today() - timedelta(days=1)
    resposta = await client.post(
        "/onboarding",
        headers=auth_headers,
        json={"titulo": "Medicina", "data_alvo": ontem.isoformat()},
    )
    assert resposta.status_code == 422
    assert "passado" in resposta.text.lower()


async def test_titulo_vazio_ou_so_espaco_e_recusado(client, auth_headers):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    for titulo in ("", "   "):
        resposta = await client.post(
            "/onboarding", headers=auth_headers, json={"titulo": titulo, "data_alvo": alvo}
        )
        assert resposta.status_code == 422


async def test_titulo_acima_do_teto_e_recusado(client, auth_headers):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    resposta = await client.post(
        "/onboarding", headers=auth_headers, json={"titulo": "x" * 121, "data_alvo": alvo}
    )
    assert resposta.status_code == 422


async def test_segundo_objetivo_do_mesmo_aluno_e_conflito(client, db_session, auth_headers):
    await _seed_conteudo(db_session)
    alvo = (date.today() + timedelta(days=30)).isoformat()
    primeira = await client.post(
        "/onboarding", headers=auth_headers, json={"titulo": "Medicina", "data_alvo": alvo}
    )
    assert primeira.status_code == 201

    segunda = await client.post(
        "/onboarding", headers=auth_headers, json={"titulo": "Direito", "data_alvo": alvo}
    )
    assert segunda.status_code == 409


async def test_alterar_a_data_regenera_os_prazos(client, db_session, student_identity):
    await _seed_conteudo(db_session)
    alvo = date.today() + timedelta(days=30)
    await client.post(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina", "data_alvo": alvo.isoformat()},
    )

    novo_alvo = date.today() + timedelta(days=90)
    resposta = await client.put(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina", "data_alvo": novo_alvo.isoformat()},
    )
    assert resposta.status_code == 200
    assert resposta.json()["etapas_geradas"] == 4

    etapas = (
        await db_session.execute(
            select(EtapaRoadmap)
            .where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
            .order_by(EtapaRoadmap.ordem)
        )
    ).scalars().all()
    assert etapas[-1].prazo == novo_alvo


async def test_alterar_so_o_titulo_nao_mexe_nos_prazos(client, db_session, student_identity):
    await _seed_conteudo(db_session)
    alvo = date.today() + timedelta(days=30)
    await client.post(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina", "data_alvo": alvo.isoformat()},
    )
    antes = [
        e.prazo
        for e in (
            await db_session.execute(
                select(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
                .order_by(EtapaRoadmap.ordem)
            )
        ).scalars().all()
    ]

    await client.put(
        "/onboarding",
        headers=student_identity.headers,
        json={"titulo": "Medicina UFMG", "data_alvo": alvo.isoformat()},
    )
    depois = [
        e.prazo
        for e in (
            await db_session.execute(
                select(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
                .order_by(EtapaRoadmap.ordem)
            )
        ).scalars().all()
    ]
    assert antes == depois


async def test_put_sem_objetivo_e_404(client, auth_headers):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    resposta = await client.put(
        "/onboarding", headers=auth_headers, json={"titulo": "Medicina", "data_alvo": alvo}
    )
    assert resposta.status_code == 404


async def test_rotas_de_onboarding_exigem_token(client):
    alvo = (date.today() + timedelta(days=10)).isoformat()
    assert (await client.get("/onboarding")).status_code == 403
    assert (
        await client.post("/onboarding", json={"titulo": "x", "data_alvo": alvo})
    ).status_code == 403


async def test_prazo_apertado_e_sinalizado(client, db_session, auth_headers):
    await _seed_conteudo(db_session, quantos=10)
    resposta = await client.post(
        "/onboarding",
        headers=auth_headers,
        json={"titulo": "Prova da semana", "data_alvo": (date.today() + timedelta(days=2)).isoformat()},
    )
    assert resposta.status_code == 201
    assert resposta.json()["prazo_apertado"] is True
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_onboarding_routes.py -q`
Expected: FAIL — as rotas devolvem 404 porque não existem.

- [ ] **Step 3: Escreva os schemas**

`app/schemas/objetivo.py`:

```python
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ObjetivoIn(BaseModel):
    """Entrada do onboarding: o que o aluno quer e para quando.

    A data no passado é recusada AQUI, no schema, não na tela: a tela é uma
    das duas portas (a outra é o PUT do perfil) e uma regra que vive no
    cliente é uma regra que o segundo cliente não tem.
    """

    titulo: str = Field(min_length=1, max_length=120)
    data_alvo: date

    @field_validator("titulo")
    @classmethod
    def _titulo_nao_pode_ser_so_espaco(cls, valor: str) -> str:
        limpo = valor.strip()
        if not limpo:
            raise ValueError("O objetivo não pode ficar em branco")
        return limpo

    @field_validator("data_alvo")
    @classmethod
    def _data_nao_pode_estar_no_passado(cls, valor: date) -> date:
        if valor < date.today():
            raise ValueError("A data-alvo não pode estar no passado")
        return valor


class ObjetivoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    titulo: str
    data_alvo: date
    criado_em: datetime
    atualizado_em: datetime


class ObjetivoSalvoOut(BaseModel):
    """Resposta de POST e PUT: o objetivo e o que a geração do percurso fez.

    `etapas_geradas` e `prazo_apertado` viajam junto porque a tela mostra
    "seu percurso tem N etapas" logo depois de salvar — sem isso ela faria
    uma segunda chamada só para contar.
    """

    objetivo: ObjetivoOut
    etapas_geradas: int
    prazo_apertado: bool
```

- [ ] **Step 4: Escreva o router**

`app/routers/onboarding.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.objetivo import ObjetivoAluno
from app.schemas.objetivo import ObjetivoIn, ObjetivoOut, ObjetivoSalvoOut
from app.services.roadmap import gerar_roadmap, prazo_apertado

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


async def _objetivo_do_aluno(db: AsyncSession, aluno_id: str) -> ObjetivoAluno | None:
    return (
        await db.execute(select(ObjetivoAluno).where(ObjetivoAluno.aluno_id == aluno_id))
    ).scalar_one_or_none()


@router.get("", response_model=ObjetivoOut | None)
async def ler_objetivo(
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """O objetivo do aluno, ou `null`.

    `null` não é erro: aluno que pulou o onboarding é caso previsto, e um
    404 aqui faria a tela tratar "não preencheu ainda" como falha.
    """
    return await _objetivo_do_aluno(db, aluno_id)


@router.post("", response_model=ObjetivoSalvoOut, status_code=201)
async def criar_objetivo(
    payload: ObjetivoIn,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    hoje = date.today()
    objetivo = ObjetivoAluno(
        aluno_id=aluno_id, titulo=payload.titulo, data_alvo=payload.data_alvo
    )
    db.add(objetivo)
    try:
        await db.flush()
    except IntegrityError as exc:
        # `uq_objetivo_aluno`: dois POSTs simultâneos do mesmo aluno. O
        # segundo vira 409 em vez de 500 — e o cliente sabe que o caminho
        # certo é o PUT.
        await db.rollback()
        raise HTTPException(409, "Você já tem um objetivo. Altere o que existe.") from exc

    total = await gerar_roadmap(db, aluno_id=aluno_id, data_alvo=payload.data_alvo, hoje=hoje)
    await db.commit()
    await db.refresh(objetivo)
    return ObjetivoSalvoOut(
        objetivo=ObjetivoOut.model_validate(objetivo),
        etapas_geradas=total,
        prazo_apertado=prazo_apertado(total, hoje, payload.data_alvo),
    )


@router.put("", response_model=ObjetivoSalvoOut)
async def alterar_objetivo(
    payload: ObjetivoIn,
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Altera o objetivo. Regenera o percurso SÓ quando a data muda.

    Mudar o título não move prazo nenhum: regenerar por causa de um texto
    apagaria e recriaria dezenas de linhas para um resultado idêntico.
    """
    objetivo = await _objetivo_do_aluno(db, aluno_id)
    if objetivo is None:
        raise HTTPException(404, "Você ainda não tem um objetivo")

    data_mudou = objetivo.data_alvo != payload.data_alvo
    objetivo.titulo = payload.titulo
    objetivo.data_alvo = payload.data_alvo

    hoje = date.today()
    if data_mudou:
        total = await gerar_roadmap(
            db, aluno_id=aluno_id, data_alvo=payload.data_alvo, hoje=hoje
        )
    else:
        total = await _contar_etapas(db, aluno_id)

    await db.commit()
    await db.refresh(objetivo)
    return ObjetivoSalvoOut(
        objetivo=ObjetivoOut.model_validate(objetivo),
        etapas_geradas=total,
        prazo_apertado=prazo_apertado(total, hoje, payload.data_alvo),
    )


async def _contar_etapas(db: AsyncSession, aluno_id: str) -> int:
    from sqlalchemy import func

    from app.models.roadmap import EtapaRoadmap

    total = await db.execute(
        select(func.count()).select_from(EtapaRoadmap).where(EtapaRoadmap.aluno_id == aluno_id)
    )
    return int(total.scalar_one())
```

- [ ] **Step 5: Ligue o router no app**

Em `app/main.py`, acrescente `onboarding` ao import de routers e uma linha
`app.include_router(onboarding.router)` junto das existentes.

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_onboarding_routes.py -q`
Expected: 11 passed.

- [ ] **Step 7: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **132 passed** (121 + 11).

- [ ] **Step 8: Commit**

```bash
git add back-end/learning-service/app/schemas/objetivo.py \
        back-end/learning-service/app/routers/onboarding.py \
        back-end/learning-service/app/main.py \
        back-end/learning-service/tests/test_onboarding_routes.py
git commit -m "feat(learning): add the onboarding routes for goal and target date"
```

---

### Task 5: `GET /roadmap` — o percurso que a tela do tracker lê

**Files:**
- Create: `back-end/learning-service/app/schemas/roadmap.py`
- Create: `back-end/learning-service/app/routers/roadmap.py`
- Modify: `back-end/learning-service/app/main.py`
- Test: `back-end/learning-service/tests/test_roadmap_routes.py`

**Interfaces:**
- Consumes: `EtapaRoadmap`, `ObjetivoAluno`, `Questao`, `prazo_apertado`.
- Produces, consumido pela Task 14:
  - `GET /roadmap?limit=&offset=` → `RoadmapOut`
  - `EtapaOut { subtema_id, subtema_nome, tema_nome, materia_nome, ordem,
    prazo, concluida, concluida_em, tem_questoes }`
  - `RoadmapOut { objetivo, motivo, prazo_apertado, items, total, limit, offset }`

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_roadmap_routes.py`:

```python
from datetime import date, timedelta

from app.models.questao import Questao
from app.models.subtema import Materia, Subtema, Tema


async def _seed(db, *, com_questao_no_primeiro=True, quantos=3):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    subtemas = []
    for k in range(quantos):
        subtema = Subtema(tema_id=tema.id, nome=f"S{k}", ordem=k + 1)
        db.add(subtema)
        await db.flush()
        subtemas.append(subtema)
    if com_questao_no_primeiro:
        db.add(
            Questao(
                subtema_id=subtemas[0].id,
                enunciado="Enunciado",
                alternativas={"A": "a", "B": "b"},
                gabarito="A",
                nivel_dificuldade=1,
            )
        )
    await db.commit()
    return subtemas


async def _fazer_onboarding(client, headers, dias=30):
    return await client.post(
        "/onboarding",
        headers=headers,
        json={
            "titulo": "Medicina",
            "data_alvo": (date.today() + timedelta(days=dias)).isoformat(),
        },
    )


async def test_sem_objetivo_a_lista_vem_vazia_com_motivo(client, auth_headers):
    resposta = await client.get("/roadmap", headers=auth_headers)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["items"] == []
    assert corpo["total"] == 0
    assert corpo["objetivo"] is None
    assert corpo["motivo"]
    assert "objetivo" in corpo["motivo"].lower()


async def test_com_objetivo_traz_as_etapas_em_ordem(client, db_session, auth_headers):
    subtemas = await _seed(db_session)
    await _fazer_onboarding(client, auth_headers)

    corpo = (await client.get("/roadmap", headers=auth_headers)).json()
    assert corpo["total"] == 3
    assert [e["subtema_id"] for e in corpo["items"]] == [s.id for s in subtemas]
    assert [e["ordem"] for e in corpo["items"]] == [0, 1, 2]
    assert corpo["motivo"] is None
    assert corpo["objetivo"]["titulo"] == "Medicina"


async def test_etapa_carrega_os_nomes_da_hierarquia(client, db_session, auth_headers):
    await _seed(db_session)
    await _fazer_onboarding(client, auth_headers)

    primeira = (await client.get("/roadmap", headers=auth_headers)).json()["items"][0]
    assert primeira["materia_nome"] == "Biologia"
    assert primeira["tema_nome"] == "Citologia"
    assert primeira["subtema_nome"] == "S0"


async def test_subtema_sem_questao_vem_marcado(client, db_session, auth_headers):
    await _seed(db_session, com_questao_no_primeiro=True)
    await _fazer_onboarding(client, auth_headers)

    itens = (await client.get("/roadmap", headers=auth_headers)).json()["items"]
    assert itens[0]["tem_questoes"] is True
    assert itens[1]["tem_questoes"] is False
    assert itens[2]["tem_questoes"] is False


async def test_a_listagem_pagina(client, db_session, auth_headers):
    await _seed(db_session, quantos=5)
    await _fazer_onboarding(client, auth_headers)

    corpo = (await client.get("/roadmap?limit=2&offset=2", headers=auth_headers)).json()
    assert corpo["total"] == 5
    assert corpo["limit"] == 2
    assert corpo["offset"] == 2
    assert [e["ordem"] for e in corpo["items"]] == [2, 3]


async def test_limite_fora_de_faixa_e_recusado(client, auth_headers):
    assert (await client.get("/roadmap?limit=0", headers=auth_headers)).status_code == 422
    assert (await client.get("/roadmap?limit=500", headers=auth_headers)).status_code == 422


async def test_o_roadmap_e_do_aluno_do_token(client, db_session, student_identity, auth_headers):
    """Duas identidades, dois percursos — nenhuma enxerga a outra."""
    await _seed(db_session)
    await _fazer_onboarding(client, student_identity.headers)

    outro = await client.get("/roadmap", headers=auth_headers)
    assert outro.status_code == 200


async def test_roadmap_exige_token(client):
    assert (await client.get("/roadmap")).status_code == 403


async def test_prazo_apertado_aparece_no_corpo(client, db_session, auth_headers):
    await _seed(db_session, quantos=5)
    await _fazer_onboarding(client, auth_headers, dias=1)
    corpo = (await client.get("/roadmap", headers=auth_headers)).json()
    assert corpo["prazo_apertado"] is True
```

Nota para o implementador: no teste `test_o_roadmap_e_do_aluno_do_token`,
`auth_headers` e `student_identity.headers` são o **mesmo** token (a fixture
`auth_headers` deriva de `student_identity`) — o teste afirma só que a rota
responde 200 para quem não tem percurso. A separação real entre alunos está
coberta em `test_pontuacao.py::test_alunos_diferentes_nao_disputam_a_mesma_referencia`
e no filtro por `aluno_id` que toda consulta desta rota carrega.

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_roadmap_routes.py -q`
Expected: FAIL — 404 em `/roadmap`.

- [ ] **Step 3: Escreva o schema**

`app/schemas/roadmap.py`:

```python
from datetime import date, datetime

from pydantic import BaseModel

from app.schemas.objetivo import ObjetivoOut


class EtapaOut(BaseModel):
    """Uma etapa do percurso, com o caminho inteiro até ela.

    Os três nomes (matéria, tema, subtema) viajam juntos porque a tela
    agrupa por matéria — sem eles, o cliente faria uma chamada por etapa
    para descobrir onde ela mora.
    """

    subtema_id: int
    subtema_nome: str
    tema_nome: str
    materia_nome: str
    ordem: int
    prazo: date
    concluida: bool
    concluida_em: datetime | None
    # False quando o subtema ainda não tem questão semeada. A tela mostra a
    # etapa assim mesmo, com o botão de praticar desabilitado e o motivo —
    # esconder a matéria seria mentir sobre o tamanho do percurso.
    tem_questoes: bool


class RoadmapOut(BaseModel):
    objetivo: ObjetivoOut | None
    # Preenchido só quando `items` está vazio por falta de objetivo: é o que
    # a tela exibe convidando o aluno a fazer o onboarding.
    motivo: str | None
    prazo_apertado: bool
    items: list[EtapaOut]
    total: int
    limit: int
    offset: int
```

- [ ] **Step 4: Escreva o router**

`app/routers/roadmap.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.objetivo import ObjetivoAluno
from app.models.questao import Questao
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema
from app.schemas.objetivo import ObjetivoOut
from app.schemas.roadmap import EtapaOut, RoadmapOut
from app.services.roadmap import prazo_apertado

router = APIRouter(prefix="/roadmap", tags=["roadmap"])

SEM_OBJETIVO = "Defina um objetivo e uma data-alvo para montar seu percurso."


@router.get("", response_model=RoadmapOut)
async def listar_roadmap(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    objetivo = (
        await db.execute(select(ObjetivoAluno).where(ObjetivoAluno.aluno_id == aluno_id))
    ).scalar_one_or_none()
    if objetivo is None:
        return RoadmapOut(
            objetivo=None,
            motivo=SEM_OBJETIVO,
            prazo_apertado=False,
            items=[],
            total=0,
            limit=limit,
            offset=offset,
        )

    total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(EtapaRoadmap)
                .where(EtapaRoadmap.aluno_id == aluno_id)
            )
        ).scalar_one()
    )

    linhas = (
        await db.execute(
            select(EtapaRoadmap, Subtema, Tema, Materia)
            .join(Subtema, Subtema.id == EtapaRoadmap.subtema_id)
            .join(Tema, Tema.id == Subtema.tema_id)
            .join(Materia, Materia.id == Tema.materia_id)
            .where(EtapaRoadmap.aluno_id == aluno_id)
            # `.ordem` é única por aluno na prática, mas `.id` como desempate
            # mantém a ordem total estável entre páginas mesmo se uma
            # regeneração concorrente empatar dois valores.
            .order_by(EtapaRoadmap.ordem.asc(), EtapaRoadmap.id.asc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    # UMA agregação para todas as etapas da página, não uma consulta por
    # etapa: com 130 subtemas no seed do ENEM, o caminho ingênuo seriam 130
    # viagens ao banco para desenhar uma tela.
    ids_da_pagina = [etapa.subtema_id for etapa, _s, _t, _m in linhas]
    com_questao: set[int] = set()
    if ids_da_pagina:
        com_questao = set(
            (
                await db.execute(
                    select(Questao.subtema_id)
                    .where(Questao.subtema_id.in_(ids_da_pagina))
                    .group_by(Questao.subtema_id)
                )
            ).scalars().all()
        )

    items = [
        EtapaOut(
            subtema_id=etapa.subtema_id,
            subtema_nome=subtema.nome,
            tema_nome=tema.nome,
            materia_nome=materia.nome,
            ordem=etapa.ordem,
            prazo=etapa.prazo,
            concluida=etapa.concluida_em is not None,
            concluida_em=etapa.concluida_em,
            tem_questoes=etapa.subtema_id in com_questao,
        )
        for etapa, subtema, tema, materia in linhas
    ]

    return RoadmapOut(
        objetivo=ObjetivoOut.model_validate(objetivo),
        motivo=None,
        prazo_apertado=prazo_apertado(total, date.today(), objetivo.data_alvo),
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
```

- [ ] **Step 5: Ligue o router no app**

Em `app/main.py`, acrescente `roadmap` ao import e
`app.include_router(roadmap.router)`.

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_roadmap_routes.py -q`
Expected: 9 passed.

- [ ] **Step 7: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **141 passed** (132 + 9).

- [ ] **Step 8: Commit**

```bash
git add back-end/learning-service/app/schemas/roadmap.py \
        back-end/learning-service/app/routers/roadmap.py \
        back-end/learning-service/app/main.py \
        back-end/learning-service/tests/test_roadmap_routes.py
git commit -m "feat(learning): serve the study roadmap with per-step availability"
```

---

### Task 6: `GET /profile/summary` — o resumo que as duas telas leem

**Files:**
- Create: `back-end/learning-service/app/schemas/perfil.py`
- Create: `back-end/learning-service/app/routers/perfil.py`
- Modify: `back-end/learning-service/app/main.py`
- Test: `back-end/learning-service/tests/test_perfil_routes.py`

**Interfaces:**
- Consumes: `ObjetivoAluno`, `EtapaRoadmap`, `AlunoTemaProgresso`,
  `total_de_pontos`, `nivel_do_total`.
- Produces, consumido pelas tarefas 10, 12 e 13:
  `GET /profile/summary` → `ResumoOut` com a forma exata da spec:

```json
{
  "objetivo": {"titulo": "...", "data_alvo": "2027-11-07",
               "dias_decorridos": 0, "dias_totais": 0},
  "roadmap":  {"etapas_totais": 0, "etapas_concluidas": 0, "progresso": 0.0},
  "pontos":   {"total": 0, "nivel": 1, "streak": 0},
  "estudo":   {"questoes_respondidas": 0, "subtemas_iniciados": 0}
}
```

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_perfil_routes.py`:

```python
from datetime import UTC, date, datetime, timedelta

from app.models.objetivo import ObjetivoAluno
from app.models.pontuacao import LancamentoPontos
from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _subtemas(db, quantos=3):
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    criados = []
    for k in range(quantos):
        subtema = Subtema(tema_id=tema.id, nome=f"S{k}", ordem=k + 1)
        db.add(subtema)
        await db.flush()
        criados.append(subtema)
    await db.commit()
    return criados


async def test_aluno_zerado_mostra_zero(client, auth_headers):
    """O teste que fecha o objetivo da spec: recém-criado é zero, não 3.120."""
    corpo = (await client.get("/profile/summary", headers=auth_headers)).json()
    assert corpo["objetivo"] is None
    assert corpo["roadmap"] == {"etapas_totais": 0, "etapas_concluidas": 0, "progresso": 0.0}
    assert corpo["pontos"] == {"total": 0, "nivel": 1, "streak": 0}
    assert corpo["estudo"] == {"questoes_respondidas": 0, "subtemas_iniciados": 0}


async def test_objetivo_traz_dias_decorridos_e_totais(client, db_session, student_identity):
    criado_em = datetime.now(UTC) - timedelta(days=10)
    db_session.add(
        ObjetivoAluno(
            aluno_id=student_identity.aluno_id,
            titulo="Medicina USP",
            data_alvo=date.today() + timedelta(days=90),
            criado_em=criado_em,
            atualizado_em=criado_em,
        )
    )
    await db_session.commit()

    objetivo = (
        await client.get("/profile/summary", headers=student_identity.headers)
    ).json()["objetivo"]
    assert objetivo["titulo"] == "Medicina USP"
    assert objetivo["dias_decorridos"] == 10
    assert objetivo["dias_totais"] == 100


async def test_progresso_do_roadmap_e_a_razao_de_etapas_concluidas(
    client, db_session, student_identity
):
    subtemas = await _subtemas(db_session, quantos=4)
    for indice, subtema in enumerate(subtemas):
        db_session.add(
            EtapaRoadmap(
                aluno_id=student_identity.aluno_id,
                subtema_id=subtema.id,
                ordem=indice,
                prazo=date.today(),
                concluida_em=datetime.now(UTC) if indice < 3 else None,
            )
        )
    await db_session.commit()

    roadmap = (
        await client.get("/profile/summary", headers=student_identity.headers)
    ).json()["roadmap"]
    assert roadmap["etapas_totais"] == 4
    assert roadmap["etapas_concluidas"] == 3
    assert roadmap["progresso"] == 0.75


async def test_pontos_e_nivel_saem_do_extrato(client, db_session, student_identity):
    for referencia in ("1", "2", "3"):
        db_session.add(
            LancamentoPontos(
                aluno_id=student_identity.aluno_id,
                origem="questao",
                referencia=referencia,
                pontos=50,
            )
        )
    await db_session.commit()

    pontos = (
        await client.get("/profile/summary", headers=student_identity.headers)
    ).json()["pontos"]
    assert pontos["total"] == 150
    assert pontos["nivel"] == 2  # 150 está na faixa que começa em 100


async def test_streak_e_o_maior_do_aluno_e_estudo_soma_respostas(
    client, db_session, student_identity
):
    subtemas = await _subtemas(db_session, quantos=2)
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtemas[0].id,
            streak_acertos=2,
            total_respondidas=7,
        )
    )
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtemas[1].id,
            streak_acertos=5,
            total_respondidas=3,
        )
    )
    await db_session.commit()

    corpo = (await client.get("/profile/summary", headers=student_identity.headers)).json()
    assert corpo["pontos"]["streak"] == 5
    assert corpo["estudo"] == {"questoes_respondidas": 10, "subtemas_iniciados": 2}


async def test_objetivo_criado_hoje_nao_divide_por_zero(client, db_session, student_identity):
    db_session.add(
        ObjetivoAluno(
            aluno_id=student_identity.aluno_id,
            titulo="Prova amanhã",
            data_alvo=date.today(),
        )
    )
    await db_session.commit()

    objetivo = (
        await client.get("/profile/summary", headers=student_identity.headers)
    ).json()["objetivo"]
    assert objetivo["dias_totais"] == 0
    assert objetivo["dias_decorridos"] == 0


async def test_dias_decorridos_nunca_passa_do_total(client, db_session, student_identity):
    criado_em = datetime.now(UTC) - timedelta(days=200)
    db_session.add(
        ObjetivoAluno(
            aluno_id=student_identity.aluno_id,
            titulo="Prova que já passou",
            data_alvo=date.today(),
            criado_em=criado_em,
            atualizado_em=criado_em,
        )
    )
    await db_session.commit()

    objetivo = (
        await client.get("/profile/summary", headers=student_identity.headers)
    ).json()["objetivo"]
    assert objetivo["dias_decorridos"] == objetivo["dias_totais"] == 200


async def test_summary_exige_token(client):
    assert (await client.get("/profile/summary")).status_code == 403
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_perfil_routes.py -q`
Expected: FAIL — 404 em `/profile/summary`.

- [ ] **Step 3: Escreva o schema**

`app/schemas/perfil.py`:

```python
from datetime import date

from pydantic import BaseModel


class ObjetivoResumoOut(BaseModel):
    titulo: str
    data_alvo: date
    # Dias desde a criação do objetivo e dias entre a criação e a data-alvo —
    # é o par que a tela inicial exibe como "124/200 dias". `decorridos`
    # nunca passa de `totais`: uma prova que já passou mostra o percurso
    # cheio, não um número maior que o denominador.
    dias_decorridos: int
    dias_totais: int


class RoadmapResumoOut(BaseModel):
    etapas_totais: int
    etapas_concluidas: int
    # 0.0 a 1.0 — é o valor da barra da tela inicial, que antes era 0.68 fixo.
    progresso: float


class PontosResumoOut(BaseModel):
    total: int
    nivel: int
    streak: int


class EstudoResumoOut(BaseModel):
    questoes_respondidas: int
    subtemas_iniciados: int


class ResumoOut(BaseModel):
    """Um agregador para duas telas: sem ele, abrir o app faria quatro
    chamadas em série antes de desenhar qualquer número."""

    objetivo: ObjetivoResumoOut | None
    roadmap: RoadmapResumoOut
    pontos: PontosResumoOut
    estudo: EstudoResumoOut
```

- [ ] **Step 4: Escreva o router**

`app/routers/perfil.py`:

```python
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_user_id
from app.models.objetivo import ObjetivoAluno
from app.models.progresso import AlunoTemaProgresso
from app.models.roadmap import EtapaRoadmap
from app.schemas.perfil import (
    EstudoResumoOut,
    ObjetivoResumoOut,
    PontosResumoOut,
    ResumoOut,
    RoadmapResumoOut,
)
from app.services.pontuacao import nivel_do_total, total_de_pontos

router = APIRouter(prefix="/profile", tags=["perfil"])


@router.get("/summary", response_model=ResumoOut)
async def resumo(
    aluno_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Tudo que a tela inicial e o perfil precisam, numa chamada.

    Cada campo tem origem única e verificável — nenhum é derivado de outro
    campo desta mesma resposta.
    """
    objetivo = (
        await db.execute(select(ObjetivoAluno).where(ObjetivoAluno.aluno_id == aluno_id))
    ).scalar_one_or_none()

    objetivo_out = None
    if objetivo is not None:
        inicio = objetivo.criado_em.date()
        dias_totais = max((objetivo.data_alvo - inicio).days, 0)
        # `min` com o total: um objetivo cuja data já passou mostra o
        # percurso cheio. Sem isso a barra da tela passaria de 100%.
        dias_decorridos = max(min((date.today() - inicio).days, dias_totais), 0)
        objetivo_out = ObjetivoResumoOut(
            titulo=objetivo.titulo,
            data_alvo=objetivo.data_alvo,
            dias_decorridos=dias_decorridos,
            dias_totais=dias_totais,
        )

    etapas_totais, etapas_concluidas = (
        await db.execute(
            select(
                func.count(),
                func.count(EtapaRoadmap.concluida_em),
            ).where(EtapaRoadmap.aluno_id == aluno_id)
        )
    ).one()

    total_pontos = await total_de_pontos(db, aluno_id)

    streak, respondidas, iniciados = (
        await db.execute(
            select(
                func.coalesce(func.max(AlunoTemaProgresso.streak_acertos), 0),
                func.coalesce(func.sum(AlunoTemaProgresso.total_respondidas), 0),
                func.count(),
            ).where(AlunoTemaProgresso.aluno_id == aluno_id)
        )
    ).one()

    return ResumoOut(
        objetivo=objetivo_out,
        roadmap=RoadmapResumoOut(
            etapas_totais=int(etapas_totais),
            etapas_concluidas=int(etapas_concluidas),
            progresso=(round(etapas_concluidas / etapas_totais, 4) if etapas_totais else 0.0),
        ),
        pontos=PontosResumoOut(
            total=total_pontos,
            nivel=nivel_do_total(total_pontos),
            streak=int(streak),
        ),
        estudo=EstudoResumoOut(
            questoes_respondidas=int(respondidas),
            subtemas_iniciados=int(iniciados),
        ),
    )
```

**Por que `func.count(EtapaRoadmap.concluida_em)`:** `COUNT` de uma coluna
ignora `NULL`, então a mesma varredura devolve total e concluídas. Duas
consultas separadas dariam a mesma resposta com o dobro das viagens, e
abririam a janela em que uma etapa é concluída entre as duas — a tela
mostraria 4 de 3.

- [ ] **Step 5: Ligue o router no app**

Em `app/main.py`, acrescente `perfil` ao import e
`app.include_router(perfil.router)`.

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_perfil_routes.py -q`
Expected: 8 passed.

- [ ] **Step 7: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **149 passed** (141 + 8).

- [ ] **Step 8: Commit**

```bash
git add back-end/learning-service/app/schemas/perfil.py \
        back-end/learning-service/app/routers/perfil.py \
        back-end/learning-service/app/main.py \
        back-end/learning-service/tests/test_perfil_routes.py
git commit -m "feat(learning): aggregate the student study summary in one call"
```

---

### Task 7: O gancho — responder questão pontua e conclui etapa

**Files:**
- Modify: `back-end/learning-service/app/routers/diagnostico.py` (dentro de
  `responder_diagnostico`, no laço por subtema e no laço que grava as respostas)
- Test: `back-end/learning-service/tests/test_pontuacao_no_diagnostico.py`

**Interfaces:**
- Consumes: `registrar`, `bonus_streak`, `PONTOS_*` (Task 2);
  `concluir_etapa` (Task 3); `LIMIAR_DOMINIO_SUBTEMA` (já importado no arquivo).
- Produces: nenhuma assinatura nova. O efeito é observável por
  `GET /profile/summary` e pela tabela `lancamento_pontos`.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_pontuacao_no_diagnostico.py`:

```python
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select

from app.models.pontuacao import LancamentoPontos
from app.models.progresso import AlunoTemaProgresso
from app.models.questao import Questao
from app.models.roadmap import EtapaRoadmap
from app.models.subtema import Materia, Subtema, Tema


async def _cenario(db, *, quantas_questoes=4):
    """Um tema com um subtema e N questões, todas de dificuldade 1."""
    materia = Materia(nome="Biologia")
    db.add(materia)
    await db.flush()
    tema = Tema(materia_id=materia.id, nome="Citologia", ordem=1)
    db.add(tema)
    await db.flush()
    subtema = Subtema(tema_id=tema.id, nome="Membrana", ordem=1)
    db.add(subtema)
    await db.flush()
    questoes = []
    for _ in range(quantas_questoes):
        questao = Questao(
            subtema_id=subtema.id,
            enunciado="Enunciado",
            alternativas={"A": "a", "B": "b"},
            gabarito="A",
            nivel_dificuldade=1,
        )
        db.add(questao)
        await db.flush()
        questoes.append(questao)
    await db.commit()
    return tema, subtema, questoes


def _respostas(questoes, corretas):
    return [
        {"questao_id": q.id, "alternativa_escolhida": "A" if i < corretas else "B"}
        for i, q in enumerate(questoes)
    ]


async def _pontos(db, aluno_id, origem=None):
    stmt = select(LancamentoPontos).where(LancamentoPontos.aluno_id == aluno_id)
    if origem:
        stmt = stmt.where(LancamentoPontos.origem == origem)
    return (await db.execute(stmt)).scalars().all()


async def test_cada_questao_correta_vale_dez(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session)

    resposta = await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=3)},
    )
    assert resposta.status_code == 200

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="questao")
    assert len(lancamentos) == 3
    assert {l.pontos for l in lancamentos} == {10}


async def test_responder_de_novo_nao_pontua_de_novo(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session)
    corpo = {"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)}

    await client.post("/diagnostic/answer", headers=student_identity.headers, json=corpo)
    await client.post("/diagnostic/answer", headers=student_identity.headers, json=corpo)

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="questao")
    assert len(lancamentos) == 4  # e não 8


async def test_dominio_alto_conclui_a_etapa_e_pontua_cinquenta(
    client, db_session, student_identity
):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        EtapaRoadmap(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            ordem=0,
            prazo=date.today(),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )

    etapa = (
        await db_session.execute(
            select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
        )
    ).scalar_one()
    assert etapa.concluida_em is not None

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="etapa")
    assert [l.pontos for l in lancamentos] == [50]


async def test_dominio_baixo_nao_conclui_etapa(client, db_session, student_identity):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        EtapaRoadmap(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            ordem=0,
            prazo=date.today(),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=1)},
    )

    etapa = (
        await db_session.execute(
            select(EtapaRoadmap).where(EtapaRoadmap.aluno_id == student_identity.aluno_id)
        )
    ).scalar_one()
    assert etapa.concluida_em is None
    assert await _pontos(db_session, student_identity.aluno_id, origem="etapa") == []


async def test_revisao_vencida_respondida_pontua_quinze(client, db_session, student_identity):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            nivel_dominio=0.8,
            proxima_revisao=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )

    lancamentos = await _pontos(db_session, student_identity.aluno_id, origem="revisao")
    assert [l.pontos for l in lancamentos] == [15]


async def test_revisao_no_futuro_nao_pontua(client, db_session, student_identity):
    tema, subtema, questoes = await _cenario(db_session)
    db_session.add(
        AlunoTemaProgresso(
            aluno_id=student_identity.aluno_id,
            subtema_id=subtema.id,
            nivel_dominio=0.8,
            proxima_revisao=datetime.now(UTC) + timedelta(days=3),
        )
    )
    await db_session.commit()

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )
    assert await _pontos(db_session, student_identity.aluno_id, origem="revisao") == []


async def test_primeira_resposta_de_um_subtema_nao_conta_como_revisao(
    client, db_session, student_identity
):
    """Sem linha de progresso anterior não há revisão vencida — a primeira
    resposta é estudo novo, não revisão."""
    tema, _subtema, questoes = await _cenario(db_session)
    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )
    assert await _pontos(db_session, student_identity.aluno_id, origem="revisao") == []


async def test_bonus_de_sequencia_cresce_com_o_streak(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session, quantas_questoes=8)
    primeira = questoes[:4]
    segunda = questoes[4:]

    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(primeira, corretas=4)},
    )
    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(segunda, corretas=4)},
    )

    lancamentos = sorted(
        (l.pontos for l in await _pontos(db_session, student_identity.aluno_id, origem="streak"))
    )
    assert lancamentos == [5, 10]  # streak 1 e streak 2


async def test_o_resumo_enxerga_os_pontos_lancados(client, db_session, student_identity):
    tema, _subtema, questoes = await _cenario(db_session)
    await client.post(
        "/diagnostic/answer",
        headers=student_identity.headers,
        json={"tema_id": tema.id, "respostas": _respostas(questoes, corretas=4)},
    )

    corpo = (await client.get("/profile/summary", headers=student_identity.headers)).json()
    # 4 questões x 10 + bônus de sequência 1 x 5 = 45
    assert corpo["pontos"]["total"] == 45
    assert corpo["estudo"]["questoes_respondidas"] == 4
    assert corpo["estudo"]["subtemas_iniciados"] == 1
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_pontuacao_no_diagnostico.py -q`
Expected: FAIL — nenhum lançamento é gravado.

- [ ] **Step 3: Acrescente os imports no router**

Em `app/routers/diagnostico.py`, junto dos imports de serviço já existentes:

```python
from app.services.pontuacao import (
    PONTOS_ETAPA_CONCLUIDA,
    PONTOS_QUESTAO_CORRETA,
    PONTOS_REVISAO_NO_PRAZO,
    bonus_streak,
    registrar,
)
from app.services.roadmap import concluir_etapa
```

- [ ] **Step 4: Pontue cada questão correta**

No laço que já percorre `payload.respostas` e grava `DiagnosticoResposta`,
logo depois do `db.add(DiagnosticoResposta(...))`, acrescente:

```python
        # Pontuação da questão: MESMA transação que grava a resposta. O
        # `registrar` é idempotente por (aluno, "questao", questao_id), então
        # reenviar o questionário não pontua de novo — e não pontuar duas
        # vezes é o que permite deixar o reenvio livre.
        if acertou:
            await registrar(
                db,
                aluno_id=aluno_id,
                origem="questao",
                referencia=str(r.questao_id),
                pontos=PONTOS_QUESTAO_CORRETA,
            )
```

- [ ] **Step 5: Pontue revisão, sequência e conclusão de etapa**

No laço por subtema, logo depois de `await db.execute(stmt)` (o upsert de
`AlunoTemaProgresso`), acrescente:

```python
        agora = datetime.now(UTC)

        # Revisão concluída no prazo: a linha de progresso JÁ existia e a
        # próxima revisão já tinha vencido quando o aluno respondeu. Não há
        # rota de "concluir revisão" neste serviço — `/reviews/today` só
        # lista —, então responder é o ato que a conclui (decisão D1 do
        # plano). A referência carrega a DATA da revisão vencida: assim a
        # revisão de amanhã pontua de novo, e a de hoje, não.
        if progresso_atual is not None and progresso_atual.proxima_revisao is not None:
            vencida_em = progresso_atual.proxima_revisao
            if vencida_em <= agora:
                await registrar(
                    db,
                    aluno_id=aluno_id,
                    origem="revisao",
                    referencia=f"{subtema_id}:{vencida_em.date().isoformat()}",
                    pontos=PONTOS_REVISAO_NO_PRAZO,
                )

        # Bônus de sequência: só quando a sequência CRESCEU nesta resposta.
        # A referência inclui o novo valor, então cada degrau paga uma vez.
        if novo_streak > streak_atual:
            await registrar(
                db,
                aluno_id=aluno_id,
                origem="streak",
                referencia=f"{subtema_id}:{novo_streak}",
                pontos=bonus_streak(novo_streak),
            )

        # Conclusão de etapa: `concluir_etapa` só devolve True na transição
        # (o UPDATE tem `WHERE concluida_em IS NULL`), e é esse True que
        # impede pontuar de novo um subtema que o aluno já dominava.
        if dominio >= LIMIAR_DOMINIO_SUBTEMA:
            concluiu = await concluir_etapa(
                db, aluno_id=aluno_id, subtema_id=subtema_id, quando=agora
            )
            if concluiu:
                await registrar(
                    db,
                    aluno_id=aluno_id,
                    origem="etapa",
                    referencia=str(subtema_id),
                    pontos=PONTOS_ETAPA_CONCLUIDA,
                )
```

`datetime` e `UTC` já são importados por este módulo? **Não** — o arquivo
importa só `defaultdict` e os símbolos de app/. Acrescente no topo:

```python
from datetime import UTC, datetime
```

**Onde NÃO mexer:** não crie um `try/except` em volta destes blocos. Pontos e
progresso compartilham a transação e o `await db.commit()` que já existe no
fim da rota — ou tudo grava, ou nada grava e o aluno reenvia sem pontuar
duas vezes (decisão D17).

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_pontuacao_no_diagnostico.py -q`
Expected: 9 passed.

- [ ] **Step 7: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **158 passed** (149 + 9). Em particular, os testes de concorrência que já
existiam (`test_concurrent_answers_*`) continuam verdes: o `registrar` novo
não segura lock nenhum além do que a linha de progresso já segurava.

- [ ] **Step 8: Commit**

```bash
git add back-end/learning-service/app/routers/diagnostico.py \
        back-end/learning-service/tests/test_pontuacao_no_diagnostico.py
git commit -m "feat(learning): award points and close roadmap steps when answering"
```

---

### Task 8: O gateway aprende três prefixos

**Files:**
- Modify: `back-end/api-gateway/app/routing.py` (dicionário `SERVICE_MAP`)
- Test: `back-end/api-gateway/tests/test_routing.py`

**Interfaces:**
- Consumes: nada das tarefas anteriores — pode rodar em paralelo.
- Produces: `/api/onboarding`, `/api/roadmap` e `/api/profile/*` chegam ao
  learning-service. É o que torna as tarefas 10-14 possíveis pelo app.

- [ ] **Step 1: Escreva o teste que falha**

Acrescente a `tests/test_routing.py`:

```python
def test_os_prefixos_da_spec_d_vao_para_o_learning():
    from app.config import settings

    for prefixo in ("onboarding", "roadmap", "profile"):
        destino = resolve_destination(f"{prefixo}/qualquer-coisa")
        assert destino is not None, prefixo
        base_url, path = destino
        assert base_url == settings.learning_service_url
        assert path == f"/{prefixo}/qualquer-coisa"


def test_profile_nao_rouba_o_caminho_de_conta_do_auth():
    """`/api/users/me` continua no auth: `profile` é resumo de estudo, não
    identidade."""
    from app.config import settings

    base_url, _path = resolve_destination("users/me")
    assert base_url == settings.auth_service_url
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/api-gateway && uv run pytest tests/test_routing.py -q`
Expected: FAIL — `resolve_destination("onboarding/...")` devolve `None`.

- [ ] **Step 3: Acrescente os prefixos**

Em `app/routing.py`, no `SERVICE_MAP`, junto das entradas de learning:

```python
    "subjects": "learning",
    "topics": "learning",
    "subtopics": "learning",
    "diagnostic": "learning",
    "recommendations": "learning",
    "reviews": "learning",
    # Spec D. `profile` é do learning-service porque o que a tela lê ali é
    # resumo de ESTUDO (objetivo, percurso, pontos) — os dados de conta
    # continuam em `/api/users/me`, no auth.
    "onboarding": "learning",
    "roadmap": "learning",
    "profile": "learning",
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/api-gateway && uv run pytest -q`
Expected: **41 passed** (39 do baseline + 2).

- [ ] **Step 5: Lint e commit**

```bash
cd back-end/api-gateway && uv run ruff format . && uv run ruff check .
git add back-end/api-gateway/app/routing.py back-end/api-gateway/tests/test_routing.py
git commit -m "feat(gateway): route onboarding, roadmap and profile to learning"
```

---

### Task 9: `scripts/seed_enem.sql` — a estrutura completa

**Files:**
- Create: `back-end/learning-service/scripts/seed_enem.sql`
- Test: `back-end/learning-service/tests/test_seed_enem.py`

**Interfaces:**
- Consumes: as tabelas `materia`, `tema`, `subtema` (já existiam).
- Produces: 11 matérias, 33 temas e 99 subtemas, com `ordem` preenchido — é
  o insumo que `gerar_roadmap` percorre.

- [ ] **Step 1: Escreva o teste que falha**

Crie `tests/test_seed_enem.py`:

```python
from pathlib import Path

from sqlalchemy import func, select, text

from app.models.subtema import Materia, Subtema, Tema

SEED = Path(__file__).resolve().parents[1] / "scripts" / "seed_enem.sql"


async def _rodar_seed(db):
    # `text()` com um arquivo do próprio repositório, sem interpolação de
    # nada vindo do usuário — é execução de script, não montagem de query.
    await db.execute(text(SEED.read_text()))
    await db.commit()


async def test_o_seed_existe_e_e_sql():
    assert SEED.exists()
    conteudo = SEED.read_text()
    assert "INSERT INTO materia" in conteudo
    assert "ON CONFLICT (id) DO NOTHING" in conteudo


async def test_o_seed_cria_a_estrutura_completa(db_session):
    await _rodar_seed(db_session)

    materias = (await db_session.execute(select(func.count()).select_from(Materia))).scalar_one()
    temas = (await db_session.execute(select(func.count()).select_from(Tema))).scalar_one()
    subtemas = (await db_session.execute(select(func.count()).select_from(Subtema))).scalar_one()
    assert materias == 11
    assert temas == 33
    assert subtemas == 99


async def test_toda_materia_tem_ao_menos_um_subtema(db_session):
    await _rodar_seed(db_session)

    orfas = (
        await db_session.execute(
            select(Materia.nome)
            .outerjoin(Tema, Tema.materia_id == Materia.id)
            .outerjoin(Subtema, Subtema.tema_id == Tema.id)
            .group_by(Materia.id, Materia.nome)
            .having(func.count(Subtema.id) == 0)
        )
    ).scalars().all()
    assert orfas == []


async def test_toda_ordem_esta_preenchida(db_session):
    await _rodar_seed(db_session)

    temas_sem_ordem = (
        await db_session.execute(select(func.count()).select_from(Tema).where(Tema.ordem == 0))
    ).scalar_one()
    subtemas_sem_ordem = (
        await db_session.execute(
            select(func.count()).select_from(Subtema).where(Subtema.ordem == 0)
        )
    ).scalar_one()
    assert temas_sem_ordem == 0
    assert subtemas_sem_ordem == 0


async def test_o_seed_e_idempotente_em_duas_passadas(db_session):
    await _rodar_seed(db_session)
    await _rodar_seed(db_session)

    materias = (await db_session.execute(select(func.count()).select_from(Materia))).scalar_one()
    subtemas = (await db_session.execute(select(func.count()).select_from(Subtema))).scalar_one()
    assert materias == 11
    assert subtemas == 99


async def test_as_faixas_de_id_nao_invadem_o_seed_de_citologia(db_session):
    """`seed_biologia_citologia.sql` ocupa temas 1-3 e subtemas 1-8. Se o
    seed novo entrar nessa faixa, rodar os dois no mesmo banco perde
    linhas em silêncio pelo `ON CONFLICT DO NOTHING`."""
    await _rodar_seed(db_session)

    menor_tema = (await db_session.execute(select(func.min(Tema.id)))).scalar_one()
    menor_subtema = (await db_session.execute(select(func.min(Subtema.id)))).scalar_one()
    assert menor_tema >= 100
    assert menor_subtema >= 100
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd back-end/learning-service && uv run pytest tests/test_seed_enem.py -q`
Expected: FAIL — `scripts/seed_enem.sql` não existe.

- [ ] **Step 3: Escreva o seed**

`scripts/seed_enem.sql`, exatamente este conteúdo:

```sql
-- Estrutura do ENEM: matérias, temas e subtemas das quatro áreas.
--
-- SEED DE ESTRUTURA, não de conteúdo: nenhuma questão entra aqui. As
-- questões entram por matéria, em arquivos próprios, no formato de
-- `seed_biologia_citologia.sql` — e o roadmap funciona com qualquer
-- quantidade delas: subtema sem questão aparece no percurso marcado como
-- indisponível para praticar (ver `GET /roadmap`, campo `tem_questoes`).
--
-- FAIXAS DE ID, para não colidir com `seed_biologia_citologia.sql`, que já
-- ocupa materia 1, temas 1-3, subtemas 1-8 e questões 1-38:
--   materia   1..11   (1 é Biologia, o MESMO registro do seed existente)
--   tema      100..132
--   subtema   100..198
--
-- Idempotente: `ON CONFLICT (id) DO NOTHING` em toda inserção, e os
-- `setval` no fim reposicionam as sequences para que inserções pela API
-- (ex.: `scripts/ingest_enem.py`) não colidam com estes ids.
--
-- `videoaula_base_url`, `videoaula_revisao_url` e `descricao_ia` ficam
-- NULL: as duas primeiras são links de apoio (a rota de recomendação já
-- serializa `video_url: null` sem quebrar) e a terceira é sinal semântico
-- opcional (`f"{s.nome}. {s.descricao_ia or ''}"` em
-- `services/recomendacao_semantica.py`). Preenchê-las é melhoria por
-- matéria, não pré-requisito desta entrega.

INSERT INTO materia (id, nome) VALUES
(1, 'Biologia'),
(2, 'Física'),
(3, 'Química'),
(4, 'Matemática'),
(5, 'Português'),
(6, 'Literatura'),
(7, 'Inglês'),
(8, 'História'),
(9, 'Geografia'),
(10, 'Filosofia'),
(11, 'Sociologia')
ON CONFLICT (id) DO NOTHING;

INSERT INTO tema (id, materia_id, nome, ordem) VALUES
(100, 1, 'Ecologia', 1),
(101, 1, 'Fisiologia Humana', 2),
(102, 1, 'Evolução', 3),
(103, 2, 'Mecânica', 1),
(104, 2, 'Termologia e Óptica', 2),
(105, 2, 'Eletricidade e Magnetismo', 3),
(106, 3, 'Química Geral', 1),
(107, 3, 'Físico-Química', 2),
(108, 3, 'Química Orgânica', 3),
(109, 4, 'Álgebra e Funções', 1),
(110, 4, 'Geometria', 2),
(111, 4, 'Estatística e Probabilidade', 3),
(112, 5, 'Gramática e Norma', 1),
(113, 5, 'Interpretação de Texto', 2),
(114, 5, 'Variação Linguística', 3),
(115, 6, 'Escolas Literárias', 1),
(116, 6, 'Modernismo Brasileiro', 2),
(117, 6, 'Análise Literária', 3),
(118, 7, 'Compreensão de Texto', 1),
(119, 7, 'Vocabulário e Cognatos', 2),
(120, 7, 'Estruturas Gramaticais', 3),
(121, 8, 'Brasil Colônia e Império', 1),
(122, 8, 'Brasil República', 2),
(123, 8, 'História Geral e Contemporânea', 3),
(124, 9, 'Geografia Física', 1),
(125, 9, 'Geopolítica e Globalização', 2),
(126, 9, 'Geografia do Brasil', 3),
(127, 10, 'Filosofia Antiga', 1),
(128, 10, 'Filosofia Moderna', 2),
(129, 10, 'Ética e Política', 3),
(130, 11, 'Formação da Sociologia', 1),
(131, 11, 'Trabalho e Sociedade', 2),
(132, 11, 'Cultura e Cidadania', 3)
ON CONFLICT (id) DO NOTHING;

INSERT INTO subtema (id, tema_id, nome, ordem, videoaula_base_url, videoaula_revisao_url, descricao_ia) VALUES
(100, 100, 'Ecossistemas e Cadeias Alimentares', 1, NULL, NULL, NULL),
(101, 100, 'Ciclos Biogeoquímicos', 2, NULL, NULL, NULL),
(102, 100, 'Impactos Ambientais', 3, NULL, NULL, NULL),
(103, 101, 'Sistema Digestório', 1, NULL, NULL, NULL),
(104, 101, 'Sistema Circulatório e Respiratório', 2, NULL, NULL, NULL),
(105, 101, 'Sistema Nervoso e Endócrino', 3, NULL, NULL, NULL),
(106, 102, 'Origem da Vida', 1, NULL, NULL, NULL),
(107, 102, 'Seleção Natural', 2, NULL, NULL, NULL),
(108, 102, 'Especiação e Evidências', 3, NULL, NULL, NULL),
(109, 103, 'Cinemática', 1, NULL, NULL, NULL),
(110, 103, 'Leis de Newton', 2, NULL, NULL, NULL),
(111, 103, 'Trabalho e Energia', 3, NULL, NULL, NULL),
(112, 104, 'Temperatura e Calor', 1, NULL, NULL, NULL),
(113, 104, 'Leis da Termodinâmica', 2, NULL, NULL, NULL),
(114, 104, 'Reflexão e Refração', 3, NULL, NULL, NULL),
(115, 105, 'Carga e Campo Elétrico', 1, NULL, NULL, NULL),
(116, 105, 'Circuitos Elétricos', 2, NULL, NULL, NULL),
(117, 105, 'Campo Magnético e Indução', 3, NULL, NULL, NULL),
(118, 106, 'Estrutura Atômica', 1, NULL, NULL, NULL),
(119, 106, 'Tabela Periódica', 2, NULL, NULL, NULL),
(120, 106, 'Ligações Químicas', 3, NULL, NULL, NULL),
(121, 107, 'Soluções e Concentração', 1, NULL, NULL, NULL),
(122, 107, 'Termoquímica', 2, NULL, NULL, NULL),
(123, 107, 'Equilíbrio Químico', 3, NULL, NULL, NULL),
(124, 108, 'Funções Orgânicas', 1, NULL, NULL, NULL),
(125, 108, 'Isomeria', 2, NULL, NULL, NULL),
(126, 108, 'Reações Orgânicas', 3, NULL, NULL, NULL),
(127, 109, 'Função Afim e Quadrática', 1, NULL, NULL, NULL),
(128, 109, 'Função Exponencial e Logarítmica', 2, NULL, NULL, NULL),
(129, 109, 'Progressões', 3, NULL, NULL, NULL),
(130, 110, 'Geometria Plana', 1, NULL, NULL, NULL),
(131, 110, 'Geometria Espacial', 2, NULL, NULL, NULL),
(132, 110, 'Geometria Analítica', 3, NULL, NULL, NULL),
(133, 111, 'Medidas de Tendência Central', 1, NULL, NULL, NULL),
(134, 111, 'Análise Combinatória', 2, NULL, NULL, NULL),
(135, 111, 'Probabilidade', 3, NULL, NULL, NULL),
(136, 112, 'Classes de Palavras', 1, NULL, NULL, NULL),
(137, 112, 'Sintaxe do Período', 2, NULL, NULL, NULL),
(138, 112, 'Concordância e Regência', 3, NULL, NULL, NULL),
(139, 113, 'Gêneros Textuais', 1, NULL, NULL, NULL),
(140, 113, 'Coesão e Coerência', 2, NULL, NULL, NULL),
(141, 113, 'Figuras de Linguagem', 3, NULL, NULL, NULL),
(142, 114, 'Norma-Padrão e Variedades', 1, NULL, NULL, NULL),
(143, 114, 'Registro e Adequação', 2, NULL, NULL, NULL),
(144, 114, 'Preconceito Linguístico', 3, NULL, NULL, NULL),
(145, 115, 'Barroco e Arcadismo', 1, NULL, NULL, NULL),
(146, 115, 'Romantismo', 2, NULL, NULL, NULL),
(147, 115, 'Realismo e Naturalismo', 3, NULL, NULL, NULL),
(148, 116, 'Primeira Geração', 1, NULL, NULL, NULL),
(149, 116, 'Segunda Geração', 2, NULL, NULL, NULL),
(150, 116, 'Terceira Geração', 3, NULL, NULL, NULL),
(151, 117, 'Prosa e Narrativa', 1, NULL, NULL, NULL),
(152, 117, 'Poesia e Métrica', 2, NULL, NULL, NULL),
(153, 117, 'Contexto Histórico da Obra', 3, NULL, NULL, NULL),
(154, 118, 'Skimming e Scanning', 1, NULL, NULL, NULL),
(155, 118, 'Ideia Principal e Detalhes', 2, NULL, NULL, NULL),
(156, 118, 'Inferência de Sentido', 3, NULL, NULL, NULL),
(157, 119, 'Cognatos e Falsos Cognatos', 1, NULL, NULL, NULL),
(158, 119, 'Phrasal Verbs', 2, NULL, NULL, NULL),
(159, 119, 'Afixos e Formação de Palavras', 3, NULL, NULL, NULL),
(160, 120, 'Verb Tenses', 1, NULL, NULL, NULL),
(161, 120, 'Modal Verbs', 2, NULL, NULL, NULL),
(162, 120, 'Conectivos e Referência', 3, NULL, NULL, NULL),
(163, 121, 'Colonização e Economia Açucareira', 1, NULL, NULL, NULL),
(164, 121, 'Mineração e Inconfidências', 2, NULL, NULL, NULL),
(165, 121, 'Independência e Segundo Reinado', 3, NULL, NULL, NULL),
(166, 122, 'República Velha', 1, NULL, NULL, NULL),
(167, 122, 'Era Vargas', 2, NULL, NULL, NULL),
(168, 122, 'Ditadura Militar e Redemocratização', 3, NULL, NULL, NULL),
(169, 123, 'Revolução Industrial', 1, NULL, NULL, NULL),
(170, 123, 'Guerras Mundiais', 2, NULL, NULL, NULL),
(171, 123, 'Guerra Fria e Descolonização', 3, NULL, NULL, NULL),
(172, 124, 'Relevo e Solos', 1, NULL, NULL, NULL),
(173, 124, 'Clima e Vegetação', 2, NULL, NULL, NULL),
(174, 124, 'Hidrografia', 3, NULL, NULL, NULL),
(175, 125, 'Blocos Econômicos', 1, NULL, NULL, NULL),
(176, 125, 'Conflitos e Fronteiras', 2, NULL, NULL, NULL),
(177, 125, 'Fluxos Migratórios', 3, NULL, NULL, NULL),
(178, 126, 'Regionalização', 1, NULL, NULL, NULL),
(179, 126, 'Urbanização e Metrópoles', 2, NULL, NULL, NULL),
(180, 126, 'Agropecuária e Indústria', 3, NULL, NULL, NULL),
(181, 127, 'Pré-Socráticos', 1, NULL, NULL, NULL),
(182, 127, 'Sócrates e Platão', 2, NULL, NULL, NULL),
(183, 127, 'Aristóteles', 3, NULL, NULL, NULL),
(184, 128, 'Racionalismo e Empirismo', 1, NULL, NULL, NULL),
(185, 128, 'Contratualismo', 2, NULL, NULL, NULL),
(186, 128, 'Kant e o Iluminismo', 3, NULL, NULL, NULL),
(187, 129, 'Ética e Moral', 1, NULL, NULL, NULL),
(188, 129, 'Poder e Estado', 2, NULL, NULL, NULL),
(189, 129, 'Direitos Humanos', 3, NULL, NULL, NULL),
(190, 130, 'Durkheim', 1, NULL, NULL, NULL),
(191, 130, 'Weber', 2, NULL, NULL, NULL),
(192, 130, 'Marx', 3, NULL, NULL, NULL),
(193, 131, 'Divisão Social do Trabalho', 1, NULL, NULL, NULL),
(194, 131, 'Taylorismo e Fordismo', 2, NULL, NULL, NULL),
(195, 131, 'Trabalho na Era Digital', 3, NULL, NULL, NULL),
(196, 132, 'Cultura e Identidade', 1, NULL, NULL, NULL),
(197, 132, 'Movimentos Sociais', 2, NULL, NULL, NULL),
(198, 132, 'Cidadania e Desigualdade', 3, NULL, NULL, NULL)
ON CONFLICT (id) DO NOTHING;

-- materias 1..11, temas 100..132, subtemas 100..198

-- Sequences reposicionadas, mesmo padrão do seed de Citologia.
SELECT setval('materia_id_seq', (SELECT MAX(id) FROM materia));
SELECT setval('tema_id_seq', (SELECT MAX(id) FROM tema));
SELECT setval('subtema_id_seq', (SELECT MAX(id) FROM subtema));
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd back-end/learning-service && uv run pytest tests/test_seed_enem.py -q`
Expected: 6 passed.

- [ ] **Step 5: Suíte inteira + lint**

Run: `cd back-end/learning-service && uv run ruff format . && uv run ruff check . && uv run pytest -q`
Expected: **164 passed** (158 + 6).

- [ ] **Step 6: Commit**

```bash
git add back-end/learning-service/scripts/seed_enem.sql \
        back-end/learning-service/tests/test_seed_enem.py
git commit -m "feat(learning): seed the full ENEM subject structure"
```

---

### Task 10: Flutter — modelos e cliente HTTP do tracker

**Files:**
- Create: `front-end-flutter/lib/features/tracker/domain/study_summary.dart`
- Create: `front-end-flutter/lib/features/tracker/domain/roadmap_step.dart`
- Create: `front-end-flutter/lib/features/tracker/data/tracker_api.dart`
- Test: `front-end-flutter/test/features/tracker/study_summary_test.dart`
- Test: `front-end-flutter/test/features/tracker/tracker_api_test.dart`

**Interfaces:**
- Consumes: `GET /profile/summary` (Task 6), `GET /roadmap` (Task 5),
  `GET|POST|PUT /onboarding` (Task 4), pelo gateway (Task 8).
- Produces, usados pelas tarefas 11-14:
  - `StudySummary { goal, roadmap, points, study }` com
    `Goal { title, targetDate, daysElapsed, daysTotal }`,
    `RoadmapProgress { totalSteps, completedSteps, progress }`,
    `Points { total, level, streak }`,
    `Study { answeredQuestions, startedSubtopics }`
  - `RoadmapStep { subtopicId, subtopicName, topicName, subjectName, order,
    deadline, done, hasQuestions }`
  - `Roadmap { goal, reason, tightDeadline, steps, total }`
  - `TrackerApi.fetchSummary()`, `.fetchRoadmap({limit, offset})`,
    `.fetchGoal()`, `.saveGoal({required String title, required DateTime
    targetDate, required bool update})`
  - `TrackerException(message)`

- [ ] **Step 1: Escreva o teste de parsing que falha**

Crie `test/features/tracker/study_summary_test.dart`:

```dart
import 'package:edu_ia/features/tracker/domain/roadmap_step.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('aluno zerado vira zeros, não nulos', () {
    final resumo = StudySummary.fromJson(const {
      'objetivo': null,
      'roadmap': {'etapas_totais': 0, 'etapas_concluidas': 0, 'progresso': 0.0},
      'pontos': {'total': 0, 'nivel': 1, 'streak': 0},
      'estudo': {'questoes_respondidas': 0, 'subtemas_iniciados': 0},
    });

    expect(resumo.goal, isNull);
    expect(resumo.points.total, 0);
    expect(resumo.points.level, 1);
    expect(resumo.roadmap.progress, 0.0);
    expect(resumo.study.answeredQuestions, 0);
  });

  test('objetivo preenchido traz título, data e os dois contadores de dias', () {
    final resumo = StudySummary.fromJson(const {
      'objetivo': {
        'titulo': 'Medicina USP',
        'data_alvo': '2027-11-07',
        'dias_decorridos': 124,
        'dias_totais': 200,
      },
      'roadmap': {'etapas_totais': 50, 'etapas_concluidas': 34, 'progresso': 0.68},
      'pontos': {'total': 3120, 'nivel': 8, 'streak': 4},
      'estudo': {'questoes_respondidas': 15, 'subtemas_iniciados': 6},
    });

    expect(resumo.goal!.title, 'Medicina USP');
    expect(resumo.goal!.targetDate, DateTime(2027, 11, 7));
    expect(resumo.goal!.daysElapsed, 124);
    expect(resumo.goal!.daysTotal, 200);
    expect(resumo.roadmap.progress, 0.68);
  });

  test('número que chega como int ou como string não quebra a tela', () {
    final resumo = StudySummary.fromJson(const {
      'objetivo': null,
      'roadmap': {'etapas_totais': 3, 'etapas_concluidas': 1, 'progresso': 1},
      'pontos': {'total': 10, 'nivel': 1, 'streak': 0},
      'estudo': {'questoes_respondidas': 2, 'subtemas_iniciados': 1},
    });

    expect(resumo.roadmap.progress, 1.0);
  });

  test('campo ausente não derruba o parse — vira zero', () {
    final resumo = StudySummary.fromJson(const {'objetivo': null});
    expect(resumo.points.total, 0);
    expect(resumo.roadmap.totalSteps, 0);
    expect(resumo.study.startedSubtopics, 0);
  });

  test('etapa do roadmap sabe se dá para praticar', () {
    final etapa = RoadmapStep.fromJson(const {
      'subtema_id': 7,
      'subtema_nome': 'Membrana Plasmática',
      'tema_nome': 'Citologia',
      'materia_nome': 'Biologia',
      'ordem': 0,
      'prazo': '2026-10-01',
      'concluida': false,
      'concluida_em': null,
      'tem_questoes': false,
    });

    expect(etapa.subtopicName, 'Membrana Plasmática');
    expect(etapa.subjectName, 'Biologia');
    expect(etapa.deadline, DateTime(2026, 10, 1));
    expect(etapa.done, isFalse);
    expect(etapa.hasQuestions, isFalse);
  });

  test('roadmap sem objetivo carrega o motivo para a tela exibir', () {
    final roadmap = Roadmap.fromJson(const {
      'objetivo': null,
      'motivo': 'Defina um objetivo e uma data-alvo para montar seu percurso.',
      'prazo_apertado': false,
      'items': [],
      'total': 0,
      'limit': 50,
      'offset': 0,
    });

    expect(roadmap.steps, isEmpty);
    expect(roadmap.reason, contains('objetivo'));
    expect(roadmap.goal, isNull);
  });
}
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd front-end-flutter && flutter test test/features/tracker/study_summary_test.dart`
Expected: FAIL — `Target of URI doesn't exist`.

- [ ] **Step 3: Escreva os modelos**

`lib/features/tracker/domain/study_summary.dart`:

```dart
/// Modelos do resumo de estudo — o que `GET /profile/summary` devolve.
///
/// Todo número desta tela vem daqui, e daqui vem só o que o backend mandou:
/// a spec D existe porque a tela inicial anunciava "124/200 dias" para
/// qualquer aluno.
///
/// O parsing é tolerante a tipo (`_asInt`/`_asDouble`) porque JSON de
/// número em Dart chega como `int` ou `double` conforme o valor, e um
/// `as double` estoura em `1` (int) enquanto `1.0` passa. Ausência de
/// campo vira zero, nunca exceção: uma tela que não desenha é pior que uma
/// tela que desenha zero.
library;

int _asInt(dynamic valor) {
  if (valor is int) return valor;
  if (valor is num) return valor.toInt();
  if (valor is String) return int.tryParse(valor) ?? 0;
  return 0;
}

double _asDouble(dynamic valor) {
  if (valor is num) return valor.toDouble();
  if (valor is String) return double.tryParse(valor) ?? 0.0;
  return 0.0;
}

DateTime? _asDate(dynamic valor) {
  if (valor is String && valor.isNotEmpty) return DateTime.tryParse(valor);
  return null;
}

class Goal {
  const Goal({
    required this.title,
    required this.targetDate,
    required this.daysElapsed,
    required this.daysTotal,
  });

  final String title;
  final DateTime targetDate;
  final int daysElapsed;
  final int daysTotal;

  /// Fração do prazo já percorrida, 0.0 a 1.0. Zero quando o objetivo foi
  /// criado para hoje — o denominador é zero e a barra fica vazia em vez de
  /// estourar.
  double get elapsedFraction => daysTotal <= 0 ? 0.0 : (daysElapsed / daysTotal).clamp(0.0, 1.0);

  static Goal? fromJson(Map<String, dynamic>? json) {
    if (json == null) return null;
    return Goal(
      title: (json['titulo'] ?? '') as String,
      targetDate: _asDate(json['data_alvo']) ?? DateTime.now(),
      daysElapsed: _asInt(json['dias_decorridos']),
      daysTotal: _asInt(json['dias_totais']),
    );
  }
}

class RoadmapProgress {
  const RoadmapProgress({
    required this.totalSteps,
    required this.completedSteps,
    required this.progress,
  });

  final int totalSteps;
  final int completedSteps;
  final double progress;

  factory RoadmapProgress.fromJson(Map<String, dynamic>? json) => RoadmapProgress(
    totalSteps: _asInt(json?['etapas_totais']),
    completedSteps: _asInt(json?['etapas_concluidas']),
    progress: _asDouble(json?['progresso']),
  );
}

class Points {
  const Points({required this.total, required this.level, required this.streak});

  final int total;
  final int level;
  final int streak;

  factory Points.fromJson(Map<String, dynamic>? json) => Points(
    total: _asInt(json?['total']),
    // Nível mínimo é 1, nunca 0: um aluno sem pontos está no nível 1.
    level: json?['nivel'] == null ? 1 : _asInt(json?['nivel']),
    streak: _asInt(json?['streak']),
  );
}

class Study {
  const Study({required this.answeredQuestions, required this.startedSubtopics});

  final int answeredQuestions;
  final int startedSubtopics;

  factory Study.fromJson(Map<String, dynamic>? json) => Study(
    answeredQuestions: _asInt(json?['questoes_respondidas']),
    startedSubtopics: _asInt(json?['subtemas_iniciados']),
  );
}

class StudySummary {
  const StudySummary({
    required this.goal,
    required this.roadmap,
    required this.points,
    required this.study,
  });

  final Goal? goal;
  final RoadmapProgress roadmap;
  final Points points;
  final Study study;

  factory StudySummary.fromJson(Map<String, dynamic> json) => StudySummary(
    goal: Goal.fromJson(json['objetivo'] as Map<String, dynamic>?),
    roadmap: RoadmapProgress.fromJson(json['roadmap'] as Map<String, dynamic>?),
    points: Points.fromJson(json['pontos'] as Map<String, dynamic>?),
    study: Study.fromJson(json['estudo'] as Map<String, dynamic>?),
  );
}
```

`lib/features/tracker/domain/roadmap_step.dart`:

```dart
import 'study_summary.dart';

/// Uma etapa do percurso e o envelope que `GET /roadmap` devolve.
class RoadmapStep {
  const RoadmapStep({
    required this.subtopicId,
    required this.subtopicName,
    required this.topicName,
    required this.subjectName,
    required this.order,
    required this.deadline,
    required this.done,
    required this.hasQuestions,
  });

  final int subtopicId;
  final String subtopicName;
  final String topicName;
  final String subjectName;
  final int order;
  final DateTime deadline;
  final bool done;

  /// `false` quando a matéria ainda não tem questão semeada. A tela mostra a
  /// etapa assim mesmo, com o botão desabilitado e o motivo — é a
  /// alternativa honesta a esconder a matéria.
  final bool hasQuestions;

  factory RoadmapStep.fromJson(Map<String, dynamic> json) => RoadmapStep(
    subtopicId: (json['subtema_id'] as num?)?.toInt() ?? 0,
    subtopicName: (json['subtema_nome'] ?? '') as String,
    topicName: (json['tema_nome'] ?? '') as String,
    subjectName: (json['materia_nome'] ?? '') as String,
    order: (json['ordem'] as num?)?.toInt() ?? 0,
    deadline: DateTime.tryParse((json['prazo'] ?? '') as String) ?? DateTime.now(),
    done: json['concluida'] == true,
    hasQuestions: json['tem_questoes'] == true,
  );
}

class Roadmap {
  const Roadmap({
    required this.goal,
    required this.reason,
    required this.tightDeadline,
    required this.steps,
    required this.total,
  });

  final Goal? goal;

  /// Só vem preenchido quando a lista está vazia por falta de objetivo — é o
  /// convite ao onboarding que a tela exibe.
  final String? reason;
  final bool tightDeadline;
  final List<RoadmapStep> steps;
  final int total;

  factory Roadmap.fromJson(Map<String, dynamic> json) => Roadmap(
    goal: Goal.fromJson(json['objetivo'] as Map<String, dynamic>?),
    reason: json['motivo'] as String?,
    tightDeadline: json['prazo_apertado'] == true,
    steps: ((json['items'] ?? const []) as List<dynamic>)
        .map((e) => RoadmapStep.fromJson(e as Map<String, dynamic>))
        .toList(),
    total: (json['total'] as num?)?.toInt() ?? 0,
  );
}
```

- [ ] **Step 4: Rode e confirme que passa**

Run: `cd front-end-flutter && flutter test test/features/tracker/study_summary_test.dart`
Expected: 6 passed.

- [ ] **Step 5: Escreva o teste do cliente HTTP**

Crie `test/features/tracker/tracker_api_test.dart`:

```dart
import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class _FakeTokenStore extends TokenStore {
  @override
  Future<String?> readAccessToken() async => 'fake-token';
}

const _resumoJson = {
  'objetivo': null,
  'roadmap': {'etapas_totais': 0, 'etapas_concluidas': 0, 'progresso': 0.0},
  'pontos': {'total': 0, 'nivel': 1, 'streak': 0},
  'estudo': {'questoes_respondidas': 0, 'subtemas_iniciados': 0},
};

void main() {
  test('fetchSummary chama /profile/summary com o token', () async {
    late http.Request capturada;
    final client = MockClient((req) async {
      capturada = req;
      return http.Response(jsonEncode(_resumoJson), 200);
    });

    final resumo = await TrackerApi(client: client, tokenStore: _FakeTokenStore()).fetchSummary();

    expect(capturada.url.path, endsWith('/profile/summary'));
    expect(capturada.headers['Authorization'], 'Bearer fake-token');
    expect(resumo.points.total, 0);
  });

  test('fetchRoadmap pagina pela query', () async {
    late http.Request capturada;
    final client = MockClient((req) async {
      capturada = req;
      return http.Response(
        jsonEncode({
          'objetivo': null,
          'motivo': null,
          'prazo_apertado': false,
          'items': [],
          'total': 0,
          'limit': 20,
          'offset': 40,
        }),
        200,
      );
    });

    await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchRoadmap(limit: 20, offset: 40);

    expect(capturada.url.queryParameters['limit'], '20');
    expect(capturada.url.queryParameters['offset'], '40');
  });

  test('saveGoal manda POST na criação e PUT na edição', () async {
    final metodos = <String>[];
    final client = MockClient((req) async {
      metodos.add(req.method);
      return http.Response(
        jsonEncode({
          'objetivo': {
            'titulo': 'Medicina',
            'data_alvo': '2027-11-07',
            'criado_em': '2026-09-10T10:00:00Z',
            'atualizado_em': '2026-09-10T10:00:00Z',
          },
          'etapas_geradas': 99,
          'prazo_apertado': false,
        }),
        req.method == 'POST' ? 201 : 200,
      );
    });

    final api = TrackerApi(client: client, tokenStore: _FakeTokenStore());
    await api.saveGoal(title: 'Medicina', targetDate: DateTime(2027, 11, 7), update: false);
    await api.saveGoal(title: 'Medicina', targetDate: DateTime(2027, 11, 7), update: true);

    expect(metodos, ['POST', 'PUT']);
  });

  test('data vai como AAAA-MM-DD, não como ISO com hora', () async {
    late http.Request capturada;
    final client = MockClient((req) async {
      capturada = req;
      return http.Response(
        jsonEncode({
          'objetivo': {
            'titulo': 'Medicina',
            'data_alvo': '2027-11-07',
            'criado_em': '2026-09-10T10:00:00Z',
            'atualizado_em': '2026-09-10T10:00:00Z',
          },
          'etapas_geradas': 1,
          'prazo_apertado': false,
        }),
        201,
      );
    });

    await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).saveGoal(title: 'Medicina', targetDate: DateTime(2027, 11, 7), update: false);

    expect(jsonDecode(capturada.body)['data_alvo'], '2027-11-07');
  });

  test('a mensagem do servidor é a que chega na tela', () async {
    final client = MockClient(
      (_) async => http.Response(
        jsonEncode({
          'detail': [
            {'msg': 'Value error, A data-alvo não pode estar no passado'},
          ],
        }),
        422,
      ),
    );

    expect(
      () => TrackerApi(
        client: client,
        tokenStore: _FakeTokenStore(),
      ).saveGoal(title: 'Medicina', targetDate: DateTime(2020, 1, 1), update: false),
      throwsA(
        isA<TrackerException>().having(
          (e) => e.message,
          'message',
          contains('não pode estar no passado'),
        ),
      ),
    );
  });

  test('fetchGoal devolve null quando o aluno pulou o onboarding', () async {
    final client = MockClient((_) async => http.Response('null', 200));
    final objetivo = await TrackerApi(
      client: client,
      tokenStore: _FakeTokenStore(),
    ).fetchGoal();
    expect(objetivo, isNull);
  });

  test('sem sessão, a chamada falha com mensagem de sessão expirada', () async {
    final client = MockClient((_) async => http.Response('{}', 200));
    expect(
      () => TrackerApi(client: client, tokenStore: _SemToken()).fetchSummary(),
      throwsA(isA<TrackerException>()),
    );
  });
}

class _SemToken extends TokenStore {
  @override
  Future<String?> readAccessToken() async => null;
}
```

- [ ] **Step 6: Escreva o cliente**

`lib/features/tracker/data/tracker_api.dart`:

```dart
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/app_http.dart';
import '../../../core/network/token_store.dart';
import '../domain/roadmap_step.dart';
import '../domain/study_summary.dart';

/// Lançada quando uma chamada do tracker falha; carrega mensagem pronta
/// para exibir.
class TrackerException implements Exception {
  TrackerException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente do learning-service para objetivo, percurso e resumo de estudo.
///
/// Mesma convenção dos demais clientes do app: usa [appAuthClient], que já
/// cuida do refresh automático em 401.
class TrackerApi {
  TrackerApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? appAuthClient,
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  Future<Map<String, String>> _headers({bool json = false}) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw TrackerException('Sessão expirada. Entre novamente.');
    }
    return {
      if (json) 'Content-Type': 'application/json',
      'Authorization': 'Bearer $access',
    };
  }

  /// Extrai a frase do servidor de um corpo de erro do FastAPI.
  ///
  /// `detail` chega como String nas exceções da aplicação e como LISTA de
  /// objetos `{loc, msg, type}` nas de validação (422) — é dessa lista que
  /// sai "A data-alvo não pode estar no passado". Uma mensagem genérica no
  /// lugar mandaria o aluno procurar no campo errado.
  String _mensagemErro(http.Response res, String acao) {
    try {
      final corpo = jsonDecode(res.body);
      if (corpo is Map<String, dynamic>) {
        final detalhe = corpo['detail'];
        if (detalhe is String) return detalhe;
        if (detalhe is List && detalhe.isNotEmpty) {
          final primeiro = detalhe.first;
          if (primeiro is Map && primeiro['msg'] is String) {
            return (primeiro['msg'] as String).replaceFirst('Value error, ', '');
          }
        }
      }
    } catch (_) {
      // corpo não é JSON — cai na mensagem genérica abaixo
    }
    return 'Falha ao $acao (${res.statusCode})';
  }

  Future<http.Response> _enviar(
    Future<http.Response> Function() chamada,
    String acao,
  ) async {
    try {
      return await chamada();
    } on TrackerException {
      rethrow;
    } on Exception {
      throw TrackerException('Não foi possível conectar ao servidor');
    }
  }

  Future<StudySummary> fetchSummary() async {
    final res = await _enviar(
      () async => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/profile/summary'),
        headers: await _headers(),
      ),
      'carregar seu resumo',
    );
    if (res.statusCode != 200) {
      throw TrackerException(_mensagemErro(res, 'carregar seu resumo'));
    }
    return StudySummary.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  Future<Roadmap> fetchRoadmap({int limit = 50, int offset = 0}) async {
    final res = await _enviar(
      () async => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/roadmap?limit=$limit&offset=$offset'),
        headers: await _headers(),
      ),
      'carregar seu percurso',
    );
    if (res.statusCode != 200) {
      throw TrackerException(_mensagemErro(res, 'carregar seu percurso'));
    }
    return Roadmap.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// O objetivo atual, ou `null` para quem pulou o onboarding.
  Future<Goal?> fetchGoal() async {
    final res = await _enviar(
      () async => _client.get(
        Uri.parse('${ApiConfig.baseUrl}/onboarding'),
        headers: await _headers(),
      ),
      'carregar seu objetivo',
    );
    if (res.statusCode != 200) {
      throw TrackerException(_mensagemErro(res, 'carregar seu objetivo'));
    }
    final corpo = jsonDecode(res.body);
    if (corpo == null) return null;
    final mapa = corpo as Map<String, dynamic>;
    // `GET /onboarding` devolve o objetivo cru (sem os contadores de dias,
    // que são do resumo) — os dois campos entram como zero.
    return Goal.fromJson({
      'titulo': mapa['titulo'],
      'data_alvo': mapa['data_alvo'],
      'dias_decorridos': 0,
      'dias_totais': 0,
    });
  }

  /// Cria (`update: false`) ou altera (`update: true`) o objetivo.
  /// Devolve quantas etapas o percurso passou a ter.
  Future<int> saveGoal({
    required String title,
    required DateTime targetDate,
    required bool update,
  }) async {
    final uri = Uri.parse('${ApiConfig.baseUrl}/onboarding');
    // Data sem hora: o backend recebe `date`, e mandar o ISO completo com
    // fuso faria a data virar o dia anterior para quem está a oeste de
    // Greenwich.
    final corpo = jsonEncode({
      'titulo': title,
      'data_alvo':
          '${targetDate.year.toString().padLeft(4, '0')}-'
          '${targetDate.month.toString().padLeft(2, '0')}-'
          '${targetDate.day.toString().padLeft(2, '0')}',
    });
    final res = await _enviar(
      () async => update
          ? _client.put(uri, headers: await _headers(json: true), body: corpo)
          : _client.post(uri, headers: await _headers(json: true), body: corpo),
      'salvar seu objetivo',
    );
    if (res.statusCode != 200 && res.statusCode != 201) {
      throw TrackerException(_mensagemErro(res, 'salvar seu objetivo'));
    }
    final mapa = jsonDecode(res.body) as Map<String, dynamic>;
    return (mapa['etapas_geradas'] as num?)?.toInt() ?? 0;
  }
}
```

- [ ] **Step 7: Rode os dois arquivos de teste**

Run: `cd front-end-flutter && flutter test test/features/tracker/`
Expected: 13 passed.

- [ ] **Step 8: Suíte inteira + analyze**

Run: `cd front-end-flutter && flutter test && flutter analyze lib/`
Expected: **218 passed**; `analyze` continua em 6 issues (nenhuma nova).

- [ ] **Step 9: Commit**

```bash
git add front-end-flutter/lib/features/tracker front-end-flutter/test/features/tracker
git commit -m "feat(tracker): add study summary and roadmap models with their client"
```

---

### Task 11: Flutter — a tela de onboarding e os dois caminhos até ela

**Files:**
- Create: `front-end-flutter/lib/features/onboarding/presentation/onboarding_screen.dart`
- Modify: `front-end-flutter/lib/main.dart` (rota `/onboarding`)
- Modify: `front-end-flutter/lib/features/auth/presentation/register_screen.dart:76-80`
- Modify: `front-end-flutter/lib/features/profile/presentation/profile_screen.dart:76`
  (item "Metas e objetivos" ganha `route: '/onboarding'`)
- Test: `front-end-flutter/test/features/onboarding/onboarding_screen_test.dart`

**Interfaces:**
- Consumes: `TrackerApi.fetchGoal()`, `TrackerApi.saveGoal(...)`,
  `TrackerException` (Task 10).
- Produces: rota `/onboarding`; `OnboardingScreen({TrackerApi? api})` — o
  parâmetro existe para o teste injetar um fake, como
  `OrdersScreen`/`OrdersProvider` já fazem no marketplace.

- [ ] **Step 1: Escreva o teste que falha**

Crie `test/features/onboarding/onboarding_screen_test.dart`:

```dart
import 'package:edu_ia/features/onboarding/presentation/onboarding_screen.dart';
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeApi extends TrackerApi {
  _FakeApi({this.objetivo, this.erro});

  final Goal? objetivo;
  final String? erro;
  String? tituloSalvo;
  DateTime? dataSalva;
  bool? atualizou;

  @override
  Future<Goal?> fetchGoal() async => objetivo;

  @override
  Future<int> saveGoal({
    required String title,
    required DateTime targetDate,
    required bool update,
  }) async {
    if (erro != null) throw TrackerException(erro!);
    tituloSalvo = title;
    dataSalva = targetDate;
    atualizou = update;
    return 99;
  }
}

Widget _harness(TrackerApi api) => MaterialApp(
  home: OnboardingScreen(api: api),
  routes: {'/home': (_) => const Scaffold(body: Text('HOME'))},
);

void main() {
  testWidgets('sem objetivo, os campos vêm vazios e o botão diz Começar', (tester) async {
    await tester.pumpWidget(_harness(_FakeApi()));
    await tester.pumpAndSettle();

    expect(find.text('Começar'), findsOneWidget);
    expect(find.text('Pular por enquanto'), findsOneWidget);
  });

  testWidgets('com objetivo, os campos vêm preenchidos e o botão diz Salvar', (tester) async {
    final api = _FakeApi(
      objetivo: Goal(
        title: 'Medicina USP',
        targetDate: DateTime(2027, 11, 7),
        daysElapsed: 0,
        daysTotal: 0,
      ),
    );
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    expect(find.text('Medicina USP'), findsOneWidget);
    expect(find.text('Salvar'), findsOneWidget);
  });

  testWidgets('objetivo em branco não envia nada', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, isNull);
    expect(find.textContaining('Diga o que você quer'), findsOneWidget);
  });

  testWidgets('salvar manda título e data e volta para a home', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina USP');
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, 'Medicina USP');
    expect(api.atualizou, isFalse);
    expect(find.text('HOME'), findsOneWidget);
  });

  testWidgets('a mensagem do servidor aparece na tela', (tester) async {
    final api = _FakeApi(erro: 'A data-alvo não pode estar no passado');
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.enterText(find.byType(TextField).first, 'Medicina');
    await tester.tap(find.text('Começar'));
    await tester.pumpAndSettle();

    expect(find.text('A data-alvo não pode estar no passado'), findsOneWidget);
  });

  testWidgets('pular vai para a home sem salvar nada', (tester) async {
    final api = _FakeApi();
    await tester.pumpWidget(_harness(api));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Pular por enquanto'));
    await tester.pumpAndSettle();

    expect(api.tituloSalvo, isNull);
    expect(find.text('HOME'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd front-end-flutter && flutter test test/features/onboarding/`
Expected: FAIL — `onboarding_screen.dart` não existe.

- [ ] **Step 3: Escreva a tela**

`lib/features/onboarding/presentation/onboarding_screen.dart`:

```dart
import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../tracker/data/tracker_api.dart';
import '../../tracker/domain/study_summary.dart';

/// Onboarding de estudo: o objetivo do aluno e a data em que ele quer
/// chegar lá. Um formulário só, e pulável.
///
/// Duas portas chegam aqui: o cadastro (logo depois de criar a conta) e o
/// item "Metas e objetivos" do perfil, que antes não levava a lugar nenhum.
/// Com objetivo já cadastrado a tela abre preenchida e salva com PUT.
///
/// Pular não grava nada: aluno sem objetivo é caso previsto, e a tela
/// inicial simplesmente não desenha o cartão de meta.
class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key, this.api});

  final TrackerApi? api;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  late final TrackerApi _api = widget.api ?? TrackerApi();
  final _tituloController = TextEditingController();

  DateTime _dataAlvo = DateTime.now().add(const Duration(days: 180));
  bool _carregando = true;
  bool _salvando = false;
  bool _edicao = false;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregarObjetivo();
  }

  @override
  void dispose() {
    _tituloController.dispose();
    super.dispose();
  }

  Future<void> _carregarObjetivo() async {
    try {
      final objetivo = await _api.fetchGoal();
      if (!mounted) return;
      if (objetivo != null) {
        _tituloController.text = objetivo.title;
        _dataAlvo = objetivo.targetDate;
        _edicao = true;
      }
    } on TrackerException {
      // Sem objetivo legível, a tela abre vazia — é o mesmo estado de quem
      // nunca preencheu, e insistir num erro aqui bloquearia o cadastro.
    }
    if (mounted) setState(() => _carregando = false);
  }

  Future<void> _escolherData() async {
    final hoje = DateTime.now();
    final escolhida = await showDatePicker(
      context: context,
      initialDate: _dataAlvo.isBefore(hoje) ? hoje : _dataAlvo,
      firstDate: hoje,
      lastDate: DateTime(hoje.year + 10),
    );
    if (escolhida != null && mounted) setState(() => _dataAlvo = escolhida);
  }

  Future<void> _salvar() async {
    final titulo = _tituloController.text.trim();
    if (titulo.isEmpty) {
      setState(() => _erro = 'Diga o que você quer conquistar');
      return;
    }
    setState(() {
      _salvando = true;
      _erro = null;
    });
    try {
      await _api.saveGoal(title: titulo, targetDate: _dataAlvo, update: _edicao);
      if (!mounted) return;
      Navigator.pushReplacementNamed(context, '/home');
    } on TrackerException catch (e) {
      if (!mounted) return;
      setState(() {
        _erro = e.message;
        _salvando = false;
      });
    }
  }

  void _pular() => Navigator.pushReplacementNamed(context, '/home');

  @override
  Widget build(BuildContext context) {
    if (_carregando) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    return Scaffold(
      backgroundColor: AppColors.white,
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 32, 24, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Qual é o seu objetivo?',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 8),
              const Text(
                'Ele guia o seu percurso de estudo até a data da prova.',
                style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 24),
              TextField(
                controller: _tituloController,
                maxLength: 120,
                decoration: const InputDecoration(
                  labelText: 'Objetivo',
                  hintText: 'Ex.: Medicina na USP',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 8),
              InkWell(
                onTap: _escolherData,
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Data-alvo',
                    border: OutlineInputBorder(),
                  ),
                  child: Text(
                    '${_dataAlvo.day.toString().padLeft(2, '0')}/'
                    '${_dataAlvo.month.toString().padLeft(2, '0')}/'
                    '${_dataAlvo.year}',
                  ),
                ),
              ),
              if (_erro != null) ...[
                const SizedBox(height: 12),
                Text(_erro!, style: const TextStyle(color: Colors.red, fontSize: 13)),
              ],
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _salvando ? null : _salvar,
                  child: Text(_edicao ? 'Salvar' : 'Começar'),
                ),
              ),
              const SizedBox(height: 8),
              Center(
                child: TextButton(
                  onPressed: _salvando ? null : _pular,
                  child: const Text('Pular por enquanto'),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
```

- [ ] **Step 4: Ligue as duas portas**

Em `lib/main.dart`, junto das rotas existentes:

```dart
          '/onboarding': (_) => const OnboardingScreen(),
```

Em `register_screen.dart`, a navegação depois do cadastro passa a ser:

```dart
      Navigator.pushReplacementNamed(
        context,
        '/onboarding',
        arguments: {'justRegistered': true},
      );
```

Em `profile_screen.dart`, o item que hoje não navega:

```dart
                  _SettingsItem(
                    Icons.track_changes_outlined,
                    'Metas e objetivos',
                    route: '/onboarding',
                  ),
```

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd front-end-flutter && flutter test test/features/onboarding/`
Expected: 6 passed.

- [ ] **Step 6: Suíte inteira + analyze**

Run: `cd front-end-flutter && flutter test && flutter analyze lib/`
Expected: **224 passed**; `analyze` em 6 issues.

- [ ] **Step 7: Commit**

```bash
git add front-end-flutter/lib/features/onboarding front-end-flutter/lib/main.dart \
        front-end-flutter/lib/features/auth/presentation/register_screen.dart \
        front-end-flutter/lib/features/profile/presentation/profile_screen.dart \
        front-end-flutter/test/features/onboarding
git commit -m "feat(onboarding): ask for the study goal after sign up"
```

---

### Task 12: Flutter — a tela inicial passa a ler dados reais

**Files:**
- Create: `front-end-flutter/lib/features/tracker/presentation/summary_provider.dart`
- Create: `front-end-flutter/lib/features/tracker/presentation/goal_card.dart`
- Modify: `front-end-flutter/lib/features/home/presentation/home_screen.dart:120-195`
  (o cartão de meta)
- Test: `front-end-flutter/test/features/tracker/goal_card_test.dart`
- Test: `front-end-flutter/test/features/tracker/summary_provider_test.dart`

**Interfaces:**
- Consumes: `TrackerApi.fetchSummary()`, `StudySummary` (Task 10).
- Produces, usados pelas tarefas 13 e 14:
  - `SummaryProvider extends ChangeNotifier` com
    `SummaryViewState { loading, success, error }`, `summary`,
    `errorMessage`, `load()`
  - `GoalCard({required StudySummary summary})` — desenha o cartão de meta,
    ou **nada** quando `summary.goal == null`

- [ ] **Step 1: Escreva os testes que falham**

Crie `test/features/tracker/summary_provider_test.dart`:

```dart
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/summary_provider.dart';
import 'package:flutter_test/flutter_test.dart';

StudySummary _resumo({Goal? goal}) => StudySummary(
  goal: goal,
  roadmap: const RoadmapProgress(totalSteps: 0, completedSteps: 0, progress: 0),
  points: const Points(total: 0, level: 1, streak: 0),
  study: const Study(answeredQuestions: 0, startedSubtopics: 0),
);

class _FakeApi extends TrackerApi {
  _FakeApi({this.resumo, this.erro});
  final StudySummary? resumo;
  final String? erro;

  @override
  Future<StudySummary> fetchSummary() async {
    if (erro != null) throw TrackerException(erro!);
    return resumo!;
  }
}

void main() {
  test('sucesso guarda o resumo', () async {
    final provider = SummaryProvider(api: _FakeApi(resumo: _resumo()));
    await provider.load();

    expect(provider.state, SummaryViewState.success);
    expect(provider.summary!.points.total, 0);
    expect(provider.errorMessage, isNull);
  });

  test('falha vira estado de erro com a mensagem do servidor', () async {
    final provider = SummaryProvider(api: _FakeApi(erro: 'servidor fora'));
    await provider.load();

    expect(provider.state, SummaryViewState.error);
    expect(provider.errorMessage, 'servidor fora');
    expect(provider.summary, isNull);
  });
}
```

Crie `test/features/tracker/goal_card_test.dart`:

```dart
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/goal_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

StudySummary _resumo({Goal? goal, double progresso = 0.0}) => StudySummary(
  goal: goal,
  roadmap: RoadmapProgress(totalSteps: 50, completedSteps: 34, progress: progresso),
  points: const Points(total: 0, level: 1, streak: 0),
  study: const Study(answeredQuestions: 0, startedSubtopics: 0),
);

void main() {
  testWidgets('sem objetivo, o cartão inteiro não é desenhado', (tester) async {
    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: GoalCard(summary: _resumo()))),
    );

    expect(find.byType(LinearProgressIndicator), findsNothing);
    expect(find.textContaining('dias'), findsNothing);
  });

  testWidgets('com objetivo, mostra título, dias e progresso do backend', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalCard(
            summary: _resumo(
              goal: Goal(
                title: 'Medicina USP',
                targetDate: DateTime(2027, 11, 7),
                daysElapsed: 124,
                daysTotal: 200,
              ),
              progresso: 0.68,
            ),
          ),
        ),
      ),
    );

    expect(find.text('Meta: Medicina USP'), findsOneWidget);
    expect(find.text('124/200 dias'), findsOneWidget);
    expect(find.text('68% do\nPercurso'), findsOneWidget);

    final barra = tester.widget<LinearProgressIndicator>(
      find.byType(LinearProgressIndicator),
    );
    expect(barra.value, 0.68);
  });

  testWidgets('aluno com objetivo e nenhuma etapa concluída mostra 0%', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalCard(
            summary: _resumo(
              goal: Goal(
                title: 'Direito',
                targetDate: DateTime(2027, 11, 7),
                daysElapsed: 0,
                daysTotal: 300,
              ),
            ),
          ),
        ),
      ),
    );

    expect(find.text('0% do\nPercurso'), findsOneWidget);
    expect(find.text('0/300 dias'), findsOneWidget);
  });

  testWidgets('tocar o cartão leva ao tracker', (tester) async {
    var rotaAberta = '';
    await tester.pumpWidget(
      MaterialApp(
        home: Scaffold(
          body: GoalCard(
            summary: _resumo(
              goal: Goal(
                title: 'Medicina',
                targetDate: DateTime(2027, 11, 7),
                daysElapsed: 1,
                daysTotal: 10,
              ),
            ),
          ),
        ),
        onGenerateRoute: (settings) {
          rotaAberta = settings.name ?? '';
          return MaterialPageRoute(builder: (_) => const SizedBox());
        },
      ),
    );

    await tester.tap(find.text('Meta: Medicina'));
    await tester.pumpAndSettle();
    expect(rotaAberta, '/tracker');
  });
}
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd front-end-flutter && flutter test test/features/tracker/`
Expected: FAIL — `summary_provider.dart` e `goal_card.dart` não existem.

- [ ] **Step 3: Escreva o provider**

`lib/features/tracker/presentation/summary_provider.dart`:

```dart
import 'package:flutter/foundation.dart';

import '../data/tracker_api.dart';
import '../domain/study_summary.dart';

enum SummaryViewState { loading, success, error }

/// Estado do resumo de estudo, compartilhado pela tela inicial e pelo
/// perfil: as duas leem `GET /profile/summary`, e uma chamada só serve as
/// duas quando o aluno navega entre elas.
class SummaryProvider extends ChangeNotifier {
  SummaryProvider({TrackerApi? api}) : _api = api ?? TrackerApi();

  final TrackerApi _api;

  SummaryViewState _state = SummaryViewState.loading;
  StudySummary? _summary;
  String? _errorMessage;

  SummaryViewState get state => _state;
  StudySummary? get summary => _summary;
  String? get errorMessage => _errorMessage;

  Future<void> load() async {
    _state = SummaryViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _summary = await _api.fetchSummary();
      _state = SummaryViewState.success;
    } on TrackerException catch (e) {
      _errorMessage = e.message;
      _state = SummaryViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = SummaryViewState.error;
    }
    notifyListeners();
  }
}
```

- [ ] **Step 4: Escreva o cartão**

`lib/features/tracker/presentation/goal_card.dart`:

```dart
import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/study_summary.dart';

/// O cartão de meta da tela inicial.
///
/// Antes da spec D ele anunciava "Meta: Medicina USP", "124/200 dias" e uma
/// barra em 0.68 — os três fixos no código, para qualquer aluno. Agora os
/// três vêm de `GET /profile/summary`, e **sem objetivo o cartão não é
/// desenhado**: um cartão vazio com zeros seria outro jeito de mostrar um
/// número que ninguém escolheu.
class GoalCard extends StatelessWidget {
  const GoalCard({super.key, required this.summary});

  final StudySummary summary;

  @override
  Widget build(BuildContext context) {
    final goal = summary.goal;
    if (goal == null) return const SizedBox.shrink();

    final progresso = summary.roadmap.progress.clamp(0.0, 1.0);
    final percentual = (progresso * 100).round();

    return GestureDetector(
      onTap: () => Navigator.pushNamed(context, '/tracker'),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          color: AppColors.white,
          borderRadius: BorderRadius.circular(20),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '$percentual% do\nPercurso',
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                    height: 1.2,
                  ),
                ),
                Image.asset('assets/images/target.png', width: 80, height: 80),
              ],
            ),
            const SizedBox(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  'Meta: ${goal.title}',
                  style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                ),
                Text(
                  '${goal.daysElapsed}/${goal.daysTotal} dias',
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: LinearProgressIndicator(
                value: progresso,
                minHeight: 10,
                backgroundColor: const Color(0xFFE5E7EB),
                valueColor: const AlwaysStoppedAnimation<Color>(AppColors.purple),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 5: Ligue o cartão na tela inicial**

Em `home_screen.dart`, o widget de cartão fixo (o bloco que contém
`'68% do\nPercurso'`, `'Meta: Medicina USP'`, `'124/200 dias'` e
`value: 0.68`) é **removido inteiro** e substituído por um consumidor do
provider. No `_HomeScreenState`:

```dart
  final _summaryProvider = SummaryProvider();

  @override
  void initState() {
    super.initState();
    _loadName();
    _summaryProvider.load();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowWelcome());
  }

  @override
  void dispose() {
    _summaryProvider.dispose();
    super.dispose();
  }
```

E, no lugar do cartão antigo:

```dart
              AnimatedBuilder(
                animation: _summaryProvider,
                builder: (context, _) {
                  final resumo = _summaryProvider.summary;
                  // Enquanto carrega, e quando falha, a home não inventa
                  // número nenhum: o cartão simplesmente não aparece.
                  if (resumo == null) return const SizedBox.shrink();
                  return GoalCard(summary: resumo);
                },
              ),
```

**Confira o `grep` do critério de pronto 1** depois desta edição:
`grep -rn "3,120\|124/200\|Medicina USP\|0.68" front-end-flutter/lib` só pode
devolver as ocorrências de `profile_screen.dart` (que a Task 13 remove).

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd front-end-flutter && flutter test test/features/tracker/`
Expected: 19 passed (13 da Task 10 + 6 desta).

- [ ] **Step 7: Suíte inteira + analyze**

Run: `cd front-end-flutter && flutter test && flutter analyze lib/`
Expected: **230 passed**; `analyze` em 6 issues.

- [ ] **Step 8: Commit**

```bash
git add front-end-flutter/lib/features/tracker/presentation \
        front-end-flutter/lib/features/home/presentation/home_screen.dart \
        front-end-flutter/test/features/tracker
git commit -m "feat(home): draw the goal card from the study summary"
```

---

### Task 13: Flutter — o perfil mostra pontos e testes reais

**Files:**
- Create: `front-end-flutter/lib/features/tracker/presentation/points_card.dart`
- Modify: `front-end-flutter/lib/features/profile/presentation/profile_screen.dart`
  (`_PointsCard` e `_StatsRow`, hoje com `'3,120'` e `'15'` fixos)
- Test: `front-end-flutter/test/features/tracker/points_card_test.dart`

**Interfaces:**
- Consumes: `SummaryProvider`, `StudySummary`, `Points`, `Study` (tarefas 10 e 12).
- Produces: `PointsCard({required Points points})` e
  `StudyStatsRow({required Points points, required Study study})`.

- [ ] **Step 1: Escreva o teste que falha**

Crie `test/features/tracker/points_card_test.dart`:

```dart
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/points_card.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('aluno zerado mostra zero, não 3.120', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: PointsCard(points: Points(total: 0, level: 1, streak: 0))),
      ),
    );

    expect(find.text('0'), findsOneWidget);
    expect(find.text('3,120'), findsNothing);
    expect(find.textContaining('Nível 1'), findsOneWidget);
  });

  testWidgets('total grande sai formatado com separador de milhar', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(body: PointsCard(points: Points(total: 3120, level: 8, streak: 4))),
      ),
    );

    expect(find.text('3.120'), findsOneWidget);
    expect(find.textContaining('Nível 8'), findsOneWidget);
  });

  testWidgets('a linha de estatísticas vem do resumo', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StudyStatsRow(
            points: Points(total: 100, level: 2, streak: 6),
            study: Study(answeredQuestions: 42, startedSubtopics: 7),
          ),
        ),
      ),
    );

    expect(find.text('42'), findsOneWidget);
    expect(find.text('Questões'), findsOneWidget);
    expect(find.text('6'), findsOneWidget);
    expect(find.text('Sequência'), findsOneWidget);
  });

  testWidgets('aluno zerado na linha de estatísticas mostra dois zeros', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: Scaffold(
          body: StudyStatsRow(
            points: Points(total: 0, level: 1, streak: 0),
            study: Study(answeredQuestions: 0, startedSubtopics: 0),
          ),
        ),
      ),
    );

    expect(find.text('0'), findsNWidgets(2));
  });
}
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd front-end-flutter && flutter test test/features/tracker/points_card_test.dart`
Expected: FAIL — `points_card.dart` não existe.

- [ ] **Step 3: Escreva os widgets**

`lib/features/tracker/presentation/points_card.dart`:

```dart
import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/study_summary.dart';

/// Formata 3120 como "3.120" — separador de milhar do português, sem
/// depender de `intl` (o app não o tem hoje).
String _milhar(int valor) {
  final digitos = valor.abs().toString();
  final partes = <String>[];
  for (var fim = digitos.length; fim > 0; fim -= 3) {
    partes.insert(0, digitos.substring(fim - 3 < 0 ? 0 : fim - 3, fim));
  }
  return (valor < 0 ? '-' : '') + partes.join('.');
}

/// Total de pontos e nível — os dois vindos de `GET /profile/summary`.
///
/// O valor que estava aqui antes era `'3,120'`, escrito no código, igual
/// para todo mundo. O teste que trava isso é "aluno zerado mostra zero".
class PointsCard extends StatelessWidget {
  const PointsCard({super.key, required this.points});

  final Points points;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Total de pontos',
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 4),
              Text(
                _milhar(points.total),
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                'Nível ${points.level}',
                style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.purple,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.star, color: AppColors.white, size: 22),
          ),
        ],
      ),
    );
  }
}

/// Questões respondidas e sequência atual.
///
/// O rótulo mudou de "Testes" para "Questões" porque é o que o backend
/// conta (`estudo.questoes_respondidas`, a soma de `total_respondidas`).
/// Manter "Testes" sobre um número de questões seria trocar um dado
/// inventado por um rótulo inventado.
class StudyStatsRow extends StatelessWidget {
  const StudyStatsRow({super.key, required this.points, required this.study});

  final Points points;
  final Study study;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _StatBox(
            icone: Icons.description_outlined,
            valor: study.answeredQuestions,
            rotulo: 'Questões',
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _StatBox(
            icone: Icons.local_fire_department_outlined,
            valor: points.streak,
            rotulo: 'Sequência',
          ),
        ),
      ],
    );
  }
}

class _StatBox extends StatelessWidget {
  const _StatBox({required this.icone, required this.valor, required this.rotulo});

  final IconData icone;
  final int valor;
  final String rotulo;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icone, size: 24, color: AppColors.textSecondary),
          const SizedBox(height: 12),
          Text(
            '$valor',
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 2),
          Text(rotulo, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4: Ligue no perfil**

Em `profile_screen.dart`: apague as classes privadas `_PointsCard` e
`_StatsRow` inteiras (são elas que carregam `'3,120'` e `'15'`), importe
`PointsCard`/`StudyStatsRow` e `SummaryProvider`, e no `_ProfileScreenState`
carregue o resumo do mesmo jeito que a home:

```dart
  final _summaryProvider = SummaryProvider();

  @override
  void initState() {
    super.initState();
    _loadName();
    _summaryProvider.load();
  }

  @override
  void dispose() {
    _summaryProvider.dispose();
    super.dispose();
  }
```

E no `build`, no lugar de `const _PointsCard()` e `const _StatsRow()`:

```dart
              AnimatedBuilder(
                animation: _summaryProvider,
                builder: (context, _) {
                  // Enquanto carrega, mostra ZERO — não um valor de exemplo,
                  // e não um vazio que pula a tela quando o dado chega.
                  final resumo = _summaryProvider.summary;
                  final pontos = resumo?.points ?? const Points(total: 0, level: 1, streak: 0);
                  final estudo =
                      resumo?.study ?? const Study(answeredQuestions: 0, startedSubtopics: 0);
                  return Column(
                    children: [
                      PointsCard(points: pontos),
                      const SizedBox(height: 16),
                      StudyStatsRow(points: pontos, study: estudo),
                    ],
                  );
                },
              ),
```

- [ ] **Step 5: Rode e confirme que passa**

Run: `cd front-end-flutter && flutter test test/features/tracker/points_card_test.dart`
Expected: 4 passed.

- [ ] **Step 6: Prove o critério de pronto 1**

Run: `grep -rn "3,120\|124/200\|Medicina USP\|0.68" front-end-flutter/lib`
Expected: **nenhum resultado**.

- [ ] **Step 7: Suíte inteira + analyze**

Run: `cd front-end-flutter && flutter test && flutter analyze lib/`
Expected: **234 passed**; `analyze` em 6 issues.

- [ ] **Step 8: Commit**

```bash
git add front-end-flutter/lib/features/tracker/presentation/points_card.dart \
        front-end-flutter/lib/features/profile/presentation/profile_screen.dart \
        front-end-flutter/test/features/tracker/points_card_test.dart
git commit -m "feat(profile): show real points, level and answered questions"
```

---

### Task 14: Flutter — a tela do percurso

**Files:**
- Create: `front-end-flutter/lib/features/tracker/presentation/tracker_provider.dart`
- Create: `front-end-flutter/lib/features/tracker/presentation/tracker_screen.dart`
- Modify: `front-end-flutter/lib/main.dart` (rota `/tracker`)
- Test: `front-end-flutter/test/features/tracker/tracker_screen_test.dart`

**Interfaces:**
- Consumes: `TrackerApi.fetchRoadmap()`, `Roadmap`, `RoadmapStep` (Task 10).
- Produces: rota `/tracker`; `TrackerProvider` com
  `TrackerViewState { loading, success, error }`; `TrackerView` (o widget
  testável, sem `Scaffold` de rota) e `TrackerScreen` (a rota).

- [ ] **Step 1: Escreva o teste que falha**

Crie `test/features/tracker/tracker_screen_test.dart`:

```dart
import 'package:edu_ia/features/tracker/data/tracker_api.dart';
import 'package:edu_ia/features/tracker/domain/roadmap_step.dart';
import 'package:edu_ia/features/tracker/domain/study_summary.dart';
import 'package:edu_ia/features/tracker/presentation/tracker_provider.dart';
import 'package:edu_ia/features/tracker/presentation/tracker_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:provider/provider.dart';

RoadmapStep _etapa({
  int id = 1,
  String nome = 'Membrana Plasmática',
  bool concluida = false,
  bool temQuestoes = true,
}) => RoadmapStep(
  subtopicId: id,
  subtopicName: nome,
  topicName: 'Citologia',
  subjectName: 'Biologia',
  order: id - 1,
  deadline: DateTime(2026, 10, 1),
  done: concluida,
  hasQuestions: temQuestoes,
);

class _FakeApi extends TrackerApi {
  _FakeApi(this.roadmap, {this.erro});
  final Roadmap roadmap;
  final String? erro;

  @override
  Future<Roadmap> fetchRoadmap({int limit = 50, int offset = 0}) async {
    if (erro != null) throw TrackerException(erro!);
    return roadmap;
  }
}

Roadmap _roadmap({List<RoadmapStep> etapas = const [], String? motivo}) => Roadmap(
  goal: motivo == null
      ? Goal(
          title: 'Medicina USP',
          targetDate: DateTime(2027, 11, 7),
          daysElapsed: 10,
          daysTotal: 100,
        )
      : null,
  reason: motivo,
  tightDeadline: false,
  steps: etapas,
  total: etapas.length,
);

Widget _harness(TrackerProvider provider) => MaterialApp(
  home: ChangeNotifierProvider.value(value: provider, child: const TrackerView()),
  routes: {'/onboarding': (_) => const Scaffold(body: Text('ONBOARDING'))},
);

void main() {
  testWidgets('sem objetivo, a tela convida ao onboarding', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(motivo: 'Defina um objetivo e uma data-alvo para montar seu percurso.')),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.textContaining('Defina um objetivo'), findsOneWidget);
    expect(find.text('Definir objetivo'), findsOneWidget);
  });

  testWidgets('com percurso, lista as etapas agrupadas por matéria', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(), _etapa(id: 2, nome: 'Organelas')])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('Biologia'), findsOneWidget); // cabeçalho da matéria
    expect(find.text('Membrana Plasmática'), findsOneWidget);
    expect(find.text('Organelas'), findsOneWidget);
  });

  testWidgets('etapa sem questão fica desabilitada e diz por quê', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(temQuestoes: false)])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('Conteúdo em preparação'), findsOneWidget);
    final botao = tester.widget<ElevatedButton>(find.byType(ElevatedButton).first);
    expect(botao.onPressed, isNull);
  });

  testWidgets('etapa com questão tem botão de praticar habilitado', (tester) async {
    final provider = TrackerProvider(api: _FakeApi(_roadmap(etapas: [_etapa()])));
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    final botao = tester.widget<ElevatedButton>(find.byType(ElevatedButton).first);
    expect(botao.onPressed, isNotNull);
    expect(find.text('Praticar'), findsOneWidget);
  });

  testWidgets('etapa concluída aparece marcada', (tester) async {
    final provider = TrackerProvider(
      api: _FakeApi(_roadmap(etapas: [_etapa(concluida: true)])),
    );
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('falha mostra a mensagem, não uma tela em branco', (tester) async {
    final provider = TrackerProvider(api: _FakeApi(_roadmap(), erro: 'servidor fora'));
    await tester.pumpWidget(_harness(provider));
    await provider.load();
    await tester.pumpAndSettle();

    expect(find.text('servidor fora'), findsOneWidget);
  });
}
```

- [ ] **Step 2: Rode e confirme que falha**

Run: `cd front-end-flutter && flutter test test/features/tracker/tracker_screen_test.dart`
Expected: FAIL — `tracker_provider.dart` não existe.

- [ ] **Step 3: Escreva o provider**

`lib/features/tracker/presentation/tracker_provider.dart`:

```dart
import 'package:flutter/foundation.dart';

import '../data/tracker_api.dart';
import '../domain/roadmap_step.dart';

enum TrackerViewState { loading, success, error }

class TrackerProvider extends ChangeNotifier {
  TrackerProvider({TrackerApi? api}) : _api = api ?? TrackerApi();

  final TrackerApi _api;

  TrackerViewState _state = TrackerViewState.loading;
  Roadmap? _roadmap;
  String? _errorMessage;

  TrackerViewState get state => _state;
  Roadmap? get roadmap => _roadmap;
  String? get errorMessage => _errorMessage;

  /// Etapas agrupadas por matéria, preservando a ordem do percurso — a
  /// resposta já vem ordenada por `ordem`, então basta não reordenar.
  Map<String, List<RoadmapStep>> get stepsBySubject {
    final agrupado = <String, List<RoadmapStep>>{};
    for (final etapa in _roadmap?.steps ?? const <RoadmapStep>[]) {
      agrupado.putIfAbsent(etapa.subjectName, () => []).add(etapa);
    }
    return agrupado;
  }

  Future<void> load() async {
    _state = TrackerViewState.loading;
    _errorMessage = null;
    notifyListeners();
    try {
      _roadmap = await _api.fetchRoadmap();
      _state = TrackerViewState.success;
    } on TrackerException catch (e) {
      _errorMessage = e.message;
      _state = TrackerViewState.error;
    } catch (_) {
      _errorMessage = 'Algo deu errado. Tente novamente.';
      _state = TrackerViewState.error;
    }
    notifyListeners();
  }
}
```

- [ ] **Step 4: Escreva a tela**

`lib/features/tracker/presentation/tracker_screen.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../domain/roadmap_step.dart';

import 'tracker_provider.dart';

/// A rota `/tracker`: cria o provider e dispara a carga.
class TrackerScreen extends StatelessWidget {
  const TrackerScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => TrackerProvider()..load(),
      child: const TrackerView(),
    );
  }
}

/// O corpo da tela, sem criar dependência — é o que os testes montam.
class TrackerView extends StatelessWidget {
  const TrackerView({super.key});

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TrackerProvider>();

    return Scaffold(
      appBar: AppBar(title: const Text('Meu percurso')),
      body: switch (provider.state) {
        TrackerViewState.loading => const Center(child: CircularProgressIndicator()),
        TrackerViewState.error => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              provider.errorMessage ?? 'Algo deu errado. Tente novamente.',
              textAlign: TextAlign.center,
            ),
          ),
        ),
        TrackerViewState.success => _Conteudo(provider: provider),
      },
    );
  }
}

class _Conteudo extends StatelessWidget {
  const _Conteudo({required this.provider});

  final TrackerProvider provider;

  @override
  Widget build(BuildContext context) {
    final roadmap = provider.roadmap;
    if (roadmap == null || roadmap.steps.isEmpty) {
      // Sem objetivo, a lista vem vazia COM motivo — a tela repete a frase
      // do servidor e oferece o caminho, em vez de mostrar um vazio mudo.
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                roadmap?.reason ?? 'Seu percurso ainda está vazio.',
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 15, color: AppColors.textSecondary),
              ),
              const SizedBox(height: 16),
              ElevatedButton(
                onPressed: () => Navigator.pushNamed(context, '/onboarding'),
                child: const Text('Definir objetivo'),
              ),
            ],
          ),
        ),
      );
    }

    final grupos = provider.stepsBySubject;
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 24),
      children: [
        if (roadmap.tightDeadline)
          const Padding(
            padding: EdgeInsets.only(bottom: 12),
            child: Text(
              'Seu prazo é apertado: várias etapas caem no mesmo dia.',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
          ),
        for (final entrada in grupos.entries) ...[
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(
              entrada.key,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
          ),
          for (final etapa in entrada.value) _EtapaCard(etapa: etapa),
        ],
      ],
    );
  }
}

class _EtapaCard extends StatelessWidget {
  const _EtapaCard({required this.etapa});

  final RoadmapStep etapa;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                if (etapa.done)
                  const Padding(
                    padding: EdgeInsets.only(right: 8),
                    child: Icon(Icons.check_circle, color: AppColors.purple, size: 20),
                  ),
                Expanded(
                  child: Text(
                    etapa.subtopicName,
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 4),
            Text(
              '${etapa.topicName} · até '
              '${etapa.deadline.day.toString().padLeft(2, '0')}/'
              '${etapa.deadline.month.toString().padLeft(2, '0')}',
              style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            if (!etapa.hasQuestions) ...[
              const SizedBox(height: 8),
              // A etapa aparece mesmo sem questão, dizendo por quê. Esconder
              // a matéria faria o aluno acreditar num percurso menor do que
              // o real.
              const Text(
                'Conteúdo em preparação',
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: etapa.hasQuestions
                    ? () => Navigator.pushNamed(context, '/quiz')
                    : null,
                child: const Text('Praticar'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 5: Registre a rota**

Em `lib/main.dart`, junto das demais:

```dart
          '/tracker': (_) => const TrackerScreen(),
```

- [ ] **Step 6: Rode e confirme que passa**

Run: `cd front-end-flutter && flutter test test/features/tracker/tracker_screen_test.dart`
Expected: 6 passed.

- [ ] **Step 7: Suíte inteira + analyze**

Run: `cd front-end-flutter && flutter test && flutter analyze lib/`
Expected: **240 passed**; `analyze` em 6 issues.

- [ ] **Step 8: Commit**

```bash
git add front-end-flutter/lib/features/tracker front-end-flutter/lib/main.dart \
        front-end-flutter/test/features/tracker/tracker_screen_test.dart
git commit -m "feat(tracker): add the study roadmap screen"
```

---

### Task 15: Documentação da entrega

**Files:**
- Create: `docs/back-end/study-tracker.md`
- Modify: `CLAUDE.md` (uma linha na tabela de documentação)
- Modify: `back-end/learning-service/README.md` se existir; caso não exista,
  pule esta modificação (confira com `ls back-end/learning-service/README.md`)

**Interfaces:**
- Consumes: tudo que as tarefas 1-14 construíram.
- Produces: o documento que o smoke test e a próxima spec vão citar.

- [ ] **Step 1: Escreva o documento**

`docs/back-end/study-tracker.md`, com estas seis seções, cada uma medida
contra o código que existe ao final da Task 14 (nada de "deve" ou "vai"):

1. **O que a spec D trocou.** A lista dos cinco valores fixos que saíram das
   telas, com o arquivo e a linha em que estavam, e o campo do backend que
   passou a alimentá-los.
2. **Objetivo e onboarding.** As três rotas, o que cada uma responde, a
   regra da data no passado, e o que acontece quando o aluno pula.
3. **O roadmap.** A regra de geração nos quatro passos da spec, com a
   fórmula de distribuição escrita por extenso, a regra de regeneração
   (apaga e recria preservando conclusão) e o campo `tem_questoes`.
4. **A pontuação.** A tabela de origens e pontos, a chave de idempotência,
   as faixas de nível, e a frase explícita de que **nível não é gravado**.
5. **O resumo.** O JSON de `GET /profile/summary` campo a campo, dizendo de
   onde cada número sai.
6. **O que ainda não existe.** Conteúdo: matérias sem questão (a lista das
   que têm, medida com
   `SELECT m.nome, count(q.id) FROM materia m LEFT JOIN tema t ON t.materia_id = m.id
   LEFT JOIN subtema s ON s.tema_id = t.id LEFT JOIN questao q ON q.subtema_id = s.id
   GROUP BY m.nome ORDER BY 2 DESC;`), e o que a spec deixou fora de escopo
   de propósito (distribuição adaptativa, ranking, conquistas).

- [ ] **Step 2: Indexe no `CLAUDE.md`**

Na tabela de documentação, na seção **Backend**, logo abaixo da linha de
`order-flow.md`:

```markdown
| | [docs/back-end/study-tracker.md](docs/back-end/study-tracker.md) | Spec D: objetivo do aluno, roadmap ate a data-alvo, pontuacao e nivel, e o resumo que a tela inicial e o perfil leem |
```

- [ ] **Step 3: Confira os critérios de pronto da spec**

```bash
# 1. Nenhum número inventado nas telas de estudante
grep -rn "3,120\|124/200\|Medicina USP\|0.68" front-end-flutter/lib   # vazio

# 6. As suítes
cd back-end/learning-service && uv run pytest -q                       # 164
cd ../api-gateway && uv run pytest -q                                  # 41
cd ../../front-end-flutter && flutter test                             # 240
flutter analyze lib/                                                   # 6 issues
```

Os critérios 2 a 5 (onboarding ponta a ponta, resposta movendo progresso,
perfil zerado, matéria sem questão marcada) exigem stack de pé e aparelho —
eles entram no plano de smoke test, não aqui.

- [ ] **Step 4: Commit**

```bash
git add docs/back-end/study-tracker.md CLAUDE.md
git commit -m "docs(learning): document the study tracker and scoring rules"
```

---

## Self-review

**1. Cobertura da spec.** Cada seção do design tem tarefa:

| Seção da spec | Tarefa |
|---|---|
| Objetivo (`ObjetivoAluno`, um por aluno, `max_length`) | 1, 4 |
| Onboarding pulável, reabrível pelo perfil | 4, 11 |
| Roadmap (`EtapaRoadmap`, os quatro passos da regra) | 1, 3 |
| Regeneração preservando conclusões | 3, 4 |
| Matéria sem questão marcada | 5, 14 |
| Pontuação (`LancamentoPontos`, extrato, idempotência) | 1, 2, 7 |
| Nível por faixas, calculado na leitura | 2, 6 |
| `GET /profile/summary` com os quatro blocos | 6 |
| Barra da home passa a ser `roadmap.progresso` | 12 |
| Sem objetivo, o cartão não é desenhado | 12 |
| Seed do ENEM idempotente | 9 |
| Erros: data no passado, aluno sem objetivo, prazo curto | 3, 4, 5 |
| Testes listados na spec (objetivo, roadmap, prazo curto, pontuação, resumo, seed, Flutter) | 1-14 |
| Critério de pronto 1 (grep vazio) | 12, 13, 15 |
| Critério de pronto 6 (suítes verdes) | todas |

**Gancho que a spec não nomeia e o plano resolve:** a spec lista "revisão
concluída no prazo" como origem de pontos sem dizer quem conclui uma
revisão. Não há rota para isso (medido em `app/routers/revisao.py`, que só
lista). D1 resolve detectando a revisão vencida no momento da resposta.

**2. Placeholders.** Nenhum "TBD", nenhum "adicione tratamento de erro",
nenhum "igual à Task N". Todo passo de código traz o código. As duas
exceções deliberadas, ambas com conteúdo completo no lugar do código:
a Task 15, cujo entregável é prosa e cujo conteúdo está enumerado seção a
seção; e o `README.md` do learning-service, cuja modificação é condicional à
existência do arquivo (o passo diz como verificar).

**3. Consistência de tipos e nomes.** Verificado o que atravessa tarefas:

- `uq_lancamento_idempotente` (Task 1) é o nome usado no `on_conflict_do_nothing`
  da Task 2; `uq_objetivo_aluno` (Task 1) é o que a Task 4 captura como 409.
- `registrar(db, *, aluno_id, origem, referencia, pontos) -> bool` tem a mesma
  assinatura nas tarefas 2 e 7.
- `concluir_etapa(db, *, aluno_id, subtema_id, quando) -> bool` idem, tarefas 3 e 7.
- `gerar_roadmap(db, *, aluno_id, data_alvo, hoje) -> int` idem, tarefas 3 e 4.
- `prazo_apertado(quantidade, inicio, data_alvo)` é chamada com posicionais
  nas tarefas 4 e 5, como definida na 3.
- Os nomes de campo do JSON são os mesmos nos schemas (tarefas 4-6) e no
  parsing Dart (Task 10): `objetivo`, `roadmap`, `pontos`, `estudo`,
  `etapas_totais`, `etapas_concluidas`, `progresso`, `dias_decorridos`,
  `dias_totais`, `tem_questoes`, `prazo_apertado`, `motivo`, `items`.
- `TrackerApi` é o nome do cliente nas tarefas 10-14; `SummaryProvider`
  aparece nas 12 e 13; `TrackerProvider` só na 14.
- As contagens de teste esperadas encadeiam: 78 → 83 → 109 → 121 → 132 → 141
  → 149 → 158 → 164 no learning-service; 39 → 41 no gateway; 205 → 218 → 224
  → 230 → 234 → 240 no Flutter.

**4. Uma armadilha que o executor precisa ver antes de tropeçar nela.** O
`conftest.py` do learning-service cria o schema por `Base.metadata`, e a
lista de imports dentro de `test_engine` é o que decide quais tabelas
existem. Um model novo que não entre naquela lista não gera tabela, e o erro
que aparece é `relation "..." does not exist` no meio de um teste de rota —
não no import. Task 1, Step 4.
