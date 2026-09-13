import 'dart:async';

import 'package:flutter/foundation.dart';

import '../../../core/utils/jwt_utils.dart';
import '../domain/local_notifier.dart';
import '../domain/notification_model.dart';

/// Cria o timer periódico do ciclo. Injetável para o teste controlar o
/// relógio; o app usa `Timer.periodic`.
typedef CriarTimerPeriodico =
    Timer Function(Duration intervalo, void Function() aoDisparar);

/// Acompanhamento "em tempo real" das notificações enquanto o processo do app
/// está vivo: consulta `GET /notifications` a cada [intervaloPadrao] e manda
/// para a bandeja do sistema o que chegou desde a consulta anterior.
///
/// NÃO é push de servidor. O notification-service só grava as notificações no
/// Postgres; ninguém as envia ao aparelho (o FCM saiu na spec A). O que esta
/// classe faz é notificação LOCAL a partir de polling — por isso só funciona
/// com o app aberto ou em segundo plano ainda vivo. Ver
/// `docs/front-end/local_notifications.md`.
///
/// Ciclo de vida da sessão:
/// - [iniciar] é chamado a cada sessão nova (login ou troca de sessão da
///   demonstração, via `irParaTelaDoPapel`). Zera o estado e faz a primeira
///   consulta na hora, que só SEMEIA: o histórico existente conta como já
///   visto, para o login não despejar notificações antigas na bandeja.
/// - Cada ciclo relê o access token. Sem token (logout, sessão expirada) o
///   polling para sozinho — nenhum dos quatro caminhos de logout do app
///   precisa lembrar de chamar [parar]. Um token de outro usuário semeia de
///   novo, pelo mesmo motivo do login.
/// - Falhas (rede, 5xx, canal de notificação) são engolidas: o último estado
///   bom fica e o próximo ciclo tenta de novo. Só a primeira falha de uma
///   sequência vai para o log.
class NotificationsPoller extends ChangeNotifier {
  NotificationsPoller({
    required LocalNotifier notifier,
    required Future<List<NotificationModel>> Function() buscar,
    required Future<String?> Function() lerAccessToken,
    Duration intervalo = intervaloPadrao,
    CriarTimerPeriodico? criarTimer,
  }) : _notifier = notifier,
       _buscar = buscar,
       _lerAccessToken = lerAccessToken,
       _intervalo = intervalo,
       _criarTimer = criarTimer ?? _timerPeriodico;

  static const intervaloPadrao = Duration(seconds: 10);

  final LocalNotifier _notifier;
  final Future<List<NotificationModel>> Function() _buscar;
  final Future<String?> Function() _lerAccessToken;
  final Duration _intervalo;
  final CriarTimerPeriodico _criarTimer;

  static Timer _timerPeriodico(
    Duration intervalo,
    void Function() aoDisparar,
  ) => Timer.periodic(intervalo, (_) => aoDisparar());

  bool _ativo = false;

  /// Há uma sessão de usuário sendo acompanhada.
  bool get ativo => _ativo;

  List<NotificationModel> _itens = const [];

  /// A lista da última consulta bem-sucedida (mais recente primeiro).
  List<NotificationModel> get itens => _itens;

  int _naoLidas = 0;

  /// Quantas notificações da última consulta ainda não foram lidas.
  int get naoLidas => _naoLidas;

  int _versao = 0;

  /// Aumenta a cada consulta que trouxe notificação nova — é o sinal para a
  /// tela aberta recarregar, sem reagir a ciclos que não mudaram nada.
  int get versao => _versao;

  Timer? _timer;
  bool _disposed = false;
  bool _permissaoPedida = false;
  bool _falhando = false;

  /// Muda a cada [iniciar]/[parar]: uma consulta que termina depois disso é
  /// de uma sessão que já acabou, e o resultado dela é descartado.
  int _geracao = 0;

  /// Geração da consulta em andamento, para não empilhar duas da mesma
  /// sessão quando a rede demora mais que o intervalo.
  int? _consultandoGeracao;

  String? _usuario;
  bool _semeado = false;
  Set<String> _vistas = {};

