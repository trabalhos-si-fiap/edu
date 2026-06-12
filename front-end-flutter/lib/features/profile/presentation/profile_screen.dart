import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../auth/data/auth_api.dart';
import '../../components/nav_bar.dart';

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  final _authApi = AuthApi();
  String? _name;

  @override
  void initState() {
    super.initState();
    _loadName();
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
              const _PointsCard(),
              const SizedBox(height: 16),
              const _StatsRow(),
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
                  _SettingsItem(Icons.track_changes_outlined, 'Metas e objetivos'),
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
                trailing: _LogoutTile(onTap: () {
                  Navigator.pushNamedAndRemoveUntil(
                    context,
                    '/login',
                    (_) => false,
                  );
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

class _PointsCard extends StatelessWidget {
  const _PointsCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Total de pontos',
                style: TextStyle(
                  fontSize: 13,
                  color: AppColors.textSecondary,
                ),
              ),
              SizedBox(height: 4),
              Text(
                '3,120',
                style: TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
            ],
          ),
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: AppColors.purple,
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.star, color: AppColors.white, size: 22),
          ),
        ],
      ),
    );
  }
}

class _StatsRow extends StatelessWidget {
  const _StatsRow();

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.description_outlined, size: 24, color: AppColors.textSecondary),
                SizedBox(height: 12),
                Text(
                  '15',
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                ),
                SizedBox(height: 2),
                Text('Testes', style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
              ],
            ),
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: AppColors.white,
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(Icons.access_time, size: 24, color: AppColors.textSecondary),
                SizedBox(height: 12),
                Text(
                  '48h',
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: AppColors.textPrimary),
                ),
                SizedBox(height: 2),
                Text('Horas de estudo', style: TextStyle(fontSize: 13, color: AppColors.textSecondary)),
              ],
            ),
          ),
        ),
      ],
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
