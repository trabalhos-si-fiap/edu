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
  late SessionManager manager;

  setUp(() {
    tokenStore = _FakeTokenStore();
    manager = SessionManager(storage: _MemoriaSegura(), tokenStore: tokenStore);
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
}
