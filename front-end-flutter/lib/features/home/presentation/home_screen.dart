import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../features/auth/data/auth_api.dart';
import '../../../features/components/top_bar.dart';
import '../../tracker/presentation/goal_card.dart';
import '../../tracker/presentation/summary_provider.dart';


class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final _authApi = AuthApi();
  final _summaryProvider = SummaryProvider();
  String? _firstName;
  bool _welcomeHandled = false;

  @override
  void initState() {
    super.initState();
    _loadName();
    _summaryProvider.load();
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybeShowWelcome());
  }

  @override
  void dispose() {
    _summaryProvider.dispose();
    super.dispose();
  }

  Future<void> _loadName() async {
    final name = await _authApi.currentDisplayName();
    if (!mounted || name == null || name.isEmpty) return;
    setState(() => _firstName = name.split(' ').first);
  }

  void _maybeShowWelcome() {
    if (_welcomeHandled || !mounted) return;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is! Map) return;

    final String? message;
    if (args['justRegistered'] == true) {
      message = 'Conta criada com sucesso! 🎉';
    } else if (args['justLoggedIn'] == true) {
      message = 'Login realizado com sucesso!';
    } else {
      message = null;
    }
    if (message == null) return;

    _welcomeHandled = true;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message), backgroundColor: AppColors.purple),
    );
  }

  @override
  Widget build(BuildContext context) {
    final name = _firstName;
    final greeting = name == null || name.isEmpty
        ? 'Bem vindo(a)!'
        : 'Bem vindo(a) de\nvolta, $name!';
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: const TopBar(),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 24),
                Text(
                  greeting,
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                    height: 1.2,
                  ),
                ),
                const SizedBox(height: 24),
                AnimatedBuilder(
                  animation: _summaryProvider,
                  builder: (context, _) {
                    final resumo = _summaryProvider.summary;
                    // Enquanto carrega, e quando falha, a home não inventa
                    // número nenhum: o cartão simplesmente não aparece.
                    if (resumo == null) return const SizedBox.shrink();
                    return GoalCard(summary: resumo);
                  },
                ),
                const SizedBox(height: 16),
                const _FeatureRow(),
              ],
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 0),
      ),
    );
  }
}

class _FeatureRow extends StatelessWidget {
  const _FeatureRow();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _SquareCard(
            label: 'Identificar\nlacunas',
            image: 'assets/images/checklist.png',
            color: const Color(0xFF369FFF),
            // O diagnóstico de lacunas começa pela escolha da matéria.
            onTap: () => Navigator.pushNamed(context, '/quiz'),
          ),
        ),
        const SizedBox(width: 14),
      ],
    );
  }
}

class _SquareCard extends StatelessWidget {
  const _SquareCard({
    required this.label,
    required this.image,
    required this.color,
    required this.onTap,
  });

  final String label;
  final String image;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        height: 140,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: color,
          borderRadius: BorderRadius.circular(24),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceAround,
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Flexible(
              child: Text(
                label,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: AppColors.white,
                ),
              ),
            ),
            const SizedBox(width: 9),
            Image.asset(image, width: 60, height: 60),
          ],
        ),
      ),
    );
  }
}
