import 'package:edu_ia/core/network/session_store.dart';
import 'package:edu_ia/core/network/token_store.dart';
import 'package:edu_ia/core/session/session_manager.dart';
import 'package:flutter_test/flutter_test.dart';

class _FakeTokenStore extends TokenStore {
  String? access;
  String? refresh;

  @override
  Future<void> save({
    required String accessToken,
    required String refreshToken,
  }) async {
    access = accessToken;
    refresh = refreshToken;
  }

  @override
  Future<String?> readAccessToken() async => access;

  @override
  Future<String?> readRefreshToken() async => refresh;

  @override
  Future<void> clear() async {
    access = null;
    refresh = null;
  }
}

class _FakeSessionStore extends SessionStore {
  String? nome;

  @override
  Future<void> saveName(String name) async => nome = name;

  @override
  Future<String?> readName() async => nome;

  @override
  Future<void> clear() async => nome = null;
}

/// Armazenamento em memória com a mesma superfície que o manager usa.
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

void main() {
  late _FakeTokenStore tokenStore;
  late _FakeSessionStore sessionStore;
  late _MemoriaSegura memoria;
  late SessionManager manager;

  setUp(() {
    tokenStore = _FakeTokenStore();
    sessionStore = _FakeSessionStore();
    memoria = _MemoriaSegura();
    manager = SessionManager(
      storage: memoria,
      tokenStore: tokenStore,
      sessionStore: sessionStore,
    );
  });

  // Medido no celular: depois de entrar como admin e trocar para a aluna pelo
  // chip, a home dizia "Bem vindo(a) de volta, Admin!" — os tokens trocavam,
  // o nome em cache (que a home e o perfil leem) não.
  test('ativar uma sessão troca também o nome exibido', () async {
    await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
    await manager.guardarSessaoAtual(papel: 'student', nome: 'Ana Ensaio');
    await tokenStore.save(accessToken: 'a-admin', refreshToken: 'r-admin');
    await manager.guardarSessaoAtual(papel: 'admin', nome: 'Admin Demo');
    sessionStore.nome = 'Admin Demo';

    await manager.ativar('student');

    expect(sessionStore.nome, 'Ana Ensaio');
  });

  test('ativar uma sessão sem nome guardado limpa o nome antigo', () async {
    // Sessão gravada antes de o nome existir no formato guardado.
    await memoria.write(
      key: 'demo_sessions',
      value: '{"student": {"access": "a", "refresh": "r"}}',
    );
    sessionStore.nome = 'Admin Demo';

    await manager.ativar('student');

    // Sem cache, `AuthApi.currentDisplayName` busca `/auth/me` do token novo.
    expect(sessionStore.nome, isNull);
  });

  test('guarda a sessão ativa sob o papel', () async {
    await tokenStore.save(accessToken: 'a1', refreshToken: 'r1');

    await manager.guardarSessaoAtual(
      papel: 'separador',
      nome: 'Separador Demo',
    );

    final sessoes = await manager.listar();
    expect(sessoes.map((s) => s.papel), ['separador']);
    expect(sessoes.single.nome, 'Separador Demo');
  });

  test('trocar de sessão preserva as demais', () async {
    await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
    await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');
    await tokenStore.save(accessToken: 'a-sep', refreshToken: 'r-sep');
    await manager.guardarSessaoAtual(
      papel: 'separador',
      nome: 'Separador Demo',
    );

    final trocou = await manager.ativar('student');

    expect(trocou, isTrue);
    expect(tokenStore.access, 'a-aluno');
    // A sessão de onde saímos continua guardada — é o ponto do recurso.
    expect(
      (await manager.listar()).map((s) => s.papel),
      containsAll(['student', 'separador']),
    );
  });

  test(
    'ativar um papel sem sessão guardada não derruba a sessão atual',
    () async {
      await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
      await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');

      final trocou = await manager.ativar('admin');

      expect(trocou, isFalse);
      expect(tokenStore.access, 'a-aluno');
    },
  );

  test('remover apaga só a sessão pedida', () async {
    await tokenStore.save(accessToken: 'a1', refreshToken: 'r1');
    await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');
    await manager.guardarSessaoAtual(papel: 'admin', nome: 'Admin Demo');

    await manager.remover('admin');

    expect((await manager.listar()).map((s) => s.papel), ['student']);
  });

  test('um valor corrompido no armazenamento não derruba o app', () async {
    final memoria = _MemoriaSegura();
    await memoria.write(key: 'demo_sessions', value: 'isto não é json');
    manager = SessionManager(storage: memoria, tokenStore: tokenStore);

    expect(await manager.listar(), isEmpty);
  });

  group('tokens de uma sessão guardada', () {
    // O poller de notificações da demonstração consulta as sessões que NÃO
    // estão ativas com o par guardado de cada uma, e grava de volta o par
    // renovado quando o access token expira.
    test('lerTokens devolve o par guardado sob o papel', () async {
      await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
      await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');

      final par = await manager.lerTokens('student');

      expect(par?.accessToken, 'a-aluno');
      expect(par?.refreshToken, 'r-aluno');
      expect(await manager.lerTokens('admin'), isNull);
    });

    test(
      'atualizarTokens troca só o par daquela sessão e não mexe na ativa',
      () async {
        await tokenStore.save(accessToken: 'a-aluno', refreshToken: 'r-aluno');
        await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');
        await tokenStore.save(accessToken: 'a-sep', refreshToken: 'r-sep');
        await manager.guardarSessaoAtual(
          papel: 'separador',
          nome: 'Separador Demo',
        );

        final gravou = await manager.atualizarTokens('student', (
          accessToken: 'a-aluno-novo',
          refreshToken: 'r-aluno-novo',
        ));

        expect(gravou, isTrue);
        final aluno = await manager.lerTokens('student');
        expect(aluno?.accessToken, 'a-aluno-novo');
        expect(aluno?.refreshToken, 'r-aluno-novo');
        expect((await manager.lerTokens('separador'))?.accessToken, 'a-sep');
        // A sessão ativa (a do separador) continua no TokenStore.
        expect(tokenStore.access, 'a-sep');
        expect(tokenStore.refresh, 'r-sep');
        final nomes = {for (final s in await manager.listar()) s.papel: s.nome};
        expect(nomes['student'], 'Aluno Demo');

        // E ativar a sessão depois usa o par renovado.
        await manager.ativar('student');
        expect(tokenStore.access, 'a-aluno-novo');
      },
    );

    test(
      'atualizarTokens não recria uma sessão que foi removida no meio-tempo',
      () async {
        await tokenStore.save(accessToken: 'a1', refreshToken: 'r1');
        await manager.guardarSessaoAtual(papel: 'student', nome: 'Aluno Demo');
        await manager.remover('student');

        final gravou = await manager.atualizarTokens('student', (
          accessToken: 'a2',
          refreshToken: 'r2',
        ));

        expect(gravou, isFalse);
        expect(await manager.listar(), isEmpty);
      },
    );
  });
}
