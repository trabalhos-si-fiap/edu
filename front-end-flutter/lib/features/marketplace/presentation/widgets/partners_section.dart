import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/marketplace/domain/partner.dart';
import 'package:edu_ia/features/marketplace/domain/product.dart';
import 'package:edu_ia/features/marketplace/presentation/partners_provider.dart';
import 'package:edu_ia/features/marketplace/presentation/widgets/product_card.dart';
import 'package:flutter/material.dart';

/// Seção "Parceiros" do marketplace: um bloco por parceiro ativo, com o
/// nome, a origem e uma faixa horizontal do catálogo dele.
///
/// Stateless e sem provider — recebe tudo por parâmetro, o que torna o
/// widget testável sem montar um `ChangeNotifierProvider` (mesmo padrão de
/// separar `MarketplaceView` do `MarketplaceScreen`). Quem chama é dono da
/// leitura do [PartnersProvider].
///
/// A seção NÃO decide o que mostrar a partir de quem é o parceiro — ela só
/// desenha o que a lista de [partners] trouxer.
class PartnersSection extends StatelessWidget {
  final PartnersViewState state;
  final List<Partner> partners;
  final Map<int, List<Product>> productsByPartner;
  final String? errorMessage;
  final VoidCallback? onRetry;

  const PartnersSection({
    super.key,
    required this.state,
    required this.partners,
    required this.productsByPartner,
    this.errorMessage,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    switch (state) {
      case PartnersViewState.loading:
        return const Padding(
          padding: EdgeInsets.symmetric(vertical: 32),
          child: Center(
            child: SizedBox(
              width: 28,
              height: 28,
              child: CircularProgressIndicator(
                strokeWidth: 3,
                color: AppColors.purple,
              ),
            ),
          ),
        );
      case PartnersViewState.error:
        return Padding(
          padding: const EdgeInsets.fromLTRB(24, 16, 24, 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                errorMessage ?? '',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: onRetry,
                child: const Text(
                  'Tentar novamente',
                  style: TextStyle(color: AppColors.purple),
                ),
              ),
            ],
          ),
        );
      case PartnersViewState.success:
        if (partners.isEmpty) return const SizedBox.shrink();
        return Padding(
          padding: const EdgeInsets.fromLTRB(24, 8, 0, 16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Padding(
                padding: EdgeInsets.only(right: 24),
                child: Text(
                  'Parceiros',
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                  ),
                ),
              ),
              for (final partner in partners)
                Padding(
                  padding: const EdgeInsets.only(top: 16, right: 24),
                  child: _PartnerBlock(
                    partner: partner,
                    products: productsByPartner[partner.id] ?? const [],
                  ),
                ),
            ],
          ),
        );
    }
  }
}

/// Um parceiro e a faixa horizontal do catálogo dele. Um parceiro sem
/// produtos (estoque zerado, ou desativado entre o load e o render) mostra
/// só o cabeçalho — sem faixa vazia, sem erro.
class _PartnerBlock extends StatelessWidget {
  static const double _cardWidth = 190;

  final Partner partner;
  final List<Product> products;

  const _PartnerBlock({required this.partner, required this.products});

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          partner.name,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: AppColors.textPrimary,
          ),
        ),
        if (partner.originLabel.isNotEmpty) ...[
          const SizedBox(height: 2),
          Text(
            partner.originLabel,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
        ],
        if (products.isNotEmpty) ...[
          const SizedBox(height: 12),
          // Altura segue a mesma proporção do grid do catálogo próprio
          // (`_buildBody` em marketplace_screen.dart: `cellWidth + 252`) —
          // o card é o mesmo [ProductCard], só que numa faixa horizontal
          // com largura fixa em vez de uma célula de grid.
          SizedBox(
            height: _cardWidth + 260,
            child: ListView.separated(
              scrollDirection: Axis.horizontal,
              itemCount: products.length,
              separatorBuilder: (_, _) => const SizedBox(width: 12),
              itemBuilder: (context, i) => SizedBox(
                width: _cardWidth,
                child: ProductCard(product: products[i]),
              ),
            ),
          ),
        ],
      ],
    );
  }
}
