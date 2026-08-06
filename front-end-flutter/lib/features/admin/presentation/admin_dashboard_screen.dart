import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/admin_api.dart';
import '../domain/analytics.dart';
import 'widgets/admin_scaffold.dart';
import 'widgets/admin_widgets.dart';

/// Tela inicial do modo Admin: relatório executivo (GET
/// /analytics/executive-summary), mini gráfico de pedidos por status, e
/// placeholders para as seções ainda sem backend (estoque, transportadoras).
class AdminDashboardScreen extends StatefulWidget {
  const AdminDashboardScreen({super.key});

  @override
  State<AdminDashboardScreen> createState() => _AdminDashboardScreenState();
}

class _AdminDashboardScreenState extends State<AdminDashboardScreen> {
  final _api = AdminApi();
  late Future<_DashboardData> _dataFuture;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  void _carregar() {
    setState(() {
      _dataFuture = _carregarDados();
    });
  }

  Future<_DashboardData> _carregarDados() async {
    // As duas chamadas são independentes — busca em paralelo pra tela não
    // demorar o dobro do tempo esperando uma depois da outra.
    final resumo = await _api.fetchResumoExecutivo(dias: 7);
    final entregas = await _api.fetchEntregasPorStatus();
    return _DashboardData(resumo: resumo, entregasPorStatus: entregas);
  }

  @override
  Widget build(BuildContext context) {
    return AdminScaffold(
      tab: AdminTab.dashboard,
      titulo: 'Painel Administrativo',
      body: RefreshIndicator(
        onRefresh: () async => _carregar(),
        child: FutureBuilder<_DashboardData>(
          future: _dataFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  const SizedBox(height: 60),
                  AdminErrorState(
                    mensagem: 'Erro ao carregar o dashboard:\n${snapshot.error}',
                    onRetry: _carregar,
                  ),
                ],
              );
            }
            final data = snapshot.data!;
            return ListView(
              padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
              children: [
                _CabecalhoResumo(resumo: data.resumo),
                const SizedBox(height: 16),
                _GradeMetricas(resumo: data.resumo),
                const SizedBox(height: 16),
                AdminSectionCard(
                  title: 'Pedidos por status',
                  subtitle: 'Últimos 7 dias',
                  child: MiniBarChart(
                    data: {
                      for (final s in data.entregasPorStatus)
                        _rotuloStatus(s.status): s.total,
                    },
                  ),
                ),
                const SizedBox(height: 16),
                AdminSectionCard(
                  title: 'Controle de estoque',
                  child: AdminComingSoon(
                    icon: Icons.inventory_2_outlined,
                    mensagem:
                        'Painel de níveis de estoque e alertas de reposição.',
                    tag: 'Em desenvolvimento',
                  ),
                ),
                const SizedBox(height: 16),
                AdminSectionCard(
                  title: 'Controle de transportadoras',
                  child: AdminComingSoon(
                    icon: Icons.local_shipping_outlined,
                    mensagem:
                        'Desempenho e SLA por transportadora parceira.',
                    tag: 'Em breve',
                  ),
                ),
              ],
            );
          },
        ),
      ),
    );
  }
}

class _DashboardData {
  const _DashboardData({required this.resumo, required this.entregasPorStatus});

  final ResumoExecutivo resumo;
  final List<StatusContagem> entregasPorStatus;
}

/// Texto do relatório executivo, gerado por LLM no backend
/// (analytics-service/app/services/resumo_ia.py) a partir das métricas do
/// período.
class _CabecalhoResumo extends StatelessWidget {
  const _CabecalhoResumo({required this.resumo});

  final ResumoExecutivo resumo;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: AppColors.primary,
        borderRadius: BorderRadius.circular(18),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                decoration: BoxDecoration(
                  color: AppColors.purple,
                  borderRadius: BorderRadius.circular(20),
                ),
                child: const Text(
                  'RELATÓRIO EXECUTIVO',
                  style: TextStyle(
                    color: AppColors.white,
                    fontSize: 10,
                    fontWeight: FontWeight.w800,
                    letterSpacing: 0.4,
                  ),
                ),
              ),
              const Spacer(),
              Text(
                'Últimos ${resumo.periodoDias} dias',
                style: const TextStyle(color: AppColors.background, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            resumo.resumoExecutivo,
            style: const TextStyle(
              color: AppColors.white,
              fontSize: 14,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }
}

class _GradeMetricas extends StatelessWidget {
  const _GradeMetricas({required this.resumo});

  final ResumoExecutivo resumo;

  @override
  Widget build(BuildContext context) {
    final m = resumo.metricas;
    return GridView.count(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      crossAxisCount: 2,
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.5,
      children: [
        AdminStatCard(
          icon: Icons.shopping_bag_outlined,
          label: 'Pedidos criados',
          value: '${m.pedidosCriados}',
        ),
        AdminStatCard(
          icon: Icons.report_problem_outlined,
          label: 'Ocorrências abertas',
          value: '${m.ocorrenciasAbertas}',
          badge: m.ocorrenciasAbertas > 0 ? 'Atenção' : null,
          badgeColor: AppColors.danger,
        ),
        AdminStatCard(
          icon: Icons.task_alt_outlined,
          label: 'Ocorrências resolvidas',
          value: '${m.ocorrenciasResolvidas}',
          badge: 'OK',
          badgeColor: AppColors.success,
        ),
        AdminStatCard(
          icon: Icons.psychology_outlined,
          label: 'Diagnósticos (ações)',
          value: '${m.diagnosticosPorAcao.values.fold<int>(0, (a, b) => a + b)}',
        ),
      ],
    );
  }
}

String _rotuloStatus(String status) {
  // Valores reais de back-end/commerce-service/app/services/status_pedido.py
  // (StatusPedido enum) — string, maiúscula, sem tradução pro Flutter
  // porque o analytics-service não serve o app do aluno.
  const rotulos = {
    'CRIADO': 'Criado',
    'AGUARDANDO_SEPARACAO': 'Ag. separ.',
    'EM_SEPARACAO': 'Separando',
    'SEPARADO': 'Separado',
    'AGUARDANDO_COLETA': 'Ag. coleta',
    'EM_TRANSITO': 'Trânsito',
    'ENTREGUE': 'Entregue',
    'CANCELADO': 'Cancelado',
  };
  return rotulos[status] ?? status;
}
