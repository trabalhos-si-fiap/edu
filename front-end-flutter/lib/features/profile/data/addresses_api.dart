import 'dart:convert';

import 'package:http/http.dart' as http;

import '../../../core/network/api_config.dart';
import '../../../core/network/token_store.dart';
import '../domain/address.dart';

/// Lançada quando uma operação de endereço falha; carrega mensagem amigável.
class AddressException implements Exception {
  AddressException(this.message);

  final String message;

  @override
  String toString() => message;
}

/// Cliente HTTP para o CRUD de endereços do backend
/// (`/auth/addresses`, em `back-end/app/modules/addresses/routes.py`).
///
/// Toda chamada exige um access token salvo (usuário autenticado); sem ele as
/// operações lançam [AddressException].
class AddressesApi {
  AddressesApi({http.Client? client, TokenStore? tokenStore})
    : _client = client ?? http.Client(),
      _tokenStore = tokenStore ?? TokenStore();

  final http.Client _client;
  final TokenStore _tokenStore;

  static final Uri _collection = Uri.parse('${ApiConfig.baseUrl}/auth/addresses');

  Future<Map<String, String>> _headers({bool json = false}) async {
    final access = await _tokenStore.readAccessToken();
    if (access == null) {
      throw AddressException('Sessão expirada. Entre novamente.');
    }
    return {
      if (json) 'Content-Type': 'application/json',
      'Authorization': 'Bearer $access',
    };
  }

  /// `GET /auth/addresses` — endereços do usuário (favorito primeiro).
  Future<List<Address>> list() async {
    final http.Response res;
    try {
      res = await _client.get(_collection, headers: await _headers());
    } on AddressException {
      rethrow;
    } on Exception {
      throw AddressException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 200) {
      throw AddressException('Falha ao carregar endereços (${res.statusCode})');
    }
    final body = jsonDecode(res.body) as List<dynamic>;
    return body
        .map((e) => Address.fromJson(e as Map<String, dynamic>))
        .toList(growable: false);
  }

  /// `POST /auth/addresses` — cria um endereço e retorna o registro salvo.
  Future<Address> create(AddressInput input) async {
    final http.Response res;
    try {
      res = await _client.post(
        _collection,
        headers: await _headers(json: true),
        body: jsonEncode(input.toJson()),
      );
    } on AddressException {
      rethrow;
    } on Exception {
      throw AddressException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode != 201) {
      throw AddressException(_messageFor(res, 'salvar'));
    }
    return Address.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// `PATCH /auth/addresses/{id}` — atualização parcial.
  Future<Address> update(String id, AddressInput input) async {
    final http.Response res;
    try {
      res = await _client.patch(
        Uri.parse('${ApiConfig.baseUrl}/auth/addresses/$id'),
        headers: await _headers(json: true),
        body: jsonEncode(input.toJson()),
      );
    } on AddressException {
      rethrow;
    } on Exception {
      throw AddressException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw AddressException('Endereço não encontrado');
    }
    if (res.statusCode != 200) {
      throw AddressException(_messageFor(res, 'atualizar'));
    }
    return Address.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// `PATCH /auth/addresses/{id}` apenas marcando como favorito.
  Future<Address> setFavorite(String id) async {
    final http.Response res;
    try {
      res = await _client.patch(
        Uri.parse('${ApiConfig.baseUrl}/auth/addresses/$id'),
        headers: await _headers(json: true),
        body: jsonEncode({'is_favorite': true}),
      );
    } on AddressException {
      rethrow;
    } on Exception {
      throw AddressException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw AddressException('Endereço não encontrado');
    }
    if (res.statusCode != 200) {
      throw AddressException('Falha ao definir favorito (${res.statusCode})');
    }
    return Address.fromJson(jsonDecode(res.body) as Map<String, dynamic>);
  }

  /// `DELETE /auth/addresses/{id}`.
  Future<void> delete(String id) async {
    final http.Response res;
    try {
      res = await _client.delete(
        Uri.parse('${ApiConfig.baseUrl}/auth/addresses/$id'),
        headers: await _headers(),
      );
    } on AddressException {
      rethrow;
    } on Exception {
      throw AddressException('Não foi possível conectar ao servidor');
    }
    if (res.statusCode == 404) {
      throw AddressException('Endereço não encontrado');
    }
    if (res.statusCode != 204) {
      throw AddressException('Falha ao remover endereço (${res.statusCode})');
    }
  }

  String _messageFor(http.Response res, String action) {
    if (res.statusCode == 422) {
      return 'Confira os campos e tente novamente';
    }
    return 'Falha ao $action endereço (${res.statusCode})';
  }
}

/// Payload de escrita (create/update). Os nomes em snake_case casam com os
/// campos de `AddressIn`/`AddressPatch` do backend.
class AddressInput {
  final String label;
  final String zipCode;
  final String street;
  final String number;
  final String complement;
  final String neighborhood;
  final String city;
  final String state;
  final bool isFavorite;

  const AddressInput({
    required this.label,
    required this.zipCode,
    required this.street,
    required this.number,
    required this.complement,
    required this.neighborhood,
    required this.city,
    required this.state,
    required this.isFavorite,
  });

  Map<String, dynamic> toJson() => {
    'label': label,
    'zip_code': zipCode,
    'street': street,
    'number': number,
    'complement': complement,
    'neighborhood': neighborhood,
    'city': city,
    'state': state,
    'is_favorite': isFavorite,
  };
}
