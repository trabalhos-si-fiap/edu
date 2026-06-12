/// Modelos de domínio da tela de Acompanhamento de Pedido (Order Tracking).
///
/// Espelham o JSON que o backend FastAPI retornará em
/// `GET /orders/{id}/tracking`. O parsing é feito manualmente em `fromJson`
/// (sem `json_serializable`/`build_runner`) para manter o projeto sem etapa de
/// codegen, mantendo `toJson` simétrico para testes e cache local.
library;

/// Estado de cada etapa da linha do tempo de rastreio.
enum OrderStepStatus {
  done,
  current,
  pending;

  static OrderStepStatus fromJson(String? value) {
    switch (value) {
      case 'done':
        return OrderStepStatus.done;
      case 'current':
        return OrderStepStatus.current;
      default:
        return OrderStepStatus.pending;
    }
  }

  String toJson() => name;
}

/// Uma etapa do progresso do pedido (ex.: Processado, Em Trânsito, Entregue).
class TrackingStep {
  /// Identificador estável da etapa, usado pela UI para escolher o ícone
  /// (`processed`, `in_transit`, `delivered`, ...). Mantém o model agnóstico
  /// de widgets do Flutter.
  final String code;
  final String title;
  final DateTime? timestamp;
  final OrderStepStatus status;

  const TrackingStep({
    required this.code,
    required this.title,
    required this.status,
    this.timestamp,
  });

  factory TrackingStep.fromJson(Map<String, dynamic> json) {
    final raw = json['timestamp'] as String?;
    return TrackingStep(
      code: (json['code'] as String?) ?? '',
      title: (json['title'] as String?) ?? '',
      status: OrderStepStatus.fromJson(json['status'] as String?),
      timestamp: raw == null ? null : DateTime.tryParse(raw),
    );
  }

  Map<String, dynamic> toJson() => {
    'code': code,
    'title': title,
    'status': status.toJson(),
    'timestamp': timestamp?.toIso8601String(),
  };
}

/// Localização atual da encomenda (último ponto de leitura do rastreio).
class TrackingLocation {
  final String name;
  final String city;
  final String state;
  final DateTime? updatedAt;

  const TrackingLocation({
    required this.name,
    required this.city,
    required this.state,
    this.updatedAt,
  });

  factory TrackingLocation.fromJson(Map<String, dynamic> json) {
    final raw = json['updated_at'] as String?;
    return TrackingLocation(
      name: (json['name'] as String?) ?? '',
      city: (json['city'] as String?) ?? '',
      state: (json['state'] as String?) ?? '',
      updatedAt: raw == null ? null : DateTime.tryParse(raw),
    );
  }

  Map<String, dynamic> toJson() => {
    'name': name,
    'city': city,
    'state': state,
    'updated_at': updatedAt?.toIso8601String(),
  };

  /// "Cajamar, SP" — usada no subtítulo do card de localização.
  String get cityState =>
      [city, state].where((s) => s.trim().isNotEmpty).join(', ');
}

/// Item incluso no kit/pedido (ex.: apostila, caderno).
class KitItem {
  final String name;
  final String? subtitle;

  const KitItem({required this.name, this.subtitle});

  factory KitItem.fromJson(Map<String, dynamic> json) => KitItem(
    name: (json['name'] as String?) ?? '',
    subtitle: json['subtitle'] as String?,
  );

  Map<String, dynamic> toJson() => {'name': name, 'subtitle': subtitle};
}

/// Pedido completo com seu histórico de rastreio.
class OrderModel {
  final String id;
  final String headline;
  final String description;
  final DateTime estimatedArrival;
  final List<TrackingStep> steps;
  final TrackingLocation location;
  final List<KitItem> kit;
  final String carrier;
  final String? mapUrl;

  const OrderModel({
    required this.id,
    required this.headline,
    required this.description,
    required this.estimatedArrival,
    required this.steps,
    required this.location,
    required this.kit,
    required this.carrier,
    this.mapUrl,
  });

  factory OrderModel.fromJson(Map<String, dynamic> json) {
    final steps = (json['steps'] as List<dynamic>? ?? const [])
        .map((e) => TrackingStep.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
    final kit = (json['kit'] as List<dynamic>? ?? const [])
        .map((e) => KitItem.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
    return OrderModel(
      id: (json['id'] as String?) ?? '',
      headline: (json['headline'] as String?) ?? '',
      description: (json['description'] as String?) ?? '',
      estimatedArrival:
          DateTime.tryParse((json['estimated_arrival'] as String?) ?? '') ??
          DateTime.now(),
      steps: steps,
      location: TrackingLocation.fromJson(
        (json['location'] as Map<String, dynamic>?) ?? const {},
      ),
      kit: kit,
      carrier: (json['carrier'] as String?) ?? '',
      mapUrl: json['map_url'] as String?,
    );
  }

  Map<String, dynamic> toJson() => {
    'id': id,
    'headline': headline,
    'description': description,
    'estimated_arrival': estimatedArrival.toIso8601String(),
    'steps': steps.map((s) => s.toJson()).toList(),
    'location': location.toJson(),
    'kit': kit.map((k) => k.toJson()).toList(),
    'carrier': carrier,
    'map_url': mapUrl,
  };

  /// Etapa em andamento (ou a última concluída, se não houver "current").
  TrackingStep? get currentStep {
    for (final step in steps) {
      if (step.status == OrderStepStatus.current) return step;
    }
    return null;
  }
}
