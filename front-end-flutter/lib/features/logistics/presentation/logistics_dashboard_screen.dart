import 'package:edu_ia/core/theme/app_colors.dart';
import 'package:flutter/material.dart';

class LogisticsDashboardScreen extends StatefulWidget {
  const LogisticsDashboardScreen({super.key});

  @override
  State<LogisticsDashboardScreen> createState() =>
      _LogisticsDashboardScreenState();
}

class _LogisticsDashboardScreenState extends State<LogisticsDashboardScreen> {
  int _currentIndex = 3;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: AppColors.inputFill,
          elevation: 0,
          titleSpacing: 20,
          title: const Text(
            'Edu Logistics',
            style: TextStyle(
              color: AppColors.textPrimary,
              fontSize: 20,
              fontWeight: FontWeight.w800,
            ),
          ),
          actions: [
            IconButton(
              onPressed: () => Navigator.pushNamed(context, '/notifications'),
              icon: const Icon(
                Icons.notifications_none,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(width: 8),
          ],
        ),
        body: SafeArea(
          top: false,
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 20, 20, 24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: const [
                _DashboardHeader(),
                SizedBox(height: 20),
                _CurrentDestinationCard(),
                SizedBox(height: 16),
                _DailyProgressCard(),
                SizedBox(height: 16),
                _NextStopsCard(),
                SizedBox(height: 16),
              ],
            ),
          ),
        ),
        floatingActionButton: FloatingActionButton(
          onPressed: () {},
          backgroundColor: AppColors.purple,
          elevation: 2,
          shape: const CircleBorder(),
          child: const Icon(Icons.add, color: AppColors.white),
        ),
        floatingActionButtonLocation: FloatingActionButtonLocation.endFloat,
        bottomNavigationBar: _LogisticsBottomNav(
          currentIndex: _currentIndex,
          onChanged: (i) {
            setState(() => _currentIndex = i);
            if (i == 2) {
              Navigator.pushNamed(context, '/logistics-picking');
            }
          },
        ),
      ),
    );
  }
}

class _DashboardHeader extends StatelessWidget {
  const _DashboardHeader();

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: 4,
          height: 56,
          margin: const EdgeInsets.only(top: 4, right: 14),
          decoration: BoxDecoration(
            color: AppColors.purple,
            borderRadius: BorderRadius.circular(4),
          ),
        ),
        const Expanded(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                'Painel de Logística',
                style: TextStyle(
                  fontSize: 28,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                  height: 1.1,
                ),
              ),
              SizedBox(height: 6),
              Text(
                'Roteiro otimizado para o Ciclo de Entrega',
                style: TextStyle(
                  fontSize: 14,
                  color: AppColors.textSecondary,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _CurrentDestinationCard extends StatelessWidget {
  const _CurrentDestinationCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFF2F3A3E), Color(0xFF445054)],
        ),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.18),
            blurRadius: 16,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(14, 16, 14, 16),
            decoration: BoxDecoration(
              color: AppColors.inputFill,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: AppColors.purple,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: const Icon(
                    Icons.navigation,
                    color: AppColors.white,
                    size: 22,
                  ),
                ),
                const SizedBox(width: 12),
                const Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'DESTINO ATUAL',
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w800,
                          color: AppColors.purple,
                          letterSpacing: 1,
                        ),
                      ),
                      SizedBox(height: 4),
                      Text(
                        'Av. Paulista,\n1578 - Edifício Education',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textPrimary,
                          height: 1.25,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.end,
                  children: [
                    Text(
                      'CHEGADA\nESTIMADA',
                      textAlign: TextAlign.right,
                      style: TextStyle(
                        fontSize: 10,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textSecondary,
                        letterSpacing: 0.8,
                        height: 1.2,
                      ),
                    ),
                    SizedBox(height: 4),
                    Text(
                      '14:25',
                      style: TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w800,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('Entrega confirmada!')),
                );
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: AppColors.primary,
                foregroundColor: AppColors.white,
                padding: const EdgeInsets.symmetric(vertical: 16),
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(14),
                ),
              ),
              icon: const Icon(Icons.check_circle_outline, size: 20),
              label: const Text(
                'Confirmar Entrega',
                style: TextStyle(fontSize: 15, fontWeight: FontWeight.w800),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DailyProgressCard extends StatelessWidget {
  const _DailyProgressCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Progresso do Dia',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                  color: AppColors.textPrimary,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: const Color(0xFFB8F2C9),
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  '85% Completo',
                  style: TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF1F7A3F),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 14),
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: const LinearProgressIndicator(
              value: 0.85,
              minHeight: 8,
              backgroundColor: Color(0xFFE2D6F8),
              valueColor: AlwaysStoppedAnimation<Color>(AppColors.purple),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: const [
              Expanded(child: _ProgressTile(label: 'Entregues', value: '12/15')),
              SizedBox(width: 12),
              Expanded(
                child: _ProgressTile(label: 'Tempo Restante', value: '45min'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _ProgressTile extends StatelessWidget {
  final String label;
  final String value;

  const _ProgressTile({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            label,
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
              fontWeight: FontWeight.w600,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: const TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
        ],
      ),
    );
  }
}

class _NextStopsCard extends StatelessWidget {
  const _NextStopsCard();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: const [
          Text(
            'Próximas Paradas',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          SizedBox(height: 14),
          _StopItem(
            index: 1,
            title: 'Kit Acadêmico Premium',
            address: 'Rua Oscar Freire, 1142 - Ap 42',
            highlighted: true,
            highPriority: true,
          ),
          SizedBox(height: 12),
          _StopItem(
            index: 2,
            title: 'Tablet Diagnostic 5.0',
            address: 'Al. Santos, 450 - Recepção',
          ),
          SizedBox(height: 12),
          _StopItem(
            index: 3,
            title: 'Material Gráfico Ciclo 2',
            address: 'Rua Augusta, 2800 - Portaria',
          ),
        ],
      ),
    );
  }
}

