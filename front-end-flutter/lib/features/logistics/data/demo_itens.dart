import '../domain/order.dart';

/// Itens de vitrine para a tela de separação, usados APENAS em gravação de
/// demonstração.
///
/// Motivo: nenhum schema de staff do Commerce Service devolve a chave
/// `itens` — nem `PedidoStaffOut` nem `PedidoFilaOut` (ver o comentário em
/// `PedidoItem`, que já registra a medição). Sem isso a checklist de
/// conferência do separador abre vazia e a tela mostra o aviso técnico no
/// lugar dos produtos, o que não representa o fluxo real.
///
/// Isto NÃO é fallback de produção: a flag é uma constante de compilação e
/// vale `false` em qualquer build normal, então o código morto some no
/// tree-shaking. Só entra quando o build recebe explicitamente
/// `--dart-define=DEMO_ITENS_MOCK=true`, o que hoje só acontece em
/// `scripts/demo-telas.sh`.
///
/// Quando o backend passar a expor os itens, apague este arquivo e troque
/// `itensParaExibir(...)` por `pedido.itens` na `picking_screen.dart`.
const bool demoItensMock = bool.fromEnvironment('DEMO_ITENS_MOCK');

/// Nomes e preços copiados do catálogo semeado
/// (`back-end/commerce-service/app/seeds/products.py`), para a gravação não
/// mostrar produto que não existe no banco.
const List<PedidoItem> itensDeDemonstracao = [
  PedidoItem(
    produtoId: '019fee6a-90ee-7571-be6b-ce8eeec14f01',
    fornecedorId: 1,
    quantidade: 1,
    precoUnitario: 149.90,
    nomeProduto: 'Curso de Matemática Essencial',
  ),
  PedidoItem(
    produtoId: '019fee6a-90ee-7571-be6b-ce3acb3778d1',
    fornecedorId: 1,
    quantidade: 2,
    precoUnitario: 49.90,
    nomeProduto: 'Guia de Redação Nota 1000',
  ),
  PedidoItem(
    produtoId: '019fee6a-90ee-7571-be6b-ce63213bd4ca',
    fornecedorId: 2,
    quantidade: 1,
    precoUnitario: 29.90,
    nomeProduto: 'Simulado ENEM Completo',
  ),
];

/// Devolve os itens reais do pedido. A lista de demonstração só aparece
/// quando o pedido veio sem itens E a flag foi ligada no build — nessa
/// ordem, para que um pedido com itens de verdade nunca seja substituído.
///
/// [mock] existe para o teste conseguir exercitar os dois lados; o app
/// sempre usa o default, que é a constante de compilação.
List<PedidoItem> itensParaExibir(
  List<PedidoItem> reais, {
  bool mock = demoItensMock,
}) {
  if (reais.isNotEmpty || !mock) return reais;
  return itensDeDemonstracao;
}
