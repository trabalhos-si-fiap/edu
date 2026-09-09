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
