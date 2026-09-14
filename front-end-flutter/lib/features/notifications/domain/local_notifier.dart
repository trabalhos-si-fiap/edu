import 'notification_model.dart';

/// Superfície mínima para mostrar uma notificação do sistema operacional — só
/// o que o `NotificationsPoller` usa, não a API inteira do plugin. É o que
/// torna o poller testável sem canal de plataforma: os testes injetam um
/// notificador falso e o app injeta o adaptador de
/// `flutter_local_notifications` (`data/plugin_local_notifier.dart`).
abstract class LocalNotifier {
  /// Pede ao sistema permissão para notificar (Android 13+). Pode não fazer
  /// nada onde a permissão não existe ou já foi decidida pelo usuário.
  Future<void> pedirPermissao();

  /// Mostra [notificacao] na bandeja do sistema. [deOutraSessao] marca uma
  /// notificação de sessão guardada que não é a ativa (demonstração
  /// multi-sessão), para o toque não abrir as telas de quem está na tela.
  Future<void> mostrar(
    NotificationModel notificacao, {
    bool deOutraSessao = false,
  });
}

/// Notificador que não faz nada: o que o app usa onde não há notificação do
/// sistema configurada (Linux desktop, iOS, web). O sino e a lista continuam
/// funcionando — só a bandeja do sistema fica de fora.
class LocalNotifierInerte implements LocalNotifier {
  const LocalNotifierInerte();

  @override
  Future<void> pedirPermissao() async {}

  @override
  Future<void> mostrar(
    NotificationModel notificacao, {
    bool deOutraSessao = false,
  }) async {}
}
