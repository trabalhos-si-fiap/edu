import '../domain/product.dart';

/// Catálogo mockado do marketplace. Substitui as chamadas de API (Retrofit) do
/// edu-kt por dados locais, mantendo o mesmo formato de domínio.
const List<Product> mockProducts = [
  Product(
    id: 1,
    name: 'Guia de Redação Nota 1000',
    type: 'apostila',
    subtype: 'Apostila Digital',
    description:
        'Estruturas prontas e repertório sociocultural para o ENEM, com modelos comentados e checklist de revisão.',
    price: 49.90,
    ratingAvg: 4.5,
    ratingCount: 128,
  ),
  Product(
    id: 2,
    name: 'Mastering Data Synthesis',
    type: 'curso',
    subtype: 'Premium Course',
    description:
        'Módulo avançado de Educação 5.0 com trilhas práticas de análise e síntese de dados.',
    price: 189.90,
    ratingAvg: 4.8,
    ratingCount: 64,
  ),
  Product(
    id: 3,
    name: 'Diagnostic AI Toolkit',
    type: 'digital',
    subtype: 'Digital Tool',
    description:
        'Ferramenta de diagnóstico com IA para mapear pontos fracos e gerar planos de estudo personalizados.',
    price: 45.00,
    ratingAvg: 4.2,
    ratingCount: 30,
  ),
  Product(
    id: 4,
    name: 'Simulado ENEM Completo',
    type: 'apostila',
    subtype: 'Apostila',
    description:
        'Quatro provas no formato oficial, gabarito comentado e correção da redação por TRI.',
    price: 29.90,
    ratingAvg: 4.6,
    ratingCount: 210,
  ),
  Product(
    id: 5,
    name: 'Mapa Mental de Biologia',
    type: 'digital',
    subtype: 'Material Digital',
    description:
        'Coletânea de mapas mentais de citologia, genética e ecologia para revisão rápida.',
    price: 19.90,
    ratingAvg: 4.0,
    ratingCount: 15,
  ),
  Product(
    id: 6,
    name: 'Curso de Matemática Essencial',
    type: 'curso',
    subtype: 'Curso',
    description:
        'Do básico ao avançado: funções, geometria e estatística com exercícios resolvidos passo a passo.',
    price: 149.90,
    ratingAvg: 4.9,
    ratingCount: 302,
  ),
];

/// Avaliações mockadas por id de produto.
const Map<int, List<Review>> mockReviews = {
  1: [
    Review(
      id: 1,
      author: 'Ana Beatriz',
      rating: 5,
      comment: 'Salvou minha redação! Os repertórios são excelentes.',
      createdAt: '2025-03-12',
    ),
    Review(
      id: 2,
      author: 'Carlos Henrique',
      rating: 4,
      comment: 'Material muito completo, faltou só mais exemplos de conclusão.',
      createdAt: '2025-02-28',
    ),
  ],
  2: [
    Review(
      id: 3,
      author: 'Marina Lopes',
      rating: 5,
      comment: 'Conteúdo denso e muito bem explicado. Vale cada centavo.',
      createdAt: '2025-04-02',
    ),
  ],
  3: [
    Review(
      id: 4,
      author: 'Pedro Alves',
      rating: 4,
      comment: 'A análise de pontos fracos é certeira.',
      createdAt: '2025-01-19',
    ),
  ],
  4: [
    Review(
      id: 5,
      author: 'Júlia Santos',
      rating: 5,
      comment: 'Os simulados são idênticos à prova real. Recomendo!',
      createdAt: '2025-03-30',
    ),
    Review(
      id: 6,
      author: 'Rafael Costa',
      rating: 4,
      comment: 'Correção da redação foi rápida e detalhada.',
      createdAt: '2025-03-21',
    ),
  ],
  6: [
    Review(
      id: 7,
      author: 'Beatriz Nunes',
      rating: 5,
      comment: 'Finalmente entendi funções. Professor explica muito bem.',
      createdAt: '2025-04-10',
    ),
  ],
};

List<Review> reviewsForProduct(int productId) => mockReviews[productId] ?? const [];

Product? productById(int id) {
  for (final p in mockProducts) {
    if (p.id == id) return p;
  }
  return null;
}
