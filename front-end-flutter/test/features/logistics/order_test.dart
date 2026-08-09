import 'package:edu_ia/features/logistics/domain/order.dart';
import 'package:flutter_test/flutter_test.dart';

/// Payload literal no contrato NOVO (pós task C4), medido em
/// `back-end/commerce-service/app/schemas/pedido.py::PedidoStaffOut`.
/// Escrito à mão de propósito — gerar isto a partir de `Pedido.toJson`
/// provaria só que o parser concorda consigo mesmo.
Map<String, dynamic> _pedidoJson({String status = 'EM_SEPARACAO', String enderecoEntrega = 'Rua das Flores, 123 - Centro'}) => {
  'id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
  'user_id': 'b2c1a940-1234-4562-b3fc-2c963f66afa7',
  'status': status,
  'total': '242.00',
  'endereco_entrega': enderecoEntrega,
  'carrier_name': 'Transportadora XPTO',
  'estimated_delivery_at': '2026-08-15T18:00:00Z',
  'created_at': '2026-08-09T09:30:00Z',
  'picker_id': 'c3d2b850-2222-4562-b3fc-2c963f66afa8',
  'deliverer_id': null,
};

void main() {
  group('Pedido.fromJson', () {
    test('parses the new staff contract (user_id, total string, picker_id, '
        'deliverer_id, carrier_name, created_at, estimated_delivery_at)', () {
      final pedido = Pedido.fromJson(_pedidoJson());

      expect(pedido.id, isA<String>());
      expect(pedido.id, '3fa85f64-5717-4562-b3fc-2c963f66afa6');
      expect(pedido.userId, 'b2c1a940-1234-4562-b3fc-2c963f66afa7');
      expect(pedido.status, StatusPedido.emSeparacao);
      expect(pedido.total, isA<String>());
      expect(pedido.total, '242.00');
      expect(pedido.enderecoEntrega, 'Rua das Flores, 123 - Centro');
      expect(pedido.carrierName, 'Transportadora XPTO');
      expect(pedido.estimatedDeliveryAt, DateTime.utc(2026, 8, 15, 18, 0, 0));
      expect(pedido.createdAt, DateTime.utc(2026, 8, 9, 9, 30, 0));
      expect(pedido.pickerId, 'c3d2b850-2222-4562-b3fc-2c963f66afa8');
      expect(pedido.delivererId, isNull);
    });

    test('accepts endereco_entrega as an empty string (order without an '
        'address snapshot) instead of throwing', () {
      final pedido = Pedido.fromJson(_pedidoJson(enderecoEntrega: ''));

      expect(pedido.enderecoEntrega, '');
    });
  });

  group('StatusPedido.fromApi', () {
    test('"CONFIRMADO" (task C1) is not cancelado', () {
      expect(StatusPedido.fromApi('CONFIRMADO'), isNot(StatusPedido.cancelado));
      expect(StatusPedido.fromApi('CONFIRMADO'), StatusPedido.confirmado);
    });

    // Medido: esta asserção sozinha já passa no código NÃO corrigido, porque
    // hoje qualquer valor não mapeado (inclusive "CANCELADO", que nunca teve
    // `case` próprio) cai no mesmo `default: return StatusPedido.cancelado`
    // — o valor certo pelo motivo errado (brief C4b, "O que quebrou,
    // medido"). Isoladamente ela não é guarda de regressão desta task
    // (Regra 1 do controlador: "um teste que já passava não prova nada").
    // O teste de colisão logo abaixo é o que de fato força um `case`
    // explícito para CANCELADO — ele falha no código não corrigido.
    test('"CANCELADO" is cancelado', () {
      expect(StatusPedido.fromApi('CANCELADO'), StatusPedido.cancelado);
    });

    test('no two of the nine known backend statuses collapse onto the same '
        'value (proves CANCELADO has its own case, not a default fallback '
        'shared with CONFIRMADO)', () {
      const valoresConhecidos = [
        'CRIADO',
        'CONFIRMADO',
        'AGUARDANDO_SEPARACAO',
        'EM_SEPARACAO',
        'SEPARADO',
        'AGUARDANDO_COLETA',
        'EM_TRANSITO',
        'ENTREGUE',
        'CANCELADO',
      ];
      final mapeados = valoresConhecidos.map(StatusPedido.fromApi).toSet();
      expect(mapeados.length, valoresConhecidos.length);
    });

    test('an unknown value ("NAO_EXISTE") is not cancelado', () {
      expect(StatusPedido.fromApi('NAO_EXISTE'), isNot(StatusPedido.cancelado));
      expect(StatusPedido.fromApi('NAO_EXISTE'), StatusPedido.desconhecido);
    });
  });

  group('PedidoItem.fromJson', () {
    // Nenhum schema de staff devolve a chave `itens` — medido:
    // `grep -n "itens" back-end/commerce-service/app/schemas/pedido.py`
    // só encontra `itens` em `PedidoItemIn`/`PedidoCreateIn` (corpo de
    // `POST /orders`, contrato do aluno), nunca em `PedidoStaffOut` nem
    // `PedidoFilaOut`. Este teste garante que, se a chave um dia existir,
    // os tipos já estão coerentes com o backend (produtos são UUID desde a
    // B4; fornecedores continuam inteiro).
    test('parses a UUID produto_id and an int fornecedor_id', () {
      final item = PedidoItem.fromJson({
        'produto_id': 'd4e3c960-3333-4562-b3fc-2c963f66afa9',
        'fornecedor_id': 7,
        'quantidade': 2,
        'preco_unitario': 49.9,
        'nome_produto': 'Apostila',
      });

      expect(item.produtoId, isA<String>());
      expect(item.produtoId, 'd4e3c960-3333-4562-b3fc-2c963f66afa9');
      expect(item.fornecedorId, 7);
    });
  });
}
