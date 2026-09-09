"""Contratos de `/shipments`.

`CarregamentoCriadoOut` é o ÚNICO schema desta spec que carrega a senha, e ele
só é usado na resposta da criação. Os demais expõem `codigo` (identifica o
lote, não autentica ninguém) e nunca `senha` nem `senha_hash` — regra 6 do
CLAUDE.md: campos explícitos, nada de `from_attributes` derramando coluna
sensível.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from app.ids import Int32Id


class CarregamentoIn(BaseModel):
    transportadora_id: Int32Id


class PedidoDoCarregamentoIn(BaseModel):
    pedido_id: str = Field(max_length=36)


class CarregamentoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transportadora_id: int
    codigo: str
    origem_rotulo: str
    origem_lat: Decimal | None
    origem_lng: Decimal | None
    entregador_nome: str | None
    entregador_contato: str | None
    aberto_em: datetime | None
    criado_em: datetime

    @field_serializer("origem_lat", "origem_lng")
    def _coordenada_como_texto(self, value: Decimal | None) -> str | None:
        # Mesma escolha de `ParceiroOut` (spec B): coordenada atravessa JSON
        # como string para não herdar erro de arredondamento de float.
        return None if value is None else f"{value:.6f}"


class CarregamentoCriadoOut(CarregamentoOut):
    """Resposta de `POST /shipments` — a única que traz a senha.

    Ela existe porque o admin precisa poder ler a credencial na tela quando o
    e-mail demora ou não chega. Nenhuma leitura posterior a devolve: a senha
    não é recuperável depois desta resposta, só redefinível criando outro
    carregamento.
    """

    senha: str


class CarregamentoList(BaseModel):
    items: list[CarregamentoOut]
    total: int
    limit: int
    offset: int


class CarregamentoLoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    codigo: str = Field(min_length=1, max_length=12)
    senha: str = Field(min_length=1, max_length=128)
    nome: str = Field(min_length=1, max_length=120)
    contato: str = Field(min_length=1, max_length=120)


class CarregamentoLoginOut(BaseModel):
    """Só o access token: o carregamento não tem refresh.

    Um lote é de uma jornada, e um refresh de sete dias sobre uma senha que
    circula por e-mail é vida longa demais para uma credencial compartilhada.
    Expiração e revogação sofisticadas estão explicitamente fora do escopo da
    spec; o que existe é o `exp` de 12 horas abaixo.
    """

    access_token: str
    token_type: str = "bearer"  # noqa: S105 — não é segredo, é o esquema OAuth2
    carregamento_id: int
    codigo: str
    origem_rotulo: str
