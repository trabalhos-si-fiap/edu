import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../../core/theme/app_colors.dart';
import '../../auth/data/auth_api.dart';
import '../../cart/data/cart_store.dart';
import '../../components/nav_bar.dart';
import '../../tracker/domain/study_summary.dart';
import '../../tracker/presentation/points_card.dart';
import '../../tracker/presentation/summary_provider.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _authApi = AuthApi();
  final _summaryProvider = SummaryProvider();
  String? _name;

  @override
  void initState() {
    super.initState();
    _loadName();
    _summaryProvider.load();
  }

  @override
  void dispose() {
    _summaryProvider.dispose();
    super.dispose();
  }

  Future<void> _loadName() async {
    final name = await _authApi.currentDisplayName();
    if (!mounted || name == null || name.isEmpty) return;
    setState(() => _name = name);
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          leading: IconButton(
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
            onPressed: () => Navigator.pop(context),
          ),
          title: const Text(
            'Meu perfil',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontWeight: FontWeight.w700,
              fontSize: 18,
            ),
          ),
        ),
        body: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _AvatarSection(name: _name),
              const SizedBox(height: 24),
              AnimatedBuilder(
                animation: _summaryProvider,
                builder: (context, _) {
                  // Enquanto carrega, mostra ZERO — não um valor de exemplo,
                  // e não um vazio que pula a tela quando o dado chega.
                  final resumo = _summaryProvider.summary;
                  final pontos = resumo?.points ?? const Points(total: 0, level: 1, streak: 0);
                  final estudo =
                      resumo?.study ?? const Study(answeredQuestions: 0, startedSubtopics: 0);
                  return Column(
                    children: [
                      PointsCard(points: pontos),
                      const SizedBox(height: 16),
                      StudyStatsRow(points: pontos, study: estudo),
                    ],
                  );
                },
              ),
              const SizedBox(height: 24),
              const Text(
                'Configurações',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: AppColors.textPrimary,
                ),
              ),
              const SizedBox(height: 12),
              _SettingsCard(
                items: const [
                  _SettingsItem(Icons.person_outline, 'Editar perfil e configurações'),
                  _SettingsItem(
                    Icons.track_changes_outlined,
                    'Metas e objetivos',
                    route: '/onboarding',
                  ),
                  _SettingsItem(
                    Icons.receipt_long_outlined,
                    'Meus pedidos',
                    route: '/orders',
                  ),
                  _SettingsItem(
                    Icons.location_on_outlined,
                    'Meus endereços',
                    route: '/addresses',
                  ),
                  _SettingsItem(Icons.notifications_none, 'Configuração'),
                ],
              ),
              const SizedBox(height: 12),
              _SettingsCard(
                items: const [
                  _SettingsItem(Icons.help_outline, 'Help & Support'),
                  _SettingsItem(Icons.verified_user_outlined, 'Privacy Policy'),
                ],
                trailing: _LogoutTile(onTap: () async {
                  final navigator = Navigator.of(context);
                  context.read<CartStore>().reset();
                  await _authApi.logout();
                  navigator.pushNamedAndRemoveUntil('/login', (_) => false);
                }),
              ),
            ],
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: -1),
      ),
    );
  }
}

class _AvatarSection extends StatelessWidget {
  const _AvatarSection({this.name});

  final String? name;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        children: [
          Stack(
            alignment: Alignment.bottomRight,
            children: [
              Container(
                width: 120,
                height: 120,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.purple, width: 3),
                  color: const Color(0xFFE8D5FF),
                ),
                child: const Icon(
                  Icons.person,
                  size: 60,
                  color: AppColors.purple,
                ),
              ),
              Container(
                width: 32,
                height: 32,
                decoration: BoxDecoration(
                  color: AppColors.purple,
                  shape: BoxShape.circle,
                  border: Border.all(color: AppColors.white, width: 2),
                ),
                child: const Icon(Icons.edit, size: 16, color: AppColors.white),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Text(
            name == null || name!.isEmpty ? 'Aluno(a)' : name!,
            style: const TextStyle(
              fontSize: 24,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            decoration: BoxDecoration(
              color: AppColors.purple,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Text(
              'LEVEL 18 SCHOLAR',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.white,
                letterSpacing: 1,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _SettingsItem {
  const _SettingsItem(this.icon, this.label, {this.route});
  final IconData icon;
  final String label;
  final String? route;
}

class _SettingsCard extends StatelessWidget {
  const _SettingsCard({required this.items, this.trailing});

  final List<_SettingsItem> items;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Column(
        children: [
          ...items.map((item) => ListTile(
                leading: Icon(item.icon, color: AppColors.textSecondary),
                title: Text(
                  item.label,
                  style: const TextStyle(fontSize: 14, color: AppColors.textPrimary),
                ),
                trailing: const Icon(Icons.chevron_right, color: AppColors.textSecondary, size: 20),
                onTap: item.route == null
                    ? () {}
                    : () => Navigator.pushNamed(context, item.route!),
              )),
          ?trailing,
        ],
      ),
    );
  }
}

class _LogoutTile extends StatelessWidget {
  const _LogoutTile({required this.onTap});

  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: const Icon(Icons.logout, color: Colors.red),
      title: const Text(
        'Logout',
        style: TextStyle(fontSize: 14, color: Colors.red, fontWeight: FontWeight.w600),
      ),
      onTap: onTap,
    );
  }
}
