/// Modelos de domínio do carregamento (lote que a transportadora retira na
/// origem), do ponto de vista do admin — Commerce Service (`/shipments`,
/// `/carriers`).
library;

/// Transportadora parceira, para o seletor de criação de carregamento
/// (`GET /carriers`). Porte um a um de `TransportadoraOut`
/// (`back-end/commerce-service/app/schemas/transportadora.py`).
class Carrier {
  final int id;
  final String name;
  final String location;
  final String email;
  final int averageDeliveryDays;
  // `rating` e `sla_percentage` atravessam JSON como STRING — mesma escolha
  // de `Pedido.total` (order.dart): não é aritmética, é exibição, e não
  // pode herdar erro de arredondamento de float.
  final String rating;
  final String slaPercentage;
  final String status;

  const Carrier({
    required this.id,
    required this.name,
    required this.location,
    required this.email,
    required this.averageDeliveryDays,
    required this.rating,
    required this.slaPercentage,
    required this.status,
  });

  factory Carrier.fromJson(Map<String, dynamic> json) {
    return Carrier(
      id: json['id'] as int,
      name: json['name'] as String,
      location: json['location'] as String,
      email: json['email'] as String,
      averageDeliveryDays: json['average_delivery_days'] as int,
      rating: json['rating'] as String,
      slaPercentage: json['sla_percentage'] as String,
      status: json['status'] as String,
    );
  }
}

/// Um carregamento, do jeito que `GET /shipments` e `GET /shipments/{id}`
/// devolvem. NUNCA carrega `senha` — só [ShipmentCriado] (a resposta de
/// `POST /shipments`) tem esse campo, e é o único schema do backend que o
/// expõe (ver docstring de `CarregamentoCriadoOut` no commerce-service).
class Shipment {
  final int id;
  final int transportadoraId;
  final String codigo;
  final String origemRotulo;
  // Coordenada como STRING: o backend serializa `origem_lat`/`origem_lng`
  // deliberadamente como texto (`CarregamentoOut._coordenada_como_texto`) —
  // mesmo motivo do `rating` acima, não convertido para `double` aqui.
  final String? origemLat;
  final String? origemLng;
  final String? entregadorNome;
  final String? entregadorContato;
  final DateTime? abertoEm;
  final DateTime criadoEm;

  const Shipment({
    required this.id,
    required this.transportadoraId,
    required this.codigo,
    required this.origemRotulo,
    this.origemLat,
    this.origemLng,
    this.entregadorNome,
    this.entregadorContato,
    this.abertoEm,
    required this.criadoEm,
  });

  factory Shipment.fromJson(Map<String, dynamic> json) {
    return Shipment(
      id: json['id'] as int,
      transportadoraId: json['transportadora_id'] as int,
      codigo: json['codigo'] as String,
      origemRotulo: json['origem_rotulo'] as String,
      origemLat: json['origem_lat'] as String?,
      origemLng: json['origem_lng'] as String?,
      entregadorNome: json['entregador_nome'] as String?,
      entregadorContato: json['entregador_contato'] as String?,
      abertoEm: json['aberto_em'] != null
          ? DateTime.parse(json['aberto_em'] as String)
          : null,
      criadoEm: DateTime.parse(json['criado_em'] as String),
    );
  }
}

/// Resposta de `POST /shipments` — a ÚNICA que carrega [senha]. A tela
/// mostra esse valor uma vez, num cartão copiável, e nunca o persiste: não
/// há como recuperá-lo depois desta resposta (nem `GET /shipments`, nem
/// `GET /shipments/{id}` o devolvem — só a criação de outro carregamento
/// gera outra senha).
class ShipmentCriado extends Shipment {
  final String senha;

  const ShipmentCriado({
    required super.id,
    required super.transportadoraId,
    required super.codigo,
    required super.origemRotulo,
    super.origemLat,
    super.origemLng,
    super.entregadorNome,
    super.entregadorContato,
    super.abertoEm,
    required super.criadoEm,
    required this.senha,
  });

  factory ShipmentCriado.fromJson(Map<String, dynamic> json) {
    final base = Shipment.fromJson(json);
    return ShipmentCriado(
      id: base.id,
      transportadoraId: base.transportadoraId,
      codigo: base.codigo,
      origemRotulo: base.origemRotulo,
      origemLat: base.origemLat,
      origemLng: base.origemLng,
      entregadorNome: base.entregadorNome,
      entregadorContato: base.entregadorContato,
      abertoEm: base.abertoEm,
      criadoEm: base.criadoEm,
      senha: json['senha'] as String,
    );
  }
}
