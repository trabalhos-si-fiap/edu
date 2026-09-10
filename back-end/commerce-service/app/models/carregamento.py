from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class Carregamento(Base):
    """O lote de pedidos que sai junto, de UMA origem, por UMA transportadora.

    Em PORTUGUÊS — tabela e colunas — pelo mesmo critério que deixou
    `fornecedores`, `estoque` e `ocorrencias` em português: o agregado não tem
    cliente externo. Quem tem cliente é a ROTA, e ela é `/shipments`.

    O carregamento é também a CREDENCIAL do entregador: `codigo` identifica o
    lote e `senha_hash` autentica quem o retira. Não há conta de entregador
    pré-cadastrada no caminho normal (o papel `entregador` continua no enum do
    auth-users porque a spec A seeda uma conta de demonstração com ele).

    `entregador_nome`/`entregador_contato`/`aberto_em` nascem nulos e são
    gravados no PRIMEIRO acesso — é o registro de quem pegou a carga, que não
    existia antes desta spec.
    """

    __tablename__ = "carregamentos"

    id = Column(Integer, primary_key=True)
    transportadora_id = Column(Integer, ForeignKey("carriers.id"), nullable=False, index=True)
    # Origem congelada a partir do PRIMEIRO pedido atribuído (ver D10 e
    # `app/services/carregamentos.py::atribuir_pedido`). Não é lida do
    # fornecedor em tempo de consulta: o estoque pode trocar de fornecedor
    # depois que o lote saiu, e a rota do mapa é registro histórico.
    origem_rotulo = Column(String(120), nullable=False, default="", server_default=text("''"))
    origem_lat = Column(Numeric(9, 6), nullable=True)
    origem_lng = Column(Numeric(9, 6), nullable=True)
    codigo = Column(String(12), nullable=False, unique=True, index=True)
    senha_hash = Column(String(255), nullable=False)
    entregador_nome = Column(String(120), nullable=True)
    entregador_contato = Column(String(120), nullable=True)
    aberto_em = Column(DateTime(timezone=True), nullable=True)
    criado_por = Column(UUID(as_uuid=True), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PosicaoEntrega(Base):
    """Posição do carregamento ao longo do tempo.

    SÉRIE TEMPORAL, não campo único: o mapa desenha o caminho percorrido, e um
    campo único não guarda caminho.

    Quem escreve aqui é `app/services/posicao.py::registrar_posicao` — a porta
    única. O simulador (`app/services/simulador_posicao.py`) é UM chamador
    dela; um GPS de verdade seria outro. Trocar de fonte é acrescentar um
    chamador e desligar este, não reescrever leitura, model ou tela.
    """

    __tablename__ = "posicao_entrega"

    id = Column(Integer, primary_key=True)
    carregamento_id = Column(Integer, ForeignKey("carregamentos.id"), nullable=False, index=True)
    lat = Column(Numeric(9, 6), nullable=False)
    lng = Column(Numeric(9, 6), nullable=False)
    registrado_em = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
