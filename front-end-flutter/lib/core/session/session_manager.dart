import 'dart:convert';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import '../network/token_store.dart';

/// Uma sessão guardada para um papel: o suficiente para reativá-la sem
/// redigitar senha. Os tokens em si não fazem parte deste tipo — eles só
/// existem dentro do JSON persistido e no [TokenStore] enquanto ativos, nunca
/// em um objeto que algum código de tela possa acabar logando.
class SessaoGuardada {
  const SessaoGuardada({required this.papel, required this.nome});

  final String papel; // student | separador | entregador | admin | carregamento
  final String nome;
}

/// Superfície mínima de armazenamento seguro que o [SessionManager] precisa —
/// só o que os testes exercitam, não a API inteira do plugin. É o que torna
/// o manager testável sem o plugin de plataforma.
abstract class SecureStorageLike {
  Future<String?> read({required String key});
  Future<void> write({required String key, required String? value});
  Future<void> delete({required String key});
}

/// [FlutterSecureStorage] satisfaz [SecureStorageLike] por composição: este
/// adaptador delega para a instância real sem expor mais nada da API do
/// plugin.
class _FlutterSecureStorageAdapter implements SecureStorageLike {
  const _FlutterSecureStorageAdapter(this._storage);

  final FlutterSecureStorage _storage;

  @override
  Future<String?> read({required String key}) => _storage.read(key: key);

  @override
  Future<void> write({required String key, required String? value}) =>
      _storage.write(key: key, value: value);

  @override
  Future<void> delete({required String key}) => _storage.delete(key: key);
}

/// Guarda várias sessões (uma por papel) e troca a ativa sem redigitar senha.
///
/// RECURSO DE DEMONSTRAÇÃO. A apresentação é conduzida por uma pessoa
/// alternando entre os quatro perfis, e redigitar senha a cada troca é o que
/// esta classe evita. Guardar quatro sessões ativas num aparelho não é postura
/// de segurança para um app de estudante — por isso [habilitado] é uma
/// constante de compilação, falsa em qualquer build normal, e todo o caminho
/// que a usa some no tree-shaking. Mesmo padrão de `demoItensMock`
/// (`features/logistics/data/demo_itens.dart`).
class SessionManager {
  SessionManager({SecureStorageLike? storage, TokenStore? tokenStore})
    : _storage =
          storage ?? const _FlutterSecureStorageAdapter(FlutterSecureStorage()),
      _tokenStore = tokenStore ?? TokenStore();

  final SecureStorageLike _storage;
  final TokenStore _tokenStore;

  static const _key = 'demo_sessions';

  /// `--dart-define=DEMO_MULTI_SESSAO=true`. Mesmo padrão de
  /// `demoItensMock` (`features/logistics/data/demo_itens.dart`): constante de
  /// compilação, então o código morto some no tree-shaking do build normal.
  static const bool habilitado = bool.fromEnvironment('DEMO_MULTI_SESSAO');

  /// Copia o par de tokens ativo (lido do [TokenStore]) para debaixo de
  /// [papel] no armazenamento persistido, junto com [nome]. Sobrescreve
  /// qualquer sessão anterior guardada sob o mesmo papel.
  Future<void> guardarSessaoAtual({
    required String papel,
    required String nome,
  }) async {
    final access = await _tokenStore.readAccessToken();
    final refresh = await _tokenStore.readRefreshToken();
    if (access == null || refresh == null) return;

    final sessoes = await _lerBruto();
    sessoes[papel] = {'access': access, 'refresh': refresh, 'nome': nome};
    await _escreverBruto(sessoes);
  }

  /// Lista as sessões guardadas. Um valor corrompido no armazenamento (JSON
  /// inválido ou de formato inesperado) não deve derrubar o app — devolve
  /// lista vazia nesse caso.
  Future<List<SessaoGuardada>> listar() async {
    final sessoes = await _lerBruto();
    return sessoes.entries
        .map(
          (e) => SessaoGuardada(
            papel: e.key,
            nome: (e.value['nome'] as String?) ?? e.key,
          ),
        )
        .toList();
  }

  /// Ativa a sessão guardada sob [papel]: copia seu par de tokens para o
  /// [TokenStore], de onde o resto do app (via `appAuthClient`) já lê.
  /// Devolve `false` sem tocar na sessão atual quando não há sessão guardada
  /// para [papel].
  Future<bool> ativar(String papel) async {
    final sessoes = await _lerBruto();
    final sessao = sessoes[papel];
    if (sessao == null) return false;

    final access = sessao['access'];
    final refresh = sessao['refresh'];
    if (access is! String || refresh is! String) return false;

    await _tokenStore.save(accessToken: access, refreshToken: refresh);
    return true;
  }

  /// Remove só a sessão guardada sob [papel]; as demais permanecem.
  Future<void> remover(String papel) async {
    final sessoes = await _lerBruto();
    sessoes.remove(papel);
    await _escreverBruto(sessoes);
  }

  /// Apaga todas as sessões guardadas.
  Future<void> limpar() async {
    await _storage.delete(key: _key);
  }

  Future<Map<String, Map<String, dynamic>>> _lerBruto() async {
    final raw = await _storage.read(key: _key);
    if (raw == null) return {};
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return {};
      return decoded.map(
        (papel, valor) =>
            MapEntry(papel, Map<String, dynamic>.from(valor as Map)),
      );
    } catch (_) {
      return {};
    }
  }

  Future<void> _escreverBruto(Map<String, Map<String, dynamic>> sessoes) async {
    await _storage.write(key: _key, value: jsonEncode(sessoes));
  }
}
