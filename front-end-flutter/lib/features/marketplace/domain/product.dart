/// Produto do marketplace. Portado de edu-kt `Product`.
///
/// No edu-kt o preço vinha como `String` da API; aqui (dados mockados) usamos
/// `double` para permitir cálculo de subtotais/totais no carrinho.
class Product {
  final int id;
  final String name;
  final String type;
  final String subtype;
  final String description;
  final double price;
  final String imageUrl;
  final double ratingAvg;
  final int ratingCount;

  const Product({
    required this.id,
    required this.name,
    required this.type,
    required this.subtype,
    required this.description,
    required this.price,
    this.imageUrl = '',
    this.ratingAvg = 0.0,
    this.ratingCount = 0,
  });

  /// Rótulo de categoria exibido nos cards (subtype, com fallback no type).
  String get categoryLabel =>
      subtype.trim().isNotEmpty ? subtype.toUpperCase() : type.toUpperCase();
}

/// Avaliação de um produto. Portado de edu-kt `Review`.
class Review {
  final int id;
  final String author;
  final int rating;
  final String comment;
  final String createdAt;

  const Review({
    required this.id,
    required this.author,
    required this.rating,
    required this.comment,
    required this.createdAt,
  });
}
