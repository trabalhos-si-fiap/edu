import '../../../core/utils/jwt_utils.dart';

/// O `sub` de um token de usuário, ou `null` quando o token não serve às
/// rotas de notificação. O de carregamento (`role: carregamento`) carrega no
/// `sub` o id do lote, e o notification-service responde 403 a ele —
/// consultar a cada ciclo só produziria erro.
String? usuarioNotificavel(String token) {
  try {
    final payload = decodeJwtPayload(token);
    if (payload['role'] == 'carregamento') return null;
    final sub = payload['sub'];
    return sub is String && sub.isNotEmpty ? sub : null;
  } catch (_) {
    return null;
  }
}
