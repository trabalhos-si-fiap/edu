import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/logistics_api.dart';
import '../domain/order.dart';
import 'delivery_detail_screen.dart';
import 'tracking_screen.dart';
import 'widgets/logistics_scaffold.dart';

class EntregadorFilaScreen extends StatefulWidget {
  const EntregadorFilaScreen({super.key});

  @override
  State<EntregadorFilaScreen> createState() => _EntregadorFilaScreenState();
}

class _EntregadorFilaScreenState extends State<EntregadorFilaScreen> {
  final _api = LogisticsApi();
  late Future<List<Pedido>> _filaFuture;

  @override
  void initState() {
    super.initState();
    _carregarFila();
  }

  void _carregarFila() {
    setState(() => _filaFuture = _api.fetchFilaEntrega());
  }

  Future<void> _abrirPedido(Pedido pedido) async {
    final coletado = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => EntregadorDetalheScreen(pedido: pedido)),
    );
    if (coletado == true) _carregarFila();
  }

  void _abrirEmRota() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (_) => const EntregadorEmRotaScreen()),
    );
  }

  @override
  Widget build(BuildContext context) {
    return LogisticsScaffold(
      titulo: 'Fila de Coleta',
      showLogout: true,
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _abrirEmRota,
        backgroundColor: AppColors.purple,
        icon: const Icon(Icons.local_shipping, color: Colors.white),
        label: const Text(
          'Em rota',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w700),
        ),
      ),
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
                    mensagem: 'Nenhum pedido aguardando coleta no momento.',
                    icon: Icons.local_shipping_outlined,
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 100),
              itemCount: pedidos.length,
              itemBuilder: (context, index) {
                final pedido = pedidos[index];
                return _PedidoColetaCard(pedido: pedido, onTap: () => _abrirPedido(pedido));
              },
            );
          },
        ),
      ),
    );
  }
}

class _PedidoColetaCard extends StatelessWidget {
  const _PedidoColetaCard({required this.pedido, required this.onTap});

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
                  Icons.local_shipping_outlined,
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
                      'Pedido #${pedido.id}',
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
