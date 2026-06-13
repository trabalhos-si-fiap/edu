import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/core/utils/currency.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/data/products_api.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/add_to_cart_button.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_image.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/rating_stars.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/review_item.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Detalhe do produto. Portado de edu-kt `ProductDetailScreen`.
/// Recebe o produto via `Navigator.pushNamed(arguments: product)`.
class ProductDetailScreen extends StatelessWidget {
  const ProductDetailScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final product = ModalRoute.of(context)?.settings.arguments as Product?;

    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          leading: IconButton(
            onPressed: () => Navigator.pop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
          actions: [
            _CartButton(onTap: () => Navigator.pushNamed(context, '/checkout')),
            const SizedBox(width: 8),
          ],
        ),
        body: product == null
            ? const _ProductError()
            : _ProductContent(product: product),
        bottomNavigationBar: product == null
            ? null
            : _AddToCartBar(product: product),
      ),
    );
  }
}

class _ProductContent extends StatefulWidget {
  final Product product;
  const _ProductContent({required this.product});
  @override
  State<_ProductContent> createState() => _ProductContentState();
}

class _ProductContentState extends State<_ProductContent> {
  final ProductsApi _api = ProductsApi();
  bool _loadingReviews = true;
  String? _reviewsError;
  List<Review> _reviews = const [];

  @override
  void initState() {
    super.initState();
    _loadReviews();
  }

  Future<void> _loadReviews() async {
    setState(() {
      _loadingReviews = true;
      _reviewsError = null;
    });
    try {
      final r = await _api.reviews(widget.product.id);
      if (!mounted) return;
      setState(() {
        _reviews = r;
        _loadingReviews = false;
      });
    } on ProductsException catch (e) {
      if (!mounted) return;
      setState(() {
        _reviewsError = e.message;
        _loadingReviews = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final product = widget.product;
    return SafeArea(
      bottom: false,
      child: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        children: [
          _HeroImage(product: product),
          const SizedBox(height: 12),
          _CategoryTag(text: product.categoryLabel),
          const SizedBox(height: 12),
          _Card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  product.name,
                  style: const TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 24,
                    fontWeight: FontWeight.w800,
                    height: 1.2,
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    RatingStars(
                      rating: product.ratingAvg,
                      count: product.ratingCount,
                      starSize: 18,
                    ),
                    Text(
                      formatBRL(product.price),
                      style: const TextStyle(
                        color: AppColors.purple,
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          _Card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Sobre o produto',
                  style: TextStyle(
                    color: AppColors.textPrimary,
                    fontSize: 16,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  product.description.trim().isEmpty
                      ? 'Sem descrição disponível.'
                      : product.description,
                  style: const TextStyle(
                    color: AppColors.textSecondary,
                    fontSize: 14,
                    height: 1.5,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Text(
            product.ratingCount > 0
                ? 'Avaliações (${product.ratingCount})'
                : 'Avaliações',
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 16,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 12),
          if (_loadingReviews)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 16),
              child: Center(child: CircularProgressIndicator()),
            )
          else if (_reviewsError != null)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8),
              child: Text(
                _reviewsError!,
                style: const TextStyle(color: AppColors.textSecondary, fontSize: 13),
              ),
            )
          else if (_reviews.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: Text(
                'Ainda não há avaliações.',
                style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
              ),
            )
          else
            for (final review in _reviews) ...[
              ReviewItem(review: review),
              const SizedBox(height: 10),
            ],
          const SizedBox(height: 24),
        ],
      ),
    );
  }
}

class _HeroImage extends StatelessWidget {
  final Product product;
  const _HeroImage({required this.product});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: SizedBox(
        height: 280,
        width: double.infinity,
        child: ProductImage(
          imageUrl: product.imageUrl,
          type: product.type,
          iconSize: 72,
        ),
      ),
    );
  }
}

class _CategoryTag extends StatelessWidget {
  final String text;

  const _CategoryTag({required this.text});

  @override
  Widget build(BuildContext context) {
    if (text.trim().isEmpty) return const SizedBox.shrink();
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: AppColors.purpleSoft,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          text,
          style: const TextStyle(
            color: AppColors.purple,
            fontSize: 11,
            fontWeight: FontWeight.w700,
            letterSpacing: 1,
          ),
        ),
      ),
    );
  }
}

class _Card extends StatelessWidget {
  final Widget child;

  const _Card({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _AddToCartBar extends StatelessWidget {
  final Product product;

  const _AddToCartBar({required this.product});

  @override
  Widget build(BuildContext context) {
    return Container(
      color: AppColors.white.withValues(alpha: 0.94),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
          child: AddToCartButton(
            enabled: true,
            onAddToCart: () => context.read<CartStore>().add(product),
            label: 'Adicionar ao carrinho',
            minHeight: 52,
            idleContainerColor: AppColors.blue,
            idleContentColor: AppColors.white,
          ),
        ),
      ),
    );
  }
}

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

class _ProductError extends StatelessWidget {
  const _ProductError();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(24),
        child: Text(
          'Não foi possível abrir o produto.',
          style: TextStyle(
            color: AppColors.textPrimary,
            fontSize: 16,
            fontWeight: FontWeight.w700,
          ),
        ),
      ),
    );
  }
}
