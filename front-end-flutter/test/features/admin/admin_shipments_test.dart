import 'package:edu_ia/features/admin/data/admin_api.dart';
import 'package:edu_ia/features/admin/domain/shipment.dart';
import 'package:edu_ia/features/admin/presentation/admin_shipments_screen.dart';
import 'package:edu_ia/features/admin/presentation/widgets/admin_scaffold.dart';
import 'package:edu_ia/features/admin/presentation/widgets/admin_widgets.dart';
import 'package:edu_ia/features/logistics/domain/order.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

/// Mensagem verbatim do backend para os dois 409 de
/// `POST /shipments/{id}/orders` (`app/routers/carregamentos.py`,
/// `CarregamentoOrigemDivergenteError.MENSAGEM`). O app exibe exatamente
/// isto — mesma regra já fixada para `CarrinhoOrigemMistaError` no carrinho
/// (spec B): a frase é contrato de UI, o app não reescreve.
const _mensagemOrigemDivergente =
    'Este carregamento sai de outra origem. Crie um carregamento separado '
    'para os pedidos desta origem.';

class _FakeAdminApi extends AdminApi {
  _FakeAdminApi({
    this.carregamentos = const [],
    List<Carrier> transportadoras = const [],
    ShipmentCriado? aoCriar,
    Object? erroAoAtribuir,
    Map<int, List<Pedido>> pedidosPorCarregamento = const {},
  }) : _transportadoras = transportadoras,
       _aoCriar = aoCriar,
       _erroAoAtribuir = erroAoAtribuir,
       _pedidosPorCarregamento = pedidosPorCarregamento;

  // Mutável (não `final`): o teste de reordenação reatribui esta lista
  // entre um `fetchCarregamentos()` e o próximo, simulando o efeito de
  // criar um carregamento (o mais novo entra na frente dos demais).
  List<Shipment> carregamentos;
  final List<Carrier> _transportadoras;
  final ShipmentCriado? _aoCriar;
  final Object? _erroAoAtribuir;
  final Map<int, List<Pedido>> _pedidosPorCarregamento;

  int? transportadoraIdRecebida;

  @override
  Future<List<Shipment>> fetchCarregamentos() async => carregamentos;

  @override
  Future<List<Carrier>> fetchTransportadoras() async => _transportadoras;

  @override
  Future<ShipmentCriado> criarCarregamento(int transportadoraId) async {
    transportadoraIdRecebida = transportadoraId;
    return _aoCriar!;
  }

  @override
  Future<void> atribuirPedido({
    required int carregamentoId,
    required String pedidoId,
  }) async {
    if (_erroAoAtribuir != null) throw _erroAoAtribuir;
  }

  @override
  Future<List<Pedido>> fetchPedidosDoCarregamento(int carregamentoId) async =>
      _pedidosPorCarregamento[carregamentoId] ?? const [];
}

