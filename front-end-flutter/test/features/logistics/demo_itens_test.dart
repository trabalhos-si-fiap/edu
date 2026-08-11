import 'package:edu_ia/features/logistics/data/demo_itens.dart';
import 'package:edu_ia/features/logistics/domain/order.dart';
import 'package:flutter_test/flutter_test.dart';

const _item = PedidoItem(
  produtoId: 'p1',
  fornecedorId: 1,
  quantidade: 1,
  precoUnitario: 10,
  nomeProduto: 'Produto real',
);

void main() {
  test('sem a flag, um pedido sem itens continua sem itens', () {
    // O default é a constante de compilação, que é false em qualquer build
    // que não passe --dart-define. É esta asserção que garante que a
    // vitrine de gravação não vaze para o app de verdade.
    expect(itensParaExibir(const []), isEmpty);
    expect(itensParaExibir(const [], mock: false), isEmpty);
  });

  test('com a flag, um pedido sem itens ganha a lista de demonstração', () {
    final itens = itensParaExibir(const [], mock: true);
    expect(itens, same(itensDeDemonstracao));
    expect(itens.map((i) => i.nomeProduto), contains('Simulado ENEM Completo'));
  });

  test('itens reais nunca são substituídos, nem com a flag ligada', () {
    expect(itensParaExibir(const [_item], mock: true), const [_item]);
  });
}