  /// Começa a acompanhar a sessão atual, do zero. Seguro chamar de novo a
  /// cada login: cancela o ciclo anterior antes.
  Future<void> iniciar() async {
    _cancelarTimer();
    _geracao++;
    _zerarEstado();
    _ativo = true;
    _notificar();

    unawaited(_pedirPermissaoUmaVez());
    _timer = _criarTimer(_intervalo, () => unawaited(verificar()));
    await verificar();
  }

  /// Para de acompanhar e esquece a sessão.
  void parar() {
    _cancelarTimer();
    _geracao++;
    final mudou = _ativo || _itens.isNotEmpty;
    _ativo = false;
    _zerarEstado();
    if (mudou) _notificar();
  }

  /// Um ciclo: relê a sessão, consulta e notifica o que é novo. Nunca lança.
  Future<void> verificar() async {
    final geracao = _geracao;
    if (!_ativo || _consultandoGeracao == geracao) return;
    _consultandoGeracao = geracao;
    try {
      final token = await _lerAccessToken();
      if (geracao != _geracao) return;

      final usuario = token == null ? null : _usuarioNotificavel(token);
      if (usuario == null) {
        parar();
        return;
      }
      if (_usuario != null && usuario != _usuario) {
        // Outro usuário sem passar por [iniciar]: nada do anterior vale.
        _zerarEstado();
        _notificar();
      }
      _usuario = usuario;

      final lista = await _buscar();
      if (geracao != _geracao) return;

      await _aplicar(lista);
      _falhando = false;
    } catch (e) {
      if (!_falhando) {
        debugPrint(
          'NotificationsPoller: consulta falhou, tentando no próximo ciclo ($e)',
        );
      }
      _falhando = true;
    } finally {
      if (_consultandoGeracao == geracao) _consultandoGeracao = null;
    }
  }

  Future<void> _aplicar(List<NotificationModel> lista) async {
    final novas = _semeado
        ? lista
              .where((n) => n.readAt == null && !_vistas.contains(n.id))
              .toList()
        : const <NotificationModel>[];
    _vistas.addAll(lista.map((n) => n.id));
    _semeado = true;

    _itens = List.unmodifiable(lista);
    _naoLidas = lista.where((n) => n.readAt == null).length;
    if (novas.isNotEmpty) _versao++;
    _notificar();

    // A API devolve a mais recente primeiro; a bandeja recebe na ordem em
    // que aconteceram. Uma falha aqui não desfaz o "visto": repetir a mesma
    // notificação a cada ciclo seria pior do que perdê-la — ela continua na
    // lista e no contador do sino.
    for (final notificacao in novas.reversed) {
      try {
        await _notifier.mostrar(notificacao);
      } catch (e) {
        debugPrint(
          'NotificationsPoller: não foi possível mostrar a notificação ($e)',
        );
      }
    }
  }

  /// O `sub` de um token de usuário, ou `null` quando o token não serve às
  /// rotas de notificação. O de carregamento (`role: carregamento`) carrega
  /// no `sub` o id do lote, e o notification-service responde 403 a ele —
  /// consultar a cada ciclo só produziria erro.
  static String? _usuarioNotificavel(String token) {
    try {
      final payload = decodeJwtPayload(token);
      if (payload['role'] == 'carregamento') return null;
      final sub = payload['sub'];
      return sub is String && sub.isNotEmpty ? sub : null;
    } catch (_) {
      return null;
    }
  }

  Future<void> _pedirPermissaoUmaVez() async {
    if (_permissaoPedida) return;
    _permissaoPedida = true;
    try {
      await _notifier.pedirPermissao();
    } catch (e) {
      debugPrint('NotificationsPoller: pedido de permissão falhou ($e)');
    }
  }

  void _zerarEstado() {
    _usuario = null;
    _semeado = false;
    _vistas = {};
    _itens = const [];
    _naoLidas = 0;
  }

  void _cancelarTimer() {
    _timer?.cancel();
    _timer = null;
  }

  void _notificar() {
    if (!_disposed) notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    _cancelarTimer();
    super.dispose();
  }
}
