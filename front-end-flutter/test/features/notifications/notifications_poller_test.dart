import 'dart:async';
import 'dart:convert';

import 'package:edu_ia/features/notifications/data/notifications_api.dart';
import 'package:edu_ia/features/notifications/data/outras_sessoes_guardadas.dart';
import 'package:edu_ia/features/notifications/domain/local_notifier.dart';
import 'package:edu_ia/features/notifications/domain/notification_model.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_poller.dart';
import 'package:flutter_test/flutter_test.dart';

/// Guarda o que teria ido para a bandeja do sistema, sem canal de plataforma.
class _NotificadorFalso implements LocalNotifier {
  final mostradas = <String>[];

  /// Subconjunto de [mostradas] que veio de outra sessão guardada.
  final deOutraSessao = <String>[];
  int pedidosDePermissao = 0;
  bool falhar = false;

  @override
  Future<void> pedirPermissao() async => pedidosDePermissao++;

  @override
  Future<void> mostrar(
    NotificationModel notificacao, {
    bool deOutraSessao = false,
  }) async {
    if (falhar) throw Exception('canal indisponível');
    mostradas.add(notificacao.id);
    if (deOutraSessao) this.deOutraSessao.add(notificacao.id);
  }
}

/// Timer que só dispara quando o teste manda — o relógio é do teste.
class _TimerFalso implements Timer {
  _TimerFalso(this.intervalo, this.aoDisparar);

  final Duration intervalo;
  final void Function() aoDisparar;
  bool _ativo = true;

  @override
  void cancel() => _ativo = false;

  @override
  bool get isActive => _ativo;

  @override
  int get tick => 0;
}

NotificationModel _n(String id, {bool lida = false}) => NotificationModel(
  id: id,
  title: 'Título $id',
  body: 'Corpo $id',
  createdAt: DateTime(2026, 9, 13),
  readAt: lida ? DateTime(2026, 9, 13) : null,
);

/// Um access token com o formato do backend (`sub` + `role`); a assinatura
/// não importa, o app nunca a verifica.
String _token(String sub, {String role = 'student'}) {
  String parte(Map<String, Object> m) =>
      base64Url.encode(utf8.encode(jsonEncode(m))).replaceAll('=', '');
  return '${parte({'alg': 'HS256'})}.${parte({'sub': sub, 'role': role})}.assinatura';
}

class _Cenario {
  List<NotificationModel> lista = [];
  Object? erro;
  String? token = _token('aluno-1');
  int buscas = 0;

  /// Quando presente, a próxima busca fica pendurada neste completer.
  Completer<List<NotificationModel>>? pendente;

  final notificador = _NotificadorFalso();
  final timers = <_TimerFalso>[];

  /// Demonstração multi-sessão (`DEMO_MULTI_SESSAO`). Definir antes do
  /// primeiro uso do [poller].
  bool multiSessao = false;

  /// O que as outras sessões guardadas devolvem a cada ciclo.
  List<NotificacoesDeOutraSessao> outras = [];
  Object? erroOutras;
  Completer<List<NotificacoesDeOutraSessao>>? outrasPendente;

  /// O usuário ativo informado a cada consulta das outras sessões.
  final consultasOutras = <String>[];

  late final poller = NotificationsPoller(
    notifier: notificador,
    multiSessao: multiSessao,
    buscarOutrasSessoes: (usuarioAtivo) async {
      consultasOutras.add(usuarioAtivo);
      final espera = outrasPendente;
      if (espera != null) {
        outrasPendente = null;
        return espera.future;
      }
      if (erroOutras != null) throw erroOutras!;
      return outras;
    },
    buscar: () async {
      buscas++;
      final espera = pendente;
      if (espera != null) {
        pendente = null;
        return espera.future;
      }
      if (erro != null) throw erro!;
      return lista;
    },
    lerAccessToken: () async => token,
    criarTimer: (intervalo, aoDisparar) {
      final timer = _TimerFalso(intervalo, aoDisparar);
      timers.add(timer);
      return timer;
    },
  );
}