class _StopItem extends StatelessWidget {
  final int index;
  final String title;
  final String address;
  final bool highlighted;
  final bool highPriority;

  const _StopItem({
    required this.index,
    required this.title,
    required this.address,
    this.highlighted = false,
    this.highPriority = false,
  });

  @override
  Widget build(BuildContext context) {
    final bg = highlighted ? const Color(0xFFF1E8FB) : Colors.transparent;
    final badgeBg = highlighted ? AppColors.purple : const Color(0xFFD9DBE0);
    final badgeFg = highlighted ? AppColors.white : AppColors.textSecondary;
    final borderColor = highlighted ? AppColors.purple : Colors.transparent;

    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(14),
        border: Border(left: BorderSide(color: borderColor, width: 4)),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Container(
            width: 32,
            height: 32,
            decoration: BoxDecoration(color: badgeBg, shape: BoxShape.circle),
            alignment: Alignment.center,
            child: Text(
              '$index',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w800,
                color: badgeFg,
              ),
            ),
          ),
          const SizedBox(width: 14),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w800,
                    color: AppColors.textPrimary,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  address,
                  style: const TextStyle(
                    fontSize: 13,
                    color: AppColors.textSecondary,
                  ),
                ),
                if (highPriority) ...[
                  const SizedBox(height: 6),
                  const Text(
                    '! ALTA PRIORIDADE',
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.w800,
                      color: AppColors.purple,
                      letterSpacing: 0.8,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LogisticsBottomNav extends StatelessWidget {
  final int currentIndex;
  final ValueChanged<int> onChanged;

  const _LogisticsBottomNav({
    required this.currentIndex,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final items = [
      (Icons.dashboard_outlined, 'Painel'),
      (Icons.map_outlined, 'Rota'),
      (Icons.shopping_bag_outlined, 'Separação'),
      (Icons.local_shipping_outlined, 'Pedidos'),
      (Icons.show_chart, 'Indicadores'),
    ];

    return Container(
      decoration: BoxDecoration(
        color: AppColors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 12,
            offset: const Offset(0, -2),
          ),
        ],
      ),
      child: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (var i = 0; i < items.length; i++)
                Expanded(
                  child: _NavItem(
                    icon: items[i].$1,
                    label: items[i].$2,
                    selected: i == currentIndex,
                    onTap: () => onChanged(i),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const _NavItem({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final color = selected ? AppColors.purple : AppColors.textSecondary;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, color: color, size: 22),
            const SizedBox(height: 4),
            Text(
              label,
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w700,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
