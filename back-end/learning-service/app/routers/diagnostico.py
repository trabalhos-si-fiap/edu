from collections import defaultdict

from edu_common.contracts import DiagnosticCompleted
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_student_id
from app.events.publisher import publish_event
from app.models.progresso import AlunoTemaProgresso
from app.models.questao import Questao
from app.models.resposta import DiagnosticoResposta
from app.models.subtema import Subtema, Tema
from app.schemas.diagnostico import (
    DiagnosticoResultado,
    QuestaoContextoOut,
    RecomendacaoConteudoOut,
    RespostaDiagnosticoIn,
    SubtemaAvaliadoOut,
    SubtemaRelacionadoOut,
    TemaResumoOut,
)
from app.services.decisao import (
    LIMIAR_DOMINIO_SUBTEMA,
    AcaoTema,
    ClassificacaoSubtema,
    classificar_subtema,
    decidir_acao_tema,
)
from app.services.dominio import calcular_dominio, calcular_dominio_tema
from app.services.navegacao_tema import buscar_proximo_tema, buscar_tema_anterior
from app.services.recomendacao_semantica import subtemas_relacionados
from app.services.sm2 import atualizar_revisao
from app.services.tutor_llm import gerar_mensagem_fallback, gerar_mensagem_tutor

router = APIRouter(prefix="/diagnostic", tags=["diagnostico"])


