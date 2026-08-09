import 'package:edu_ia/features/logistics/domain/occurrence.dart';
import 'package:flutter_test/flutter_test.dart';

/// Payloads literais no contrato NOVO, medido em
/// `back-end/commerce-service/app/schemas/ocorrencia.py::OcorrenciaOut` e
/// `ProdutoSugeridoOut`. `id` da ocorrência continua inteiro — só
/// `pedido_id` e `produto_id` viraram UUID (tasks C3 e B4).
void main() {
  group('Ocorrencia.fromJson', () {
    test('keeps id as int and parses pedido_id/produto_id as UUID strings', () {
      final ocorrencia = Ocorrencia.fromJson({
        'id': 42,
        'pedido_id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
        'tipo': 'FALTA_ESTOQUE',
        'status': 'ABERTA',
        'produto_id': 'd4e3c960-3333-4562-b3fc-2c963f66afa9',
        'nova_data_sugerida': null,
        'motivo': 'Sem estoque disponível',
        'resolucao': null,
        'criado_em': '2026-08-09T10:00:00Z',
        'resolvido_em': null,
      });

      expect(ocorrencia.id, isA<int>());
      expect(ocorrencia.id, 42);
      expect(ocorrencia.pedidoId, isA<String>());
      expect(ocorrencia.pedidoId, '3fa85f64-5717-4562-b3fc-2c963f66afa6');
      expect(ocorrencia.produtoId, isA<String>());
      expect(ocorrencia.produtoId, 'd4e3c960-3333-4562-b3fc-2c963f66afa9');
    });

    test('produto_id stays null when absent (ATRASO_ENTREGA has no product)', () {
      final ocorrencia = Ocorrencia.fromJson({
        'id': 43,
        'pedido_id': '3fa85f64-5717-4562-b3fc-2c963f66afa6',
        'tipo': 'ATRASO_ENTREGA',
        'status': 'ABERTA',
        'produto_id': null,
        'nova_data_sugerida': '2026-08-20T00:00:00Z',
        'motivo': 'Trânsito intenso',
        'resolucao': null,
        'criado_em': '2026-08-09T10:00:00Z',
        'resolvido_em': null,
      });

      expect(ocorrencia.produtoId, isNull);
    });
  });

  group('ProdutoSugerido.fromJson', () {
    test('parses a UUID id', () {
      final produto = ProdutoSugerido.fromJson({
        'id': 'e5f4da70-4444-4562-b3fc-2c963f66afaa',
        'nome': 'Apostila substituta',
        'preco': 99.9,
        'imagem_url': null,
      });

      expect(produto.id, isA<String>());
      expect(produto.id, 'e5f4da70-4444-4562-b3fc-2c963f66afaa');
    });
  });
}