void main() {
  late _Cenario c;

  setUp(() => c = _Cenario());

  test(
    'a primeira verificação após o login só semeia: o histórico não vira notificação',
    () async {
      c.lista = [_n('2'), _n('1', lida: true), _n('0')];

      await c.poller.iniciar();

      expect(c.poller.ativo, isTrue);
      expect(c.buscas, 1);
      expect(c.notificador.mostradas, isEmpty);
      expect(c.poller.naoLidas, 2);
      expect(c.poller.itens.map((n) => n.id), ['2', '1', '0']);
    },
  );

  test(
    'uma notificação nova e não lida vai para a bandeja uma única vez',
    () async {
      c.lista = [_n('1')];
      await c.poller.iniciar();
      final versaoAntes = c.poller.versao;

      c.lista = [_n('3'), _n('2'), _n('1')];
      await c.poller.verificar();
      await c.poller.verificar();

      // Mais antiga primeiro, na ordem em que aconteceram.
      expect(c.notificador.mostradas, ['2', '3']);
      expect(c.poller.naoLidas, 3);
      expect(c.poller.versao, versaoAntes + 1);
    },
  );

  test(
    'uma notificação nova que já chega lida não vai para a bandeja',
    () async {
      c.lista = [_n('1')];
      await c.poller.iniciar();

      c.lista = [_n('2', lida: true), _n('1')];
      await c.poller.verificar();

      expect(c.notificador.mostradas, isEmpty);
    },
  );

  test(
    'agenda o ciclo a cada 10 segundos, e cada disparo verifica de novo',
    () async {
      c.lista = [_n('1')];
      await c.poller.iniciar();

      expect(c.timers, hasLength(1));
      expect(c.timers.single.intervalo, const Duration(seconds: 10));

      c.lista = [_n('2'), _n('1')];
      c.timers.single.aoDisparar();
      await pumpEventQueue();

      expect(c.notificador.mostradas, ['2']);
    },
  );

  test('pede permissão ao iniciar, uma vez por processo', () async {
    await c.poller.iniciar();
    await c.poller.iniciar();

    expect(c.notificador.pedidosDePermissao, 1);
  });

  test('para quando a sessão acaba: o logout apaga o token', () async {
    c.lista = [_n('1')];
    await c.poller.iniciar();

    c.token = null;
    await c.poller.verificar();

    expect(c.poller.ativo, isFalse);
    expect(c.timers.single.isActive, isFalse);
    expect(c.poller.naoLidas, 0);
    expect(c.poller.itens, isEmpty);
    // Sem token não há busca — nem nesta verificação, nem nas seguintes.
    await c.poller.verificar();
    expect(c.buscas, 1);
  });

  test('parar() cancela o timer e nenhuma busca acontece depois', () async {
    await c.poller.iniciar();

    c.poller.parar();
    await c.poller.verificar();

    expect(c.poller.ativo, isFalse);
    expect(c.timers.single.isActive, isFalse);
    expect(c.buscas, 1);
  });

  test(
    'um novo login semeia de novo: o histórico da nova sessão não vira notificação',
    () async {
      c.lista = [_n('1')];
      await c.poller.iniciar();

      c.token = _token('admin-1', role: 'admin');
      c.lista = [_n('a2'), _n('a1')];
      await c.poller.iniciar();

      expect(c.notificador.mostradas, isEmpty);
      expect(c.poller.itens.map((n) => n.id), ['a2', 'a1']);
      expect(c.timers.first.isActive, isFalse);
      expect(c.timers.last.isActive, isTrue);
    },
  );

  test(
    'outro usuário no token sem novo iniciar() também semeia, em vez de despejar o histórico',
    () async {
      c.lista = [_n('1')];
      await c.poller.iniciar();

      c.token = _token('aluno-2');
      c.lista = [_n('b2'), _n('b1')];
      await c.poller.verificar();
      expect(c.notificador.mostradas, isEmpty);

      c.lista = [_n('b3'), _n('b2'), _n('b1')];
      await c.poller.verificar();
      expect(c.notificador.mostradas, ['b3']);
    },
  );

  test(
    'voltar para um usuário já acompanhado neste processo mostra o que chegou enquanto estava fora',
    () async {
      // A apresentação alterna os quatro perfis no mesmo aparelho: o que o
      // separador faz vira notificação da Ana enquanto a sessão dela está
      // guardada. Ao voltar, isso é novo para ela — não é histórico.
      c.lista = [_n('1')];
      await c.poller.iniciar();

      c.token = _token('separador-1', role: 'separador');
      c.lista = [_n('s1')];
      await c.poller.iniciar();

      c.token = _token('aluno-1');
      c.lista = [_n('3'), _n('2'), _n('1')];
      await c.poller.iniciar();

      expect(c.notificador.mostradas, ['2', '3']);
    },
  );

  test('um ciclo manda no máximo 5 para a bandeja, as mais recentes', () async {
    c.lista = [_n('0')];
    await c.poller.iniciar();

    c.lista = [for (var i = 8; i >= 0; i--) _n('$i')];
    await c.poller.verificar();

    expect(c.notificador.mostradas, ['4', '5', '6', '7', '8']);
    // As que ficaram de fora continuam no contador e na lista.
    expect(c.poller.naoLidas, 9);
    await c.poller.verificar();
    expect(c.notificador.mostradas, hasLength(5));
  });

  test('a resposta atrasada da sessão anterior é descartada', () async {
    final antiga = Completer<List<NotificationModel>>();
    c.pendente = antiga;
    unawaited(c.poller.iniciar());
    await pumpEventQueue();

    c.token = _token('aluno-2');
    c.lista = [_n('x1')];
    await c.poller.iniciar();

    antiga.complete([_n('velha-2'), _n('velha-1')]);
    await pumpEventQueue();
    await c.poller.verificar();

    expect(c.poller.itens.map((n) => n.id), ['x1']);
    expect(c.notificador.mostradas, isEmpty);
  });

  test('falha na busca é engolida e o último estado bom continua', () async {
    c.lista = [_n('1')];
    await c.poller.iniciar();

    c.erro = NotificationsException('Não foi possível conectar ao servidor');
    await c.poller.verificar();
    await c.poller.verificar();

    expect(c.poller.ativo, isTrue);
    expect(c.poller.naoLidas, 1);

    c.erro = null;
    c.lista = [_n('2'), _n('1')];
    await c.poller.verificar();
    expect(c.notificador.mostradas, ['2']);
  });

  test(
    'falha ao mostrar é engolida e não repete a notificação no ciclo seguinte',
    () async {
      c.lista = [_n('1')];
      await c.poller.iniciar();

      c.notificador.falhar = true;
      c.lista = [_n('2'), _n('1')];
      await c.poller.verificar();

      c.notificador.falhar = false;
      await c.poller.verificar();

      expect(c.notificador.mostradas, isEmpty);
      expect(c.poller.naoLidas, 2);
    },
  );

  test(
    'token de carregamento não é sessão de usuário: não busca nem fica ativo',
    () async {
      // O backend responde 403 a este token em /notifications: o `sub` é o id
      // do lote, não de um usuário.
      c.token = _token('42', role: 'carregamento');

      await c.poller.iniciar();

      expect(c.buscas, 0);
      expect(c.poller.ativo, isFalse);
    },
  );

  group('outras sessões guardadas (demonstração multi-sessão)', () {
    // A gravação alterna os quatro perfis num aparelho só; a narração diz que
    // o aluno acompanha tudo em tempo real enquanto a câmera está no separador
    // e no entregador.
    setUp(() {
      c.multiSessao = true;
      c.token = _token('separador-1', role: 'separador');
      c.lista = [_n('s1')];
    });

    test(
      'uma notificação nova de outra sessão vai para a bandeja, sem mexer no sino da sessão ativa',
      () async {
        c.outras = [
          (usuario: 'aluno-1', itens: [_n('1')]),
        ];
        await c.poller.iniciar();
        // Primeira vez que o aluno aparece neste processo: só semeia.
        expect(c.notificador.mostradas, isEmpty);
        final versaoAntes = c.poller.versao;

        c.outras = [
          (usuario: 'aluno-1', itens: [_n('3'), _n('2'), _n('1')]),
        ];
        await c.poller.verificar();
        await c.poller.verificar();

        expect(c.notificador.mostradas, ['2', '3']);
        expect(c.notificador.deOutraSessao, ['2', '3']);
        expect(c.consultasOutras, everyElement('separador-1'));
        // Sino, lista e versão continuam sendo só do separador.
        expect(c.poller.itens.map((n) => n.id), ['s1']);
        expect(c.poller.naoLidas, 1);
        expect(c.poller.versao, versaoAntes);
      },
    );

    test(
      'o que chegou com outra sessão na tela não se repete ao voltar para ela',
      () async {
        c.outras = [
          (usuario: 'aluno-1', itens: [_n('1')]),
        ];
        await c.poller.iniciar();
        c.outras = [
          (usuario: 'aluno-1', itens: [_n('2'), _n('1')]),
        ];
        await c.poller.verificar();
        expect(c.notificador.mostradas, ['2']);

        c.token = _token('aluno-1');
        c.lista = [_n('2'), _n('1')];
        c.outras = [];
        await c.poller.iniciar();

        expect(c.notificador.mostradas, ['2']);
        expect(c.poller.naoLidas, 2);
      },
    );

    test('a sessão ativa continua avisando normalmente', () async {
      await c.poller.iniciar();

      c.lista = [_n('s2'), _n('s1')];
      await c.poller.verificar();

      expect(c.notificador.mostradas, ['s2']);
      expect(c.notificador.deOutraSessao, isEmpty);
    });

    test('outra sessão também manda no máximo 5 por consulta', () async {
      c.outras = [
        (usuario: 'aluno-1', itens: [_n('0')]),
      ];
      await c.poller.iniciar();

      c.outras = [
        (usuario: 'aluno-1', itens: [for (var i = 8; i >= 0; i--) _n('$i')]),
      ];
      await c.poller.verificar();

      expect(c.notificador.mostradas, ['4', '5', '6', '7', '8']);
    });

    test(
      'falha ao consultar as outras sessões é engolida e não atrapalha a ativa',
      () async {
        await c.poller.iniciar();

        c.erroOutras = Exception('armazenamento indisponível');
        c.lista = [_n('s2'), _n('s1')];
        await c.poller.verificar();

        expect(c.poller.ativo, isTrue);
        expect(c.notificador.mostradas, ['s2']);
      },
    );

    test('sem sessão ativa, as outras sessões não são consultadas', () async {
      c.token = null;

      await c.poller.iniciar();

      expect(c.consultasOutras, isEmpty);
    });

    test(
      'a resposta atrasada das outras sessões, de antes de uma troca de sessão, é descartada',
      () async {
        c.outras = [
          (usuario: 'aluno-1', itens: [_n('1')]),
        ];
        await c.poller.iniciar();

        final antiga = Completer<List<NotificacoesDeOutraSessao>>();
        c.outrasPendente = antiga;
        unawaited(c.poller.verificar());
        await pumpEventQueue();

        // Troca para o aluno enquanto a consulta em segundo plano não voltou:
        // o que é novo para ele chega pela sessão ativa, com o toque normal.
        c.token = _token('aluno-1');
        c.outras = [];
        final novaAtiva = Completer<List<NotificationModel>>();
        c.pendente = novaAtiva;
        unawaited(c.poller.iniciar());
        await pumpEventQueue();

        antiga.complete([
          (usuario: 'aluno-1', itens: [_n('2'), _n('1')]),
        ]);
        await pumpEventQueue();
        novaAtiva.complete([_n('2'), _n('1')]);
        await pumpEventQueue();

        expect(c.notificador.mostradas, ['2']);
        expect(c.notificador.deOutraSessao, isEmpty);
      },
    );

    test('sem multi-sessão, só o usuário ativo é consultado', () async {
      final semMultiSessao = _Cenario()
        ..multiSessao = false
        ..token = _token('separador-1', role: 'separador')
        ..lista = [_n('s1')]
        ..outras = [
          (usuario: 'aluno-1', itens: [_n('1')]),
        ];
      await semMultiSessao.poller.iniciar();

      semMultiSessao.outras = [
        (usuario: 'aluno-1', itens: [_n('2'), _n('1')]),
      ];
      await semMultiSessao.poller.verificar();

      expect(semMultiSessao.consultasOutras, isEmpty);
      expect(semMultiSessao.notificador.mostradas, isEmpty);
      expect(semMultiSessao.buscas, 2);
    });
  });
}
