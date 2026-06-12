import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/core/utils/currency.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:edu_ia/features/marketplace/data/mock_marketplace.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/add_to_cart_button.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_visuals.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/rating_stars.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/review_item.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

class MarketplaceScreen extends StatefulWidget {
  const MarketplaceScreen({super.key});

  @override
  State<MarketplaceScreen> createState() => _MarketplaceScreenState();
}

class _MarketplaceScreenState extends State<MarketplaceScreen> {
  final TextEditingController _searchController = TextEditingController();
  String _query = '';
  String? _selectedType;

  late final List<String> _types = mockProducts
      .map((p) => p.type)
      .where((t) => t.isNotEmpty)
      .toSet()
      .toList();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  List<Product> get _filtered {
    final q = _query.trim().toLowerCase();
    return mockProducts.where((p) {
      final matchesType = _selectedType == null || p.type == _selectedType;
      final matchesQuery =
          q.isEmpty ||
          p.name.toLowerCase().contains(q) ||
          p.description.toLowerCase().contains(q);
      return matchesType && matchesQuery;
    }).toList();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        body: SafeArea(
          child: Column(
            children: [
              _TopBar(
                controller: _searchController,
                onSearchChange: (v) => setState(() => _query = v),
                onOpenProfile: () => Navigator.pushNamed(context, '/profile'),
                onOpenCart: () => Navigator.pushNamed(context, '/checkout'),
              ),
              _CategoryChips(
                types: _types,
                selected: _selectedType,
                onSelected: (t) => setState(() => _selectedType = t),
              ),
              Expanded(
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    const padding = 24.0;
                    const spacing = 12.0;
                    final cellWidth =
                        (constraints.maxWidth - padding * 2 - spacing) / 2;
                    // Altura = imagem quadrada + bloco de conteúdo (textos
                    // limitados + botão), com folga.
                    final extent = cellWidth + 252;
                    return CustomScrollView(
                      slivers: [
                        const SliverToBoxAdapter(
                          child: Padding(
                            padding: EdgeInsets.fromLTRB(
                              padding,
                              padding,
                              padding,
                              16,
                            ),
                            child: Text(
                              'EduMarketplace',
                              style: TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.w800,
                                color: AppColors.textPrimary,
                                letterSpacing: -0.5,
                              ),
                            ),
                          ),
                        ),
                        if (filtered.isEmpty)
                          SliverToBoxAdapter(child: _EmptyResult(query: _query))
                        else
                          SliverPadding(
                            padding: const EdgeInsets.fromLTRB(
                              padding,
                              0,
                              padding,
                              24,
                            ),
                            sliver: SliverGrid(
                              gridDelegate:
                                  SliverGridDelegateWithFixedCrossAxisCount(
                                    crossAxisCount: 2,
                                    crossAxisSpacing: spacing,
                                    mainAxisSpacing: 16,
                                    mainAxisExtent: extent,
                                  ),
                              delegate: SliverChildBuilderDelegate(
                                (context, i) =>
                                    _ProductCard(product: filtered[i]),
                                childCount: filtered.length,
                              ),
                            ),
                          ),
                      ],
                    );
                  },
                ),
              ),
            ],
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 4),
      ),
    );
  }
}

class _TopBar extends StatelessWidget {
  final TextEditingController controller;
  final ValueChanged<String> onSearchChange;
  final VoidCallback onOpenProfile;
  final VoidCallback onOpenCart;

  const _TopBar({
    required this.controller,
    required this.onSearchChange,
    required this.onOpenProfile,
    required this.onOpenCart,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      child: Row(
        children: [
          IconButton(
            onPressed: onOpenProfile,
            icon: const Icon(
              Icons.person_outline,
              size: 26,
              color: AppColors.textPrimary,
            ),
          ),
          Expanded(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 4),
              decoration: BoxDecoration(
                color: AppColors.white,
                borderRadius: BorderRadius.circular(32),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 8,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: TextField(
                controller: controller,
                onChanged: onSearchChange,
                style: const TextStyle(
                  fontSize: 15,
                  color: AppColors.textPrimary,
                ),
                decoration: const InputDecoration(
                  hintText: 'Buscar cursos, guias ou materiais...',
                  hintStyle: TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 14,
                  ),
                  prefixIcon: Icon(
                    Icons.search,
                    color: AppColors.textSecondary,
                  ),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(vertical: 16),
                ),
              ),
            ),
          ),
          _CartButton(onTap: onOpenCart),
        ],
      ),
    );
  }
}

