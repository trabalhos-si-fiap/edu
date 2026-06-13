import 'package:cached_network_image/cached_network_image.dart';
import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_visuals.dart';
import 'package:flutter/material.dart';

/// Renders a product image from a (presigned) network URL, falling back to the
/// type icon placeholder when the URL is empty or fails to load.
class ProductImage extends StatelessWidget {
  final String imageUrl;
  final String type;
  final double iconSize;

  const ProductImage({
    super.key,
    required this.imageUrl,
    required this.type,
    this.iconSize = 48,
  });

  Widget _placeholder() => Container(
        color: AppColors.imagePlaceholder,
        alignment: Alignment.center,
        child: Icon(
          iconForProduct(type),
          size: iconSize,
          color: AppColors.textSecondary.withValues(alpha: 0.6),
        ),
      );

  @override
  Widget build(BuildContext context) {
    if (imageUrl.isEmpty) return _placeholder();
    return CachedNetworkImage(
      imageUrl: imageUrl,
      fit: BoxFit.cover,
      placeholder: (context, url) => Container(
        color: AppColors.imagePlaceholder,
        alignment: Alignment.center,
        child: const SizedBox(
          width: 24,
          height: 24,
          child: CircularProgressIndicator(strokeWidth: 2),
        ),
      ),
      errorWidget: (context, url, error) => _placeholder(),
    );
  }
}
