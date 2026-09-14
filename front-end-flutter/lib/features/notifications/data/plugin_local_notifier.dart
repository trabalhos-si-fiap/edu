import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

import '../domain/local_notifier.dart';
import '../domain/notification_model.dart';
import '../domain/notification_payload.dart';

/// O notificador que o app usa nesta plataforma.
///
/// Só o Android tem a bandeja configurada. No iOS o plugin exigiria mexer no
/// `AppDelegate` para apresentar notificação com o app em primeiro plano, e o
/// Linux desktop e a web não são alvo da demonstração — nesses, o notificador
/// inerte deixa o sino e a lista funcionando sem tocar em canal de plataforma.
LocalNotifier criarLocalNotifier({
  required void Function(String? payload) aoTocar,
}) {
  if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
    return PluginLocalNotifier(aoTocar: aoTocar);
  }
  return const LocalNotifierInerte();
}

/// [LocalNotifier] sobre `flutter_local_notifications`, para Android.
///
/// A inicialização é preguiçosa (na primeira permissão ou notificação, ou
/// seja, no primeiro login do processo): o app não paga o canal de plataforma
/// na abertura, e a tela de login não depende do plugin.
class PluginLocalNotifier implements LocalNotifier {
  PluginLocalNotifier({
    required void Function(String? payload) aoTocar,
    FlutterLocalNotificationsPlugin? plugin,
  }) : _aoTocar = aoTocar,
       _plugin = plugin ?? FlutterLocalNotificationsPlugin();

  final void Function(String? payload) _aoTocar;
  final FlutterLocalNotificationsPlugin _plugin;

  static const canal = AndroidNotificationChannel(
    'pedidos',
    'Pedidos',
    description:
        'Andamento dos pedidos, avisado enquanto o app está aberto ou em '
        'segundo plano.',
    importance: Importance.high,
  );

  /// Ícone pequeno da notificação: o do launcher, único recurso de ícone que
  /// o app já tem. O Android o desenha como silhueta monocromática.
  static const _icone = '@mipmap/ic_launcher';

  Future<void>? _inicializacao;

  @override
  Future<void> pedirPermissao() async {
    await _inicializar();
    await _android?.requestNotificationsPermission();
  }

  @override
  Future<void> mostrar(NotificationModel notificacao) async {
    await _inicializar();
    await _plugin.show(
      id: _idDoSistema(notificacao.id),
      title: notificacao.title,
      body: notificacao.body,
      notificationDetails: NotificationDetails(
        android: AndroidNotificationDetails(
          canal.id,
          canal.name,
          channelDescription: canal.description,
          importance: Importance.high,
          priority: Priority.high,
          icon: _icone,
          styleInformation: BigTextStyleInformation(notificacao.body),
        ),
      ),
      payload: payloadDaNotificacao(notificacao),
    );
  }

  AndroidFlutterLocalNotificationsPlugin? get _android => _plugin
      .resolvePlatformSpecificImplementation<
        AndroidFlutterLocalNotificationsPlugin
      >();

  /// Uma só vez por instância; se falhar, a próxima chamada tenta de novo em
  /// vez de herdar o erro para sempre.
  Future<void> _inicializar() =>
      _inicializacao ??= _fazerInicializacao().catchError((Object erro) {
        _inicializacao = null;
        throw erro;
      });

  Future<void> _fazerInicializacao() async {
    await _plugin.initialize(
      settings: const InitializationSettings(
        android: AndroidInitializationSettings(_icone),
      ),
      onDidReceiveNotificationResponse: (resposta) =>
          _aoTocar(resposta.payload),
    );
    await _android?.createNotificationChannel(canal);
  }

  /// O plugin exige um `int` de 32 bits com sinal. Os ids do
  /// notification-service são inteiros em texto; qualquer outro formato cai
  /// no hash, que só precisa ser estável para a mesma notificação.
  static int _idDoSistema(String id) =>
      (int.tryParse(id) ?? id.hashCode) & 0x7fffffff;
}