/// Ícone do carrinho com badge de quantidade. Observa o [CartStore].
class _CartButton extends StatelessWidget {
  final VoidCallback onTap;

  const _CartButton({required this.onTap});

  @override
  Widget build(BuildContext context) {
    final count = context.watch<CartStore>().totalQuantity;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        IconButton(
          onPressed: onTap,
          icon: const Icon(
            Icons.shopping_cart_outlined,
            size: 26,
            color: AppColors.textPrimary,
          ),
        ),
        if (count > 0)
          Positioned(
            right: 4,
            top: 4,
            child: Container(
              width: 18,
              height: 18,
              alignment: Alignment.center,
              decoration: const BoxDecoration(
                color: AppColors.purple,
                shape: BoxShape.circle,
              ),
              child: Text(
                count > 99 ? '99+' : '$count',
                style: const TextStyle(
                  color: AppColors.white,
                  fontSize: 10,
                  fontWeight: FontWeight.w700,
                ),
              ),
            ),
          ),
      ],
    );
  }
}

class _CategoryChips extends StatelessWidget {
  final List<String> types;
  final String? selected;
  final ValueChanged<String?> onSelected;

  const _CategoryChips({
    required this.types,
    required this.selected,
    required this.onSelected,
  });

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 52,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        children: [
          _Chip(
            label: 'Tudo',
            selected: selected == null,
            onTap: () => onSelected(null),
          ),
          for (final type in types) ...[
            const SizedBox(width: 8),
            _Chip(
              label: type.toUpperCase(),
              selected: selected == type,
              onTap: () => onSelected(type),
            ),
          ],
        ],
      ),
    );
  }
}

class _Chip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _Chip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(horizontal: 16),
        decoration: BoxDecoration(
          color: selected ? AppColors.purple : AppColors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: selected
              ? null
              : [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.04),
                    blurRadius: 4,
                    offset: const Offset(0, 1),
                  ),
                ],
        ),
        child: Text(
          label,
          style: TextStyle(
            color: selected ? AppColors.white : AppColors.textPrimary,
            fontWeight: FontWeight.w700,
            fontSize: 12,
            letterSpacing: 0.5,
          ),
        ),
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  final Product product;

  const _ProductCard({required this.product});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () =>
          Navigator.pushNamed(context, '/product', arguments: product.id),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppColors.white,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.06),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(10),
              child: AspectRatio(
                aspectRatio: 1,
                child: Container(
                  color: AppColors.imagePlaceholder,
                  child: Center(
                    child: Icon(
                      iconForProduct(product.type),
                      size: 48,
                      color: AppColors.textSecondary.withValues(alpha: 0.6),
                    ),
                  ),
                ),
              ),
            ),
            const SizedBox(height: 10),
            Text(
              product.categoryLabel,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.purple,
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 1,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              product.name,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.textPrimary,
                fontSize: 15,
                fontWeight: FontWeight.w800,
                height: 1.2,
              ),
            ),
            const SizedBox(height: 6),
            Text(
              product.description,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
                height: 1.3,
              ),
            ),
            const SizedBox(height: 8),
            GestureDetector(
              onTap: product.ratingCount > 0
                  ? () => showReviewsBottomSheet(context, product)
                  : null,
              child: FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: RatingStars(
                  rating: product.ratingAvg,
                  count: product.ratingCount,
                  starSize: 13,
                ),
              ),
            ),
            const Spacer(),
            const SizedBox(height: 8),
            FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(
                formatBRL(product.price),
                maxLines: 1,
                style: const TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 18,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            const SizedBox(height: 10),
            AddToCartButton(
              enabled: true,
              onAddToCart: () => context.read<CartStore>().add(product),
            ),
          ],
        ),
      ),
    );
  }
}

class _EmptyResult extends StatelessWidget {
  final String query;

  const _EmptyResult({required this.query});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 48, horizontal: 24),
      child: Column(
        children: [
          const Icon(
            Icons.search_off,
            size: 56,
            color: AppColors.textSecondary,
          ),
          const SizedBox(height: 16),
          const Text(
            'Nenhum produto encontrado',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.w700,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            query.trim().isEmpty
                ? 'Tente buscar por outro termo.'
                : 'Não encontramos resultados para "$query". Tente outras palavras-chave.',
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textSecondary),
          ),
        ],
      ),
    );
  }
}
