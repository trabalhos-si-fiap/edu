import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';

class MarketplaceScreen extends StatefulWidget {
  const MarketplaceScreen({super.key});

  @override
  State<MarketplaceScreen> createState() => _MarketplaceScreenState();
}

class _MarketplaceScreenState extends State<MarketplaceScreen> {
  int _currentTabIndex = 4;
  final TextEditingController _searchController = TextEditingController();

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          automaticallyImplyLeading: false,
          title: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                IconButton(
                  onPressed: () => Navigator.pushNamed(context, '/profile'),
                  icon: const Icon(Icons.person_outline, size: 28),
                ),
                Row(
                  children: [
                    IconButton(
                      onPressed: () =>
                          Navigator.pushNamed(context, '/checkout'),
                      icon: const Icon(Icons.shopping_cart_outlined, size: 28),
                    ),
                    IconButton(
                      onPressed: () =>
                          Navigator.pushNamed(context, '/notifications'),
                      icon: const Icon(Icons.notifications_none, size: 28),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(24, 24, 24, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'EduMarketplace',
                  style: TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                    letterSpacing: -0.5,
                  ),
                ),
                const SizedBox(height: 24),
                _SearchField(controller: _searchController),
                const SizedBox(height: 28),
                const _FeaturedCollectionCard(),
                const SizedBox(height: 20),
                const _ProductCard(
                  category: 'APOSTILA DIGITAL',
                  title: 'Guia de Redação Nota 1000',
                  description:
                      'Estruturas prontas e repertório sociocultural para o ENEM.',
                  price: 'R\$ 49,90',
                  imageIcon: Icons.menu_book_outlined,
                ),
                const SizedBox(height: 20),
                const _ProductCard(
                  title: '2024 Exam Prep Guide',
                  description: 'Physical Book • Hardcover',
                  price: 'R\$ 49,90',
                  imageIcon: Icons.auto_stories_outlined,
                ),
              ],
            ),
          ),
        ),
        bottomNavigationBar: NavBar(
          currentIndex: _currentTabIndex,
          onTap: (index) {
            setState(() => _currentTabIndex = index);

            switch (index) {
              case 0:
                Navigator.pushReplacementNamed(context, '/home');
                break;
              case 1:
                Navigator.pushReplacementNamed(context, '/quiz');
                break;
              case 2:
                Navigator.pushReplacementNamed(context, '/study');
                break;
              case 3:
                Navigator.pushReplacementNamed(context, '/review');
                break;
              case 4:
                Navigator.pushReplacementNamed(context, '/marketplace');
                break;
            }
          },
        ),
      ),
    );
  }
}

class _SearchField extends StatelessWidget {
  final TextEditingController controller;

  const _SearchField({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Container(
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
        style: const TextStyle(fontSize: 15, color: AppColors.textPrimary),
        decoration: InputDecoration(
          hintText: 'Search courses, guides, or materials...',
          hintStyle: const TextStyle(
            color: AppColors.textSecondary,
            fontSize: 15,
          ),
          prefixIcon: const Padding(
            padding: EdgeInsets.only(left: 16, right: 8),
            child: Icon(Icons.search, color: AppColors.textSecondary),
          ),
          prefixIconConstraints: const BoxConstraints(minWidth: 0, minHeight: 0),
          border: InputBorder.none,
          contentPadding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
        ),
      ),
    );
  }
}

class _FeaturedCollectionCard extends StatelessWidget {
  const _FeaturedCollectionCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.12),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'EDUCAÇÃO 5.0',
            style: TextStyle(
              color: Color(0xFF22C55E),
              fontSize: 13,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.5,
            ),
          ),
          const SizedBox(height: 18),
          const Text(
            'Potencialize sua\njornada cognitiva.',
            style: TextStyle(
              color: AppColors.white,
              fontSize: 32,
              fontWeight: FontWeight.w800,
              height: 1.15,
              letterSpacing: -0.5,
            ),
          ),
          const SizedBox(height: 18),
          Text(
            'A curadoria definitiva de conhecimento e ferramentas para o estudante de alta performance.',
            style: TextStyle(
              color: AppColors.white.withValues(alpha: 0.65),
              fontSize: 15,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 28),
          _ExploreButton(onPressed: () {}),
          const SizedBox(height: 24),
          ClipRRect(
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(
              aspectRatio: 16 / 10,
              child: Container(
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [
                      Color(0xFF0B1A2E),
                      Color(0xFF0F2944),
                      Color(0xFF1A4A6B),
                    ],
                  ),
                ),
                child: const Center(
                  child: Icon(
                    Icons.dashboard_customize_outlined,
                    color: Color(0xFF22D3EE),
                    size: 64,
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductCard extends StatelessWidget {
  final String? category;
  final String title;
  final String description;
  final String price;
  final IconData imageIcon;

  const _ProductCard({
    this.category,
    required this.title,
    required this.description,
    required this.price,
    required this.imageIcon,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
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
            borderRadius: BorderRadius.circular(12),
            child: AspectRatio(
              aspectRatio: 16 / 11,
              child: Container(
                color: const Color(0xFFEFEFEF),
                child: Center(
                  child: Icon(
                    imageIcon,
                    size: 64,
                    color: AppColors.textSecondary.withValues(alpha: 0.6),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 16),
          if (category != null) ...[
            Text(
              category!,
              style: const TextStyle(
                color: AppColors.textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w700,
                letterSpacing: 1.2,
              ),
            ),
            const SizedBox(height: 8),
          ],
          Text(
            title,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 20,
              fontWeight: FontWeight.w800,
              height: 1.2,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            description,
            style: const TextStyle(
              color: AppColors.textSecondary,
              fontSize: 14,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 14),
          Text(
            price,
            style: const TextStyle(
              color: AppColors.textPrimary,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () {},
              icon: const Icon(Icons.add, size: 18, color: AppColors.textPrimary),
              label: const Text(
                'Carrinho',
                style: TextStyle(
                  color: AppColors.textPrimary,
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                ),
              ),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.inputFill,
                elevation: 0,
                padding: const EdgeInsets.symmetric(vertical: 14),
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(10),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ExploreButton extends StatelessWidget {
  final VoidCallback onPressed;

  const _ExploreButton({required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: onPressed,
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.purple,
        foregroundColor: AppColors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
      child: const Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'Explorar Coleção',
            style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
          ),
          SizedBox(width: 12),
          Icon(Icons.arrow_forward, size: 18),
        ],
      ),
    );
  }
}