@router.post("/answer", response_model=DiagnosticoResultado)
async def responder_diagnostico(
    payload: RespostaDiagnosticoIn,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    tema_result = await db.execute(select(Tema).where(Tema.id == payload.tema_id))
    tema = tema_result.scalar_one_or_none()
    if not tema:
        raise HTTPException(404, "Tema não encontrado")

    questao_ids = [r.questao_id for r in payload.respostas]
    # O join em Subtema amarra cada questão ao `payload.tema_id`. Sem ele,
    # `Questao.id.in_(...)` aceitava qualquer id existente e o laço abaixo
    # gravava um `DiagnosticoResposta` para ele — que é exatamente a linha
    # que `GET /diagnostic/questions/{id}/context` checa antes de liberar o
    # gabarito. Duas requisições e o aluno lia a resposta certa de qualquer
    # questão do banco. Ids fora do tema simplesmente não entram no dict e
    # caem no `continue` do laço; se nenhum sobrar, a rota devolve o 400 de
    # "nenhuma resposta válida".
    result = await db.execute(
        select(Questao)
        .join(Subtema, Questao.subtema_id == Subtema.id)
        .where(Questao.id.in_(questao_ids), Subtema.tema_id == payload.tema_id)
    )
    questoes = {q.id: q for q in result.scalars().all()}

    # O questionário de 15 perguntas cobre vários subtemas do tema (ex:
    # Membrana, Organelas, Metabolismo, Núcleo, dentro de Citologia) —
    # agrupamos as respostas por subtema para avaliar cada parte
    # separadamente antes de agregar no resultado do tema como um todo.
    respostas_por_subtema: dict[int, list[tuple[bool, int]]] = defaultdict(list)
    for r in payload.respostas:
        questao = questoes.get(r.questao_id)
        if not questao:
            continue  # ignora ids que não existem/não pertencem a nenhum subtema válido
        acertou = r.alternativa_escolhida == questao.gabarito
        respostas_por_subtema[questao.subtema_id].append((acertou, questao.nivel_dificuldade))

        # Persiste a resposta individual — é o que permite ao Chatbot
        # Service confirmar depois "o aluno já respondeu essa questão"
        # antes de expor o gabarito na explicação por IA (ver
        # GET /diagnostic/questions/{id}/context).
        db.add(
            DiagnosticoResposta(
                aluno_id=aluno_id,
                questao_id=r.questao_id,
                alternativa_escolhida=r.alternativa_escolhida,
                acertou=acertou,
            )
        )

    if not respostas_por_subtema:
        raise HTTPException(400, "Nenhuma resposta válida foi enviada")

    subtemas_result = await db.execute(
        select(Subtema).where(Subtema.id.in_(respostas_por_subtema.keys()))
    )
    subtemas_por_id = {s.id: s for s in subtemas_result.scalars().all()}

    dominios_por_subtema: dict[int, tuple[float, int]] = {}
    subtemas_avaliados: list[SubtemaAvaliadoOut] = []
    recomendacoes: list[RecomendacaoConteudoOut] = []

    for subtema_id, respostas in respostas_por_subtema.items():
        dominio = calcular_dominio(respostas)
        dominios_por_subtema[subtema_id] = (dominio, len(respostas))

        # Atualiza (ou cria) o progresso do aluno neste subtema. Isso roda
        # SEMPRE, para todo subtema respondido — a repetição espaçada não
        # depende do resultado geral do tema (estudar/avançar/retroceder).
        progresso_result = await db.execute(
            select(AlunoTemaProgresso).where(
                AlunoTemaProgresso.aluno_id == aluno_id,
                AlunoTemaProgresso.subtema_id == subtema_id,
            )
        )
        progresso = progresso_result.scalar_one_or_none()
        intervalo_atual = progresso.intervalo_dias if progresso else 1.0
        streak_atual = progresso.streak_acertos if progresso else 0

        novo_intervalo, novo_streak, proxima_revisao = atualizar_revisao(
            dominio, intervalo_atual, streak_atual
        )

        if progresso:
            progresso.nivel_dominio = dominio
            progresso.intervalo_dias = novo_intervalo
            progresso.streak_acertos = novo_streak
            progresso.proxima_revisao = proxima_revisao
            progresso.total_respondidas += len(respostas)
        else:
            progresso = AlunoTemaProgresso(
                aluno_id=aluno_id,
                subtema_id=subtema_id,
                nivel_dominio=dominio,
                intervalo_dias=novo_intervalo,
                streak_acertos=novo_streak,
                proxima_revisao=proxima_revisao,
                total_respondidas=len(respostas),
            )
            db.add(progresso)

        classificacao = classificar_subtema(dominio)
        subtema = subtemas_por_id[subtema_id]

        subtemas_avaliados.append(
            SubtemaAvaliadoOut(
                subtema_id=subtema_id,
                nome=subtema.nome,
                dominio=dominio,
                classificacao=classificacao.value,
                proxima_revisao=proxima_revisao,
            )
        )

        # Recomendação de conteúdo gratuito para qualquer subtema ainda não
        # dominado — independente da ação geral decidida para o tema.
        if dominio < LIMIAR_DOMINIO_SUBTEMA:
            video_url = (
                subtema.videoaula_base_url
                if classificacao == ClassificacaoSubtema.ESTUDAR_DO_ZERO
                else subtema.videoaula_revisao_url
            )

            # Reforço cruzado via IA (embeddings + NearestNeighbors) só
            # para o caso mais crítico (estudar_do_zero) — evita custo de
            # inferência desnecessário quando o aluno só precisa de uma
            # revisão leve (classificação "revisar").
            #
            # IMPORTANTE (achado testando de verdade, não uma precaução
            # teórica): se o modelo de embeddings falhar ao carregar (sem
            # internet na primeira execução, timeout, etc.), isso NUNCA
            # pode derrubar o diagnóstico inteiro — é só um enriquecimento
            # opcional, não o núcleo da funcionalidade (nota, SM-2 e
            # mensagem do tutor continuam funcionando normalmente).
            relacionados_out: list[SubtemaRelacionadoOut] = []
            if classificacao == ClassificacaoSubtema.ESTUDAR_DO_ZERO:
                try:
                    relacionados = await subtemas_relacionados(db, subtema_id, k=2)
                    relacionados_out = [
                        SubtemaRelacionadoOut(subtema_id=sid, nome=nome, similaridade=sim)
                        for sid, nome, sim in relacionados
                    ]
                except Exception:
                    relacionados_out = []

            recomendacoes.append(
                RecomendacaoConteudoOut(
                    subtema_id=subtema_id,
                    nome=subtema.nome,
                    motivo=classificacao.value,
                    video_url=video_url,
                    subtemas_relacionados=relacionados_out,
                )
            )

        await publish_event(
            "revision.scheduled",
            {
                "aluno_id": str(aluno_id),
                "subtema_id": subtema_id,
                "proxima_revisao": proxima_revisao.isoformat(),
            },
        )

    dominio_tema = calcular_dominio_tema(dominios_por_subtema)

    tema_anterior = await buscar_tema_anterior(db, tema)
    tema_proximo = await buscar_proximo_tema(db, tema)

    acao = decidir_acao_tema(dominio_tema, existe_tema_anterior=tema_anterior is not None)

    tema_recomendado = None
    if acao == AcaoTema.RETROCEDER and tema_anterior:
        tema_recomendado = TemaResumoOut(id=tema_anterior.id, nome=tema_anterior.nome)
    elif acao == AcaoTema.AVANCAR and tema_proximo:
        tema_recomendado = TemaResumoOut(id=tema_proximo.id, nome=tema_proximo.nome)
        # Se acao == AVANCAR mas tema_proximo é None, o aluno concluiu o
        # último tema da matéria — tema_recomendado fica None de propósito;
        # o Flutter pode interpretar isso como "trilha concluída".

    await db.commit()

    # Payload montado pela definição compartilhada em edu-common, não por um
    # dict literal: as suítes de notification e analytics constroem seus
    # fixtures a partir da MESMA classe, então renomear um campo lá quebra os
    # dois consumidores em vez de passar despercebido (ver contracts.py).
    await publish_event(
        DiagnosticCompleted.ROUTING_KEY,
        DiagnosticCompleted(
            aluno_id=str(aluno_id),
            tema_id=tema.id,
            dominio_tema=dominio_tema,
            acao=acao.value,
        ).to_payload(),
    )

    # Mensagem do tutor: o LLM só reescreve o resultado ACIMA (já 100%
    # calculado) em tom natural — nunca influencia dominio/acao. Se o
    # Groq falhar por qualquer motivo, cai no fallback determinístico.
    contexto_tutor = {
        "tema_nome": tema.nome,
        "acao": acao.value,
        "tema_recomendado": tema_recomendado.nome if tema_recomendado else None,
        "subtemas": [
            {"nome": s.nome, "classificacao": s.classificacao} for s in subtemas_avaliados
        ],
    }
    mensagem_tutor = await gerar_mensagem_tutor(contexto_tutor)
    if mensagem_tutor is None:
        mensagem_tutor = gerar_mensagem_fallback(contexto_tutor)

    return DiagnosticoResultado(
        tema_id=tema.id,
        dominio_tema=dominio_tema,
        acao=acao.value,
        subtemas_avaliados=subtemas_avaliados,
        recomendacoes_conteudo=recomendacoes,
        tema_recomendado=tema_recomendado,
        mensagem_tutor=mensagem_tutor,
    )


@router.get("/questions/{questao_id}/context", response_model=QuestaoContextoOut)
async def contexto_questao(
    questao_id: int,
    aluno_id: str = Depends(get_current_student_id),
    db: AsyncSession = Depends(get_db),
):
    """
    Contexto completo de uma questão — enunciado, alternativas, gabarito
    E a alternativa que o próprio aluno escolheu — usado pelo Chatbot
    Service (`POST /chat/explicar-questao`) para explicar por que o aluno
    errou ou acertou.

    Só libera o gabarito se existir um registro de que ESTE aluno JÁ
    respondeu ESTA questão (`DiagnosticoResposta`). Desde a fase 2 essa
    linha só pode nascer de um `POST /diagnostic/answer` cujo `tema_id`
    contém a questão (o join em `Subtema` lá em cima), então o aluno não
    consegue mais fabricá-la para um id arbitrário.
    """
    resposta_result = await db.execute(
        select(DiagnosticoResposta)
        .where(
            DiagnosticoResposta.aluno_id == aluno_id,
            DiagnosticoResposta.questao_id == questao_id,
        )
        .order_by(DiagnosticoResposta.respondido_em.desc())
    )
    resposta = resposta_result.scalars().first()
    if not resposta:
        raise HTTPException(403, "Você ainda não respondeu essa questão em nenhum diagnóstico")

    questao_result = await db.execute(select(Questao).where(Questao.id == questao_id))
    questao = questao_result.scalar_one_or_none()
    if not questao:
        raise HTTPException(404, "Questão não encontrada")

    subtema_result = await db.execute(select(Subtema).where(Subtema.id == questao.subtema_id))
    subtema = subtema_result.scalar_one_or_none()

    tema_nome = ""
    if subtema:
        tema_result = await db.execute(select(Tema).where(Tema.id == subtema.tema_id))
        tema_obj = tema_result.scalar_one_or_none()
        tema_nome = tema_obj.nome if tema_obj else ""

    return QuestaoContextoOut(
        questao_id=questao.id,
        enunciado=questao.enunciado,
        alternativas=questao.alternativas,
        gabarito=questao.gabarito,
        alternativa_escolhida=resposta.alternativa_escolhida,
        acertou=resposta.acertou,
        subtema_nome=subtema.nome if subtema else "",
        tema_nome=tema_nome,
    )
