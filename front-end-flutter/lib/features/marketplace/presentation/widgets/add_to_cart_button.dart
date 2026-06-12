import 'package:flutter/material.dart';

import '../../../../core/theme/app_colors.dart';

/// Botão "adicionar ao carrinho" com feedback animado (vira "Adicionado" com
/// check por 1,2s). Portado de edu-kt `AddToCartButton`.
class AddToCartButton extends StatefulWidget {
  final bool enabled;
  final VoidCallback onAddToCart;
  final String label;
  final String addedLabel;
  final double minHeight;
  final Color idleContainerColor;
  final Color idleContentColor;

  const AddToCartButton({
    super.key,
    required this.enabled,
    required this.onAddToCart,
    this.label = '+ Carrinho',
    this.addedLabel = 'Adicionado',
    this.minHeight = 0,
    this.idleContainerColor = AppColors.inputFill,
    this.idleContentColor = AppColors.textPrimary,
  });

  @override
  State<AddToCartButton> createState() => _AddToCartButtonState();
}

class _AddToCartButtonState extends State<AddToCartButton> {
  bool _added = false;

  void _handleTap() {
    if (!widget.enabled || _added) return;
    setState(() => _added = true);
    widget.onAddToCart();
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (mounted) setState(() => _added = false);
    });
  }

  @override
  Widget build(BuildContext context) {
    final container = _added ? AppColors.greenSoft : widget.idleContainerColor;
    final content = _added ? AppColors.greenDark : widget.idleContentColor;

    return AnimatedScale(
      scale: _added ? 1.06 : 1.0,
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOutBack,
      child: SizedBox(
        width: double.infinity,
        child: ElevatedButton(
          onPressed: widget.enabled ? _handleTap : null,
          style: ElevatedButton.styleFrom(
            backgroundColor: container,
            foregroundColor: content,
            disabledBackgroundColor: container,
            disabledForegroundColor: content,
            elevation: 0,
            minimumSize: Size(0, widget.minHeight),
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          child: AnimatedSwitcher(
            duration: const Duration(milliseconds: 180),
            transitionBuilder: (child, animation) => ScaleTransition(
              scale: Tween<double>(begin: 0.6, end: 1).animate(animation),
              child: FadeTransition(opacity: animation, child: child),
            ),
            child: _added
                ? Row(
                    key: const ValueKey('added'),
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.check, size: 18),
                      const SizedBox(width: 8),
                      Text(
                        widget.addedLabel,
                        style: const TextStyle(fontWeight: FontWeight.w700),
                      ),
                    ],
                  )
                : Text(
                    widget.label,
                    key: const ValueKey('idle'),
                    style: const TextStyle(fontWeight: FontWeight.w700),
                  ),
          ),
        ),
      ),
    );
  }
}
