import 'package:edu_ia/features/notifications/data/plugin_local_notifier.dart';
import 'package:edu_ia/features/notifications/domain/local_notifier.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/domain/notification_payload.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_test/flutter_test.dart';

/// O adaptador fala com o plugin só pelo canal de plataforma; aqui o canal é
/// respondido pelo teste, do mesmo jeito que os testes do próprio plugin
/// fazem — nenhum aparelho envolvido.
const _canal = MethodChannel('dexterous.com/flutter/local_notifications');

NotificationModel _n(String id, {Map<String, dynamic>? data}) =>
    NotificationModel(
      id: id,
      title: 'Pedido #ABCDEF12: saiu para entrega',
      body: 'Seu pedido saiu para entrega.',
      createdAt: DateTime(2026, 9, 13),
      data: data,
    );

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  AndroidFlutterLocalNotificationsPlugin.registerWith();

  final chamadas = <MethodCall>[];
  final mensageiro =
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  setUp(() {
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
    mensageiro.setMockMethodCallHandler(_canal, (chamada) async {
      chamadas.add(chamada);
      if (chamada.method == 'initialize') return true;
      if (chamada.method == 'requestNotificationsPermission') return true;
      return null;
    });
  });

  tearDown(() {
    chamadas.clear();
    mensageiro.setMockMethodCallHandler(_canal, null);
    debugDefaultTargetPlatformOverride = null;
  });

  test(
    'pedir permissão inicializa com o ícone do launcher e cria o canal "pedidos" antes',
    () async {
      final notifier = PluginLocalNotifier(aoTocar: (_) {});

      await notifier.pedirPermissao();

      expect(chamadas.map((c) => c.method), [
        'initialize',
        'createNotificationChannel',
        'requestNotificationsPermission',
      ]);
      expect(chamadas[0].arguments['defaultIcon'], '@mipmap/ic_launcher');
      expect(chamadas[1].arguments['id'], 'pedidos');
      expect(chamadas[1].arguments['name'], 'Pedidos');
    },
  );

  test(
    'mostrar manda título, corpo, o canal e o payload da ocorrência',
    () async {
      final notifier = PluginLocalNotifier(aoTocar: (_) {});

      await notifier.mostrar(_n('42', data: const {'occurrence_id': 7}));

      final show = chamadas.singleWhere((c) => c.method == 'show');
      expect(show.arguments['id'], 42);
      expect(show.arguments['title'], 'Pedido #ABCDEF12: saiu para entrega');
      expect(show.arguments['body'], 'Seu pedido saiu para entrega.');
      expect(show.arguments['payload'], '7');
      expect(show.arguments['platformSpecifics']['channelId'], 'pedidos');
    },
  );

  test(
    'mostrar de outra sessão guardada mantém título e corpo e marca o payload',
    () async {
      final notifier = PluginLocalNotifier(aoTocar: (_) {});

      await notifier.mostrar(
        _n('43', data: const {'occurrence_id': 7}),
        deOutraSessao: true,
      );

      final show = chamadas.singleWhere((c) => c.method == 'show');
      expect(show.arguments['id'], 43);
      expect(show.arguments['title'], 'Pedido #ABCDEF12: saiu para entrega');
      expect(show.arguments['body'], 'Seu pedido saiu para entrega.');
      expect(show.arguments['payload'], payloadDeOutraSessao);
    },
  );

  test('inicializa uma vez só', () async {
    final notifier = PluginLocalNotifier(aoTocar: (_) {});

    await notifier.mostrar(_n('1'));
    await notifier.mostrar(_n('2'));

    expect(chamadas.where((c) => c.method == 'initialize'), hasLength(1));
  });

  test('um id que não é número ainda vira um id de sistema válido', () async {
    final notifier = PluginLocalNotifier(aoTocar: (_) {});

    await notifier.mostrar(_n('não-numérico'));

    final id = chamadas.singleWhere((c) => c.method == 'show').arguments['id'];
    expect(id, isA<int>());
    expect(id, inInclusiveRange(0, 0x7fffffff));
  });

  test('o toque na notificação entrega o payload', () async {
    String? recebido;
    final notifier = PluginLocalNotifier(aoTocar: (p) => recebido = p);
    await notifier.mostrar(_n('42', data: const {'occurrence_id': 7}));

    await mensageiro.handlePlatformMessage(
      _canal.name,
      _canal.codec.encodeMethodCall(
        const MethodCall('didReceiveNotificationResponse', {
          'notificationId': 42,
          'payload': '7',
          'notificationResponseType': 0,
        }),
      ),
      (_) {},
    );

    expect(recebido, '7');
  });

  test(
    'só o Android usa o plugin; o resto do app recebe o notificador inerte',
    () {
      expect(criarLocalNotifier(aoTocar: (_) {}), isA<PluginLocalNotifier>());

      for (final plataforma in [TargetPlatform.linux, TargetPlatform.iOS]) {
        debugDefaultTargetPlatformOverride = plataforma;
        expect(criarLocalNotifier(aoTocar: (_) {}), isA<LocalNotifierInerte>());
      }
    },
  );
}
