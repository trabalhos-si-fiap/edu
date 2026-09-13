import 'notification_model.dart';

/// O payload que viaja com a notificação da bandeja do sistema até o toque.
///
/// Leva só o id da ocorrência, quando há: é a única informação que muda o
/// destino do toque (a tela de resolução, em vez da lista). A chave lida é
/// `occurrence_id`, a mesma da `NotificationsScreen` — o contrato público do
/// notification-service é em inglês.
String payloadDaNotificacao(NotificationModel notificacao) {
  final ocorrenciaId = notificacao.data?['occurrence_id'];
  return ocorrenciaId is num ? '${ocorrenciaId.toInt()}' : '';
}

/// O id da ocorrência de um payload montado por [payloadDaNotificacao], ou
/// `null` quando a notificação não tem ocorrência.
int? ocorrenciaDoPayload(String? payload) =>
    payload == null ? null : int.tryParse(payload);
