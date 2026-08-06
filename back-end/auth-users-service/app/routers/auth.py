import secrets
from datetime import UTC, date, datetime, timedelta

from edu_common.contracts import StudentCreated
from edu_common.security import (
    DUMMY_PASSWORD_HASH,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.dependencies import get_current_user, requer_papel
from app.events.publisher import publish_event
from app.models.password_reset import PasswordResetCode
from app.models.user import User
from app.schemas.auth import (
    AuthResponseOut,
    LoginIn,
    PasswordResetConfirmIn,
    PasswordResetRequestIn,
    RefreshIn,
    RegisterIn,
    RegisterStaffIn,
    TokensOut,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def _montar_resposta_auth(user: User) -> AuthResponseOut:
    access_token = create_access_token(
        str(user.id),
        user.role,
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.access_token_expire_minutes,
    )
    refresh_token = create_refresh_token(
        str(user.id),
        user.role,
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.refresh_token_expire_days,
    )
    return AuthResponseOut(
        user=UserOut(id=user.id, name=user.nome, email=user.email, role=user.role),
        tokens=TokensOut(access_token=access_token, refresh_token=refresh_token),
    )


def _parse_birth_date(valor: str) -> date:
    """`RegisterIn.data_valida` já garantiu o formato — este parse não pode
    mais ser a primeira validação (era, e por isso um ISO virava 500)."""
    return datetime.strptime(valor, "%d/%m/%Y").date()  # data civil, sem fuso


@router.post("/register", response_model=AuthResponseOut, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterIn, db: AsyncSession = Depends(get_db)):
    """Cadastro público do app do estudante. Sempre cria com role='student'."""
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já está cadastrado")

    user = User(
        nome=payload.name,
        email=payload.email,
        senha_hash=hash_password(payload.password),
        telefone=payload.phone,
        data_nascimento=_parse_birth_date(payload.birth_date),
        escolaridade=payload.education_level,
        role="student",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    # Payload montado pela definição compartilhada em edu-common, não por um
    # dict literal: learning-service e analytics-service consomem este evento
    # e constroem seus fixtures a partir da MESMA classe, então renomear um
    # campo lá quebra os consumidores em vez de passar despercebido
    # (ver edu_common/contracts.py).
    await publish_event(
        StudentCreated.ROUTING_KEY,
        StudentCreated(aluno_id=str(user.id), nome=user.nome, email=user.email).to_payload(),
    )

    return _montar_resposta_auth(user)


@router.post("/register-staff", response_model=AuthResponseOut, status_code=status.HTTP_201_CREATED)
async def register_staff(
    payload: RegisterStaffIn,
    db: AsyncSession = Depends(get_db),
    _admin: dict = Depends(requer_papel("admin")),
):
    """Cadastro interno. Só admin pode criar separador/entregador/outro admin."""
    result = await db.execute(select(User).where(User.email == payload.email))
    if result.scalar_one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já está cadastrado")

    user = User(
        nome=payload.nome,
        email=payload.email,
        senha_hash=hash_password(payload.senha),
        telefone=payload.telefone,
        documento=payload.documento,
        role=payload.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    await publish_event(
        "staff.created",
        {"user_id": str(user.id), "nome": user.nome, "role": user.role},
    )

    return _montar_resposta_auth(user)


@router.post("/login", response_model=AuthResponseOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # DUMMY_PASSWORD_HASH garante que um bcrypt.checkpw completo rode mesmo
    # quando o e-mail não existe. A chamada a verify_password NÃO pode ficar
    # do lado direito de um `or`/`and` com `not user` — isso reintroduziria o
    # short-circuit que pula o bcrypt.checkpw inteiro quando o usuário não
    # existe (a defesa vira código morto sem nenhum erro de lint acusar:
    # DUMMY_PASSWORD_HASH continua "usado" na atribuição). Por isso a
    # avaliação é forçada numa variável antes do `if`.
    password_hash = user.senha_hash if user else DUMMY_PASSWORD_HASH
    senha_confere = verify_password(payload.password, password_hash)
    if not user or not senha_confere:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha inválidos")

    if not user.ativo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Conta desativada")

    return _montar_resposta_auth(user)


@router.post("/refresh", response_model=TokensOut)
async def refresh(payload: RefreshIn, db: AsyncSession = Depends(get_db)):
    """Resposta plana (sem wrapper `tokens`) — casa com `TokenRefresher.refresh()`.

    Consulta o banco de propósito, apesar de o token já vir assinado: sem
    isso, desativar ou rebaixar um usuário não tinha efeito nenhum até o
    refresh token expirar (14 dias com o `.env` compartilhado em vigor). O
    papel do token novo vem da coluna, não da claim do token velho.
    """
    # `expected_type="refresh"` deixa o próprio decode_token recusar um access
    # token aqui, em vez de checar `decoded.get("type")` manualmente.
    decoded = decode_token(
        payload.refresh_token, settings.jwt_secret, settings.jwt_algorithm, expected_type="refresh"
    )
    if decoded is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")

    # `decoded` só vem de tokens assinados por este serviço, mas um payload
    # forjado por outro emissor com o mesmo segredo (ou um token antigo,
    # gerado antes de `role` existir nas claims) pode passar em `decode_token`
    # sem carregar `sub`. Acessar via índice levantaria `KeyError`, que o
    # FastAPI transforma em 500 — aqui isso é só mais um refresh token
    # inválido, então cai no mesmo 401 genérico dos outros casos.
    #
    # `role` NÃO é mais exigido na claim: ele passa a vir da coluna logo
    # abaixo. Um token legado sem `role` funciona e recebe o papel real.
    sub = decoded.get("sub")
    if sub is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")

    result = await db.execute(select(User).where(User.id == sub))
    user = result.scalar_one_or_none()
    # Mesmo 401 genérico para usuário inexistente e usuário desativado: a
    # distinção seria um oráculo de enumeração e não muda nada para o app,
    # que trata os dois com logout.
    if user is None or not user.ativo:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token inválido ou expirado")

    access_token = create_access_token(
        str(user.id),
        user.role,
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.access_token_expire_minutes,
    )
    novo_refresh_token = create_refresh_token(
        str(user.id),
        user.role,
        settings.jwt_secret,
        settings.jwt_algorithm,
        settings.refresh_token_expire_days,
    )
    return TokensOut(access_token=access_token, refresh_token=novo_refresh_token)


@router.get("/me", response_model=UserOut)
async def me(
    user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Casa com `AuthApi.currentDisplayName()`."""
    result = await db.execute(select(User).where(User.id == user["sub"]))
    db_user = result.scalar_one_or_none()
    if not db_user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuário não encontrado")
    return UserOut(id=db_user.id, name=db_user.nome, email=db_user.email, role=db_user.role)


@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def password_reset_request(
    payload: PasswordResetRequestIn, db: AsyncSession = Depends(get_db)
):
    """
    Sempre responde 200, mesmo se o e-mail não existir (anti-enumeração,
    casa com o comentário em `AuthApi.requestPasswordReset()`).

    MVP: nenhum provedor de e-mail/SMS está configurado ainda — o código de
    6 dígitos não sai daqui (não vai para log nem resposta). Plugar um
    provedor real antes de produção.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    if user:
        # secrets.randbelow (não `random`): o código é um segredo curto de
        # uso único, precisa vir de um PRNG criptograficamente seguro.
        codigo = f"{secrets.randbelow(1_000_000):06d}"
        db.add(
            PasswordResetCode(
                user_id=user.id,
                code_hash=hash_password(codigo),
                expira_em=datetime.now(UTC) + timedelta(minutes=10),
            )
        )
        await db.commit()
        # MVP: sem provedor de e-mail/SMS configurado — o código não vai para
        # o log (é um segredo efêmero); só o fato de ter sido gerado.
        logger.info("auth: password reset code generated user={}", user.id)

    return {"detail": "Se o e-mail existir, um código foi enviado."}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def password_reset_confirm(
    payload: PasswordResetConfirmIn, db: AsyncSession = Depends(get_db)
):
    """Resposta genérica 400 para qualquer falha de verificação, casando com
    `AuthApi.confirmPasswordReset()` (não revela qual parte está errada)."""
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    erro_generico = HTTPException(status.HTTP_400_BAD_REQUEST, "Código inválido ou expirado")

    if not user:
        raise erro_generico

    result = await db.execute(
        select(PasswordResetCode)
        .where(
            PasswordResetCode.user_id == user.id,
            PasswordResetCode.usado.is_(False),
        )
        .order_by(PasswordResetCode.criado_em.desc())
    )
    reset_code = result.scalars().first()

    if not reset_code:
        raise erro_generico

    # Coluna `expira_em` é TIMESTAMPTZ (DateTime(timezone=True), alinhada ao
    # schema.sql) — comparação aware-a-aware.
    if reset_code.expira_em < datetime.now(UTC):
        raise erro_generico

    if not verify_password(payload.code, reset_code.code_hash):
        raise erro_generico

    reset_code.usado = True
    user.senha_hash = hash_password(payload.new_password)
    await db.commit()

    return {"detail": "Senha redefinida com sucesso."}