void main() {
  testWidgets('a tela lista carregamentos e não mostra senha na listagem', (
    tester,
  ) async {
    final api = _FakeAdminApi(
      carregamentos: [
        Shipment(
          id: 42,
          transportadoraId: 7,
          codigo: 'CARGA-042',
          origemRotulo: 'Centro de Distribuição SP',
          criadoEm: DateTime(2026, 9, 1, 10, 30),
        ),
      ],
    );

    await tester.pumpWidget(MaterialApp(home: AdminShipmentsScreen(api: api)));
    await tester.pumpAndSettle();

    expect(find.text('CARGA-042'), findsOneWidget);
    expect(find.text('Centro de Distribuição SP'), findsOneWidget);
    // A listagem nunca carrega senha (o schema `CarregamentoOut` não tem
    // esse campo) — nada na tela pode rotular ou mostrar uma senha aqui.
    expect(find.text('Senha'), findsNothing);
  });

  testWidgets('criar carregamento mostra código e senha uma vez', (
    tester,
  ) async {
    final api = _FakeAdminApi(
      carregamentos: const [],
      transportadoras: const [
        Carrier(
          id: 7,
          name: 'Rápido Entregas',
          location: 'São Paulo, SP',
          email: 'contato@rapido.example',
          averageDeliveryDays: 2,
          rating: '4.5',
          slaPercentage: '95.00',
          status: 'ACTIVE',
        ),
      ],
      aoCriar: ShipmentCriado(
        id: 99,
        transportadoraId: 7,
        codigo: 'CARGA-099',
        origemRotulo: 'Centro de Distribuição SP',
        criadoEm: DateTime(2026, 9, 9, 8, 0),
        senha: 's3nhaSecretaUnica',
      ),
    );

    await tester.pumpWidget(MaterialApp(home: AdminShipmentsScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Novo carregamento'));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(ElevatedButton, 'Criar'));
    await tester.pumpAndSettle();

    expect(api.transportadoraIdRecebida, 7);
    expect(find.text('CARGA-099'), findsOneWidget);
    expect(find.text('s3nhaSecretaUnica'), findsOneWidget);
    expect(
      find.text(
        'A transportadora também recebeu estes dados por e-mail. '
        'Esta senha não pode ser consultada depois.',
      ),
      findsOneWidget,
    );

    // Fecha o cartão de senha e confirma que ela some da árvore — é
    // mostrada uma vez, não fica pairando na tela.
    await tester.tap(find.widgetWithText(ElevatedButton, 'Fechar'));
    await tester.pumpAndSettle();
    expect(find.text('s3nhaSecretaUnica'), findsNothing);
  });

  testWidgets('atribuir pedido de outra origem mostra a mensagem do servidor', (
    tester,
  ) async {
    final api = _FakeAdminApi(
      carregamentos: [
        Shipment(
          id: 42,
          transportadoraId: 7,
          codigo: 'CARGA-042',
          origemRotulo: 'Centro de Distribuição SP',
          criadoEm: DateTime(2026, 9, 1, 10, 30),
        ),
      ],
      erroAoAtribuir: AdminApiException(_mensagemOrigemDivergente),
    );

    await tester.pumpWidget(MaterialApp(home: AdminShipmentsScreen(api: api)));
    await tester.pumpAndSettle();

    await tester.tap(find.widgetWithText(TextButton, 'Pedido'));
    await tester.pumpAndSettle();

    await tester.enterText(
      find.byType(TextField),
      '11111111-1111-1111-1111-111111111111',
    );
    await tester.tap(find.widgetWithText(ElevatedButton, 'Adicionar'));
    await tester.pumpAndSettle();

    // A mensagem é do servidor, verbatim — o teste usa a MESMA constante
    // que o `AdminApiException` recebeu, não uma paráfrase.
    expect(find.text(_mensagemOrigemDivergente), findsOneWidget);
  });

  testWidgets('o scaffold do admin tem três abas', (tester) async {
    await tester.pumpWidget(
      const MaterialApp(
        home: AdminScaffold(
          tab: AdminTab.dashboard,
          titulo: 'Painel Administrativo',
          body: SizedBox.shrink(),
        ),
      ),
    );
    await tester.pumpAndSettle();

    expect(AdminTab.values.length, 3);
    expect(find.text('Dashboard'), findsOneWidget);
    expect(find.text('Painel'), findsOneWidget);
    expect(find.text('Carregamentos'), findsOneWidget);
  });

  testWidgets(
    'um card expandido mantém os pedidos do próprio carregamento quando a '
    'lista reordena',
    (tester) async {
      // Fix round 1, finding 1: sem `Key`, o Flutter reaproveitava o
      // `State` de `_CarregamentoCard` por POSIÇÃO — um card expandido na
      // posição 1 continuava com o `_pedidosFuture` memoizado da posição 1
      // mesmo depois que um carregamento novo era criado (entra na
      // frente, empurrando todo mundo um índice adiante) e outro
      // carregamento passava a ocupar aquela posição.
      final s1 = Shipment(
        id: 1,
        transportadoraId: 7,
        codigo: 'CARGA-001',
        origemRotulo: 'Origem 1',
        criadoEm: DateTime(2026, 9, 1, 9, 0),
      );
      final s2 = Shipment(
        id: 2,
        transportadoraId: 7,
        codigo: 'CARGA-002',
        origemRotulo: 'Origem 2',
        criadoEm: DateTime(2026, 9, 2, 9, 0),
      );
      final s3Novo = Shipment(
        id: 3,
        transportadoraId: 7,
        codigo: 'CARGA-003 (novo)',
        origemRotulo: 'Origem 3',
        criadoEm: DateTime(2026, 9, 3, 9, 0),
      );
      final pedidoDoS2 = Pedido(
        id: '22222222-2222-2222-2222-222222222222',
        userId: 'u2',
        status: StatusPedido.aguardandoColeta,
        enderecoEntrega: 'Rua 2',
        total: '10.00',
        createdAt: DateTime(2026, 9, 2, 9, 5),
      );
      final linhaDoPedidoDoS2 =
          '${pedidoDoS2.idCurto} · ${pedidoDoS2.status.label}';

      final api = _FakeAdminApi(
        carregamentos: [s1, s2],
        pedidosPorCarregamento: {
          2: [pedidoDoS2],
        },
      );

      await tester.pumpWidget(
        MaterialApp(home: AdminShipmentsScreen(api: api)),
      );
      await tester.pumpAndSettle();

      // Expande o SEGUNDO card da lista — é o de `s2` (posição 1).
      await tester.tap(find.text('Ver pedidos').last);
      await tester.pumpAndSettle();
      expect(find.text(linhaDoPedidoDoS2), findsOneWidget);

      // Cria um carregamento novo: `fetchCarregamentos()` volta a ser
      // chamado (mesmo efeito do pull-to-refresh) e o novo lote entra na
      // FRENTE — exatamente o que a task 4 documenta para `GET /shipments`
      // ("mais recentes primeiro"). `s1`, que estava na posição 0, empurra
      // para a posição 1 — a mesma posição onde `s2` estava expandido.
      api.carregamentos = [s3Novo, s1, s2];
      await tester.fling(
        find.byType(RefreshIndicator),
        const Offset(0, 300),
        1000,
      );
      await tester.pumpAndSettle();

      // O pedido de `s2` continua só sob o card de `s2` — não vazou para
      // o card de `s1`, que agora ocupa a posição antiga de `s2`.
      expect(
        find.descendant(
          of: find.widgetWithText(AdminSectionCard, s2.codigo),
          matching: find.text(linhaDoPedidoDoS2),
        ),
        findsOneWidget,
      );
      expect(
        find.descendant(
          of: find.widgetWithText(AdminSectionCard, s1.codigo),
          matching: find.text(linhaDoPedidoDoS2),
        ),
        findsNothing,
      );
    },
  );

  testWidgets('o sino de notificações do admin abre /notifications', (
    tester,
  ) async {
    await tester.pumpWidget(
      MaterialApp(
        home: const AdminScaffold(
          tab: AdminTab.dashboard,
          titulo: 'Painel Administrativo',
          body: SizedBox.shrink(),
        ),
        routes: {
          '/notifications': (_) =>
              const Scaffold(body: Text('Notificações (destino)')),
        },
      ),
    );
    await tester.pumpAndSettle();

    final sino = find.byIcon(Icons.notifications_outlined);
    expect(sino, findsOneWidget);

    await tester.tap(sino);
    await tester.pumpAndSettle();

    expect(find.text('Notificações (destino)'), findsOneWidget);
  });
}
