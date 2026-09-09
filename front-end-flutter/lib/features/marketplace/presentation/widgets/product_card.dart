import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/core/utils/currency.dart';
import 'package:edu_ia/features/cart/data/cart_store.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_image.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/rating_stars.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/review_item.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/add_to_cart_button.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Card de produto: imagem, categoria, nome, descrição, avaliação, preço e
/// botão de adicionar ao carrinho. Extraído de `marketplace_screen.dart` para
/// ser reaproveitado também pela seção de parceiros (mesmo card, catálogo
/// próprio ou de parceiro).
class ProductCard extends StatelessWidget {
  final Product product;

  const ProductCard({super.key, required this.product});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () =>
          Navigator.pushNamed(context, '/product', arguments: product),
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
                child: ProductImage(
                  imageUrl: product.imageUrl,
                  type: product.type,
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
