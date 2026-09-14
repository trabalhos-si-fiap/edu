import 'package:flutter/foundation.dart';

import '../../../core/network/token_store.dart';
import '../../../core/session/session_manager.dart';
import '../domain/notification_model.dart';
import '../domain/usuario_notificavel.dart';
import 'notifications_api.dart';

/// As notificações de uma sessão guardada que não é a ativa, com o `sub` do
/// dono — a chave da memória de vistas do poller.
typedef NotificacoesDeOutraSessao = ({
  String usuario,
  List<NotificationModel> itens,
});

/// Consulta `GET /notifications` de cada sessão guardada que NÃO é a ativa,
/// com o par de tokens da própria sessão.
///
/// RECURSO DE DEMONSTRAÇÃO — ver [SessionManager]. A gravação alterna os
/// quatro perfis num aparelho só, e a narração diz que o aluno acompanha tudo
/// em tempo real enquanto a câmera está no separador e no entregador: as
/// notificações do aluno precisam chegar à bandeja com outra sessão na tela.
///
/// Access token expirado (duram 60 minutos) responde 401: a sessão é
/// renovada com o próprio refresh token e o par novo volta para a sessão
/// guardada via [SessionManager.atualizarTokens] — nunca para o
/// [TokenStore], que é de quem está na tela. Uma sessão que não se renova
/// (refresh vencido, usuário desativado) ou que falha por rede fica de fora
/// do ciclo; o próximo tenta de novo. Só a primeira falha de uma sequência,
/// por papel, vai para o log — sem token e sem conteúdo de notificação.
class OutrasSessoesGuardadas {
  OutrasSessoesGuardadas({
    required SessionManager sessoes,
    required Future<List<NotificationModel>> Function(String accessToken)
    buscarComToken,
    required Future<TokenPair?> Function(String refreshToken) renovar,
  }) : _sessoes = sessoes,
       _buscarComToken = buscarComToken,
       _renovar = renovar;

  final SessionManager _sessoes;
  final Future<List<NotificationModel>> Function(String accessToken)
  _buscarComToken;
  final Future<TokenPair?> Function(String refreshToken) _renovar;

  /// Papéis cuja última consulta falhou — para logar só a primeira.
  final Set<String> _falhando = {};

  /// As notificações de cada sessão guardada cujo usuário não é
  /// [usuarioAtivo] (a sessão ativa já é consultada pelo poller). As sessões
  /// são consultadas uma de cada vez: a renovação regrava o armazenamento
  /// das sessões inteiro, e duas em paralelo perderiam uma das gravações.
  /// A falha de uma sessão não lança; só a leitura do próprio armazenamento
  /// seguro pode, e o poller a engole.
  Future<List<NotificacoesDeOutraSessao>> buscar(String usuarioAtivo) async {
    final sessoes = await _sessoes.listar();
    final resultado = <NotificacoesDeOutraSessao>[];
    for (final sessao in sessoes) {
      final notificacoes = await _consultar(sessao.papel, usuarioAtivo);
      if (notificacoes != null) resultado.add(notificacoes);
    }
    return resultado;
  }

  Future<NotificacoesDeOutraSessao?> _consultar(
    String papel,
    String usuarioAtivo,
  ) async {
    try {
      final par = await _sessoes.lerTokens(papel);
      if (par == null) return null;
      final usuario = usuarioNotificavel(par.accessToken);
      if (usuario == null || usuario == usuarioAtivo) return null;

      List<NotificationModel> itens;
      try {
        itens = await _buscarComToken(par.accessToken);
      } on NotificationsUnauthorizedException {
        final novo = await _renovar(par.refreshToken);
        if (novo == null) {
          _registrarFalha(papel, 'renovação do token recusada');
          return null;
        }
        await _sessoes.atualizarTokens(papel, novo);
        itens = await _buscarComToken(novo.accessToken);
      }

      _falhando.remove(papel);
      return (usuario: usuario, itens: itens);
    } catch (e) {
      _registrarFalha(papel, e);
      return null;
    }
  }

  void _registrarFalha(String papel, Object erro) {
    if (!_falhando.add(papel)) return;
    debugPrint(
      'OutrasSessoesGuardadas: sessão "$papel" fora deste ciclo, tentando no '
      'próximo (${_descrever(erro)})',
    );
  }

  /// Texto fixo ou só o tipo do erro: a mensagem de um erro qualquer pode
  /// trazer trecho de resposta, e isso não vai para o logcat.
  static String _descrever(Object erro) => erro is String
      ? erro
      : erro is NotificationsException
      ? erro.message
      : erro.runtimeType.toString();
}
