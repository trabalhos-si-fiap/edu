import 'dart:convert';

import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/core/session/session_manager.dart';
import 'package:edu_ia/features/notifications/data/notifications_api.dart';
import 'package:edu_ia/features/notifications/data/outras_sessoes_guardadas.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';

/// O [TokenStore] da sessão ATIVA, em memória. Nada aqui pode ser escrito
/// por quem consulta as outras sessões.
class _TokenStoreFalso extends TokenStore {
  String? access;
  String? refresh;
  int gravacoes = 0;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    gravacoes++;
    access = accessToken;
    refresh = refreshToken;
  }

  @override
  Future<String?> readAccessToken() async => access;

  @override
  Future<String?> readRefreshToken() async => refresh;
}

class _MemoriaSegura implements SecureStorageLike {
  final Map<String, String> _valores = {};

  @override
  Future<String?> read({required String key}) async => _valores[key];

  @override
  Future<void> write({required String key, required String? value}) async {
    if (value == null) {
      _valores.remove(key);
    } else {
      _valores[key] = value;
    }
  }

  @override
  Future<void> delete({required String key}) async => _valores.remove(key);
}

/// Um token com o formato do backend (`sub` + `role`); o `v` distingue o par
/// renovado do original. A assinatura não importa, o app nunca a verifica.
String _token(String sub, {String role = 'student', int v = 1}) {
  String parte(Map<String, Object> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  return '${parte({'alg': 'HS256'})}.'
      '${parte({'sub': sub, 'role': role, 'v': v})}.assinatura';
}

NotificationModel _n(String id) => NotificationModel(
  id: id,
  title: 'T$id',
  body: 'C$id',
  createdAt: DateTime(2026, 9, 13),
);

class _Cenario {
  final ativa = _TokenStoreFalso();
  late final manager = SessionManager(
    storage: _MemoriaSegura(),
    tokenStore: ativa,
  );

  /// Resposta de `GET /notifications` por access token; ausente = 401.
  final respostas = <String, Object>{};
  final consultas = <String>[];

  /// Par devolvido pelo refresh, por refresh token; ausente = recusado.
  final renovacoes = <String, TokenPair>{};
  final pedidosDeRenovacao = <String>[];

  late final fonte = OutrasSessoesGuardadas(
    sessoes: manager,
    buscarComToken: (access) async {
      consultas.add(access);
      final resposta = respostas[access];
      if (resposta == null) throw NotificationsUnauthorizedException();
      if (resposta is Exception) throw resposta;
      return resposta as List<NotificationModel>;
    },
    renovar: (refresh) async {
      pedidosDeRenovacao.add(refresh);
      return renovacoes[refresh];
    },
  );

  /// Loga como [papel] (par no TokenStore ativo) e guarda a sessão — o que o
  /// login faz com `DEMO_MULTI_SESSAO`.
  Future<void> guardar(String papel, String access, String refresh) async {
    await ativa.save(accessToken: access, refreshToken: refresh);
    await manager.guardarSessaoAtual(papel: papel, nome: papel);
  }
}

void main() {
  late _Cenario c;
  late List<String> logs;
  late DebugPrintCallback debugPrintOriginal;

  final alunoA = _token('aluno-1');
  final separadorA = _token('separador-1', role: 'separador');

  setUp(() {
    c = _Cenario();
    logs = [];
    debugPrintOriginal = debugPrint;
    debugPrint = (String? mensagem, {int? wrapWidth}) => logs.add('$mensagem');
  });

  tearDown(() => debugPrint = debugPrintOriginal);

  test(
    'devolve as notificações de cada sessão guardada, menos a do usuário ativo',
    () async {
      await c.guardar('student', alunoA, 'r-aluno');
      await c.guardar('separador', separadorA, 'r-sep');
      c.respostas[alunoA] = [_n('2'), _n('1')];
      c.respostas[separadorA] = [_n('s1')];

      final resultado = await c.fonte.buscar('separador-1');

      expect(resultado, hasLength(1));
      expect(resultado.single.usuario, 'aluno-1');
      expect(resultado.single.itens.map((n) => n.id), ['2', '1']);
      // A sessão ativa já é consultada pelo poller; aqui ela nem é tocada.
      expect(c.consultas, [alunoA]);
    },
  );

  test(
    'token expirado: renova com o refresh daquela sessão, grava o par novo nela e consulta de novo',
    () async {
      await c.guardar('student', alunoA, 'r-aluno');
      await c.guardar('separador', separadorA, 'r-sep');
      final alunoB = _token('aluno-1', v: 2);
      c.renovacoes['r-aluno'] = (
        accessToken: alunoB,
        refreshToken: 'r-aluno-2',
      );
      c.respostas[alunoB] = [_n('1')];
      final gravacoesAntes = c.ativa.gravacoes;

      final resultado = await c.fonte.buscar('separador-1');

      expect(c.pedidosDeRenovacao, ['r-aluno']);
      expect(c.consultas, [alunoA, alunoB]);
      expect(resultado.single.usuario, 'aluno-1');
      expect(resultado.single.itens.map((n) => n.id), ['1']);

      final guardado = await c.manager.lerTokens('student');
      expect(guardado?.accessToken, alunoB);
      expect(guardado?.refreshToken, 'r-aluno-2');
      // A sessão na tela (separador) continua intacta.
      expect(c.ativa.gravacoes, gravacoesAntes);
      expect(c.ativa.access, separadorA);
      expect(c.ativa.refresh, 'r-sep');

      // O ciclo seguinte já usa o par renovado, sem renovar de novo.
      await c.fonte.buscar('separador-1');
      expect(c.pedidosDeRenovacao, ['r-aluno']);
      expect(c.consultas.last, alunoB);
    },
  );

  test(
    'refresh recusado: pula a sessão sem lançar, sem gravar e sem derrubar as outras',
    () async {
      final adminA = _token('admin-1', role: 'admin');
      await c.guardar('student', alunoA, 'r-aluno');
      await c.guardar('admin', adminA, 'r-admin');
      await c.guardar('separador', separadorA, 'r-sep');
      c.respostas[adminA] = [_n('a1')];

      final resultado = await c.fonte.buscar('separador-1');

      expect(resultado.map((r) => r.usuario), ['admin-1']);
      expect(c.pedidosDeRenovacao, ['r-aluno']);
      final guardado = await c.manager.lerTokens('student');
      expect(guardado?.accessToken, alunoA);
      expect(guardado?.refreshToken, 'r-aluno');
      expect(c.ativa.access, separadorA);
    },
  );

  test(
    'uma sessão que segue falhando vai para o log uma vez só, e de novo depois de voltar',
    () async {
      await c.guardar('student', alunoA, 'r-aluno');
      await c.guardar('separador', separadorA, 'r-sep');

      await c.fonte.buscar('separador-1');
      await c.fonte.buscar('separador-1');
      await c.fonte.buscar('separador-1');
      expect(logs, hasLength(1));
      // Nada de token no log.
      expect(logs.single, isNot(contains(alunoA)));
      expect(logs.single, isNot(contains('r-aluno')));

      c.respostas[alunoA] = [_n('1')];
      await c.fonte.buscar('separador-1');
      c.respostas.remove(alunoA);
      await c.fonte.buscar('separador-1');
      expect(logs, hasLength(2));
    },
  );

  test('falha de rede numa sessão não lança nem tenta renovar', () async {
    await c.guardar('student', alunoA, 'r-aluno');
    await c.guardar('separador', separadorA, 'r-sep');
    c.respostas[alunoA] = NotificationsException(
      'Não foi possível conectar ao servidor',
    );

    final resultado = await c.fonte.buscar('separador-1');

    expect(resultado, isEmpty);
    expect(c.pedidosDeRenovacao, isEmpty);
  });

  test('sessão de carregamento guardada não é consultada', () async {
    // O backend responde 403 a esse token em /notifications.
    await c.guardar('carregamento', _token('42', role: 'carregamento'), 'r-c');
    await c.guardar('separador', separadorA, 'r-sep');

    final resultado = await c.fonte.buscar('separador-1');

    expect(resultado, isEmpty);
    expect(c.consultas, isEmpty);
  });

  test('sem sessões guardadas, não consulta nada', () async {
    expect(await c.fonte.buscar('aluno-1'), isEmpty);
    expect(c.consultas, isEmpty);
  });
}
