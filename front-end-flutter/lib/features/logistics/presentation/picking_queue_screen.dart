import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/logistics_api.dart';
import '../domain/order.dart';
import 'picking_screen.dart';
import 'widgets/logistics_scaffold.dart';

class SeparadorFilaScreen extends StatefulWidget {
  const SeparadorFilaScreen({super.key});

  @override
  State<SeparadorFilaScreen> createState() => _SeparadorFilaScreenState();
}

class _SeparadorFilaScreenState extends State<SeparadorFilaScreen> {
  final _api = LogisticsApi();
  late Future<List<Pedido>> _filaFuture;

  @override
  void initState() {
    super.initState();
    _carregarFila();
  }

  void _carregarFila() {
    setState(() => _filaFuture = _api.fetchFilaSeparacao());
  }

  Future<void> _abrirPedido(Pedido pedido) async {
    final resultado = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) => SeparadorPickingScreen(pedido: pedido),
      ),
    );
    if (resultado == true) _carregarFila();
  }

  @override
  Widget build(BuildContext context) {
    return LogisticsScaffold(
      titulo: 'Fila de Separação',
      showLogout: true,
      body: RefreshIndicator(
        onRefresh: () async => _carregarFila(),
        child: FutureBuilder<List<Pedido>>(
          future: _filaFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  const SizedBox(height: 80),
                  FilaVaziaState(
                    mensagem: 'Erro ao carregar a fila:\n${snapshot.error}',
                    icon: Icons.error_outline,
                  ),
                ],
              );
            }
            final pedidos = snapshot.data ?? [];
            if (pedidos.isEmpty) {
              return ListView(
                children: const [
                  SizedBox(height: 80),
                  FilaVaziaState(
                    mensagem: 'Nenhum pedido aguardando separação no momento.',
                    icon: Icons.inventory_2_outlined,
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: pedidos.length,
              itemBuilder: (context, index) {
                final pedido = pedidos[index];
                return _PedidoFilaCard(
                  pedido: pedido,
                  onTap: () => _abrirPedido(pedido),
                );
              },
            );
          },
        ),
      ),
    );
  }
}

class _PedidoFilaCard extends StatelessWidget {
  const _PedidoFilaCard({required this.pedido, required this.onTap});

  final Pedido pedido;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: AppColors.inputBorder),
      ),
      child: InkWell(
        borderRadius: BorderRadius.circular(16),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            children: [
              Container(
                width: 48,
                height: 48,
                decoration: BoxDecoration(
                  color: AppColors.inputFill,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: const Icon(
                  Icons.inventory_2_outlined,
                  color: AppColors.purple,
                  size: 24,
                ),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Pedido #${pedido.idCurto}',
                      style: const TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      pedido.enderecoEntrega,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right, color: AppColors.textSecondary),
            ],
          ),
        ),
      ),
    );
  }
}
