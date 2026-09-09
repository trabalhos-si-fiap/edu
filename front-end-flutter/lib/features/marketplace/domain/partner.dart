/// Parceiro do marketplace. Espelha `ParceiroOut` do backend: `id` é inteiro
/// (a tabela `fornecedores` nunca migrou para UUID) e as coordenadas chegam
/// como string decimal, quando chegam.
///
/// O app NÃO sabe quais parceiros existem. Ele pergunta
/// `GET /partners?active=true` e desenha o que voltar — desativar um parceiro
/// no painel esvazia a seção sem tocar em nada aqui.
class Partner {
  final int id;
  final String name;
  final bool active;
  final String originLabel;

  const Partner({
    required this.id,
    required this.name,
    required this.active,
    this.originLabel = '',
  });

  factory Partner.fromJson(Map<String, dynamic> json) {
    return Partner(
      id: (json['id'] as num?)?.toInt() ?? 0,
      name: (json['nome'] as String?) ?? '',
      active: (json['ativo'] as bool?) ?? false,
      originLabel: (json['origem_rotulo'] as String?) ?? '',
    );
  }
}
