import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/logistics_api.dart';
import '../domain/order.dart';
import 'widgets/logistics_scaffold.dart';

class EntregadorEmRotaScreen extends StatefulWidget {
  const EntregadorEmRotaScreen({super.key});

  @override
  State<EntregadorEmRotaScreen> createState() => _EntregadorEmRotaScreenState();
}

class _EntregadorEmRotaScreenState extends State<EntregadorEmRotaScreen> {
  final _api = LogisticsApi();
  late Future<List<Pedido>> _entregasFuture;
  String? _acaoEmAndamentoId;

  @override
  void initState() {
    super.initState();
    _carregarEntregas();
  }

  void _carregarEntregas() {
    // Corpo em bloco, não em seta: `() => _x = umFuture` devolve o Future
    // atribuído, e o `setState` derruba a tela ao ver um retorno não nulo.
    setState(() {
      _entregasFuture = _api.fetchMinhasEntregas();
    });
  }

  Future<void> _confirmarEntregaComDialogo(Pedido pedido) async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Confirmar entrega?'),
        content: Text(
          'Pedido #${pedido.idCurto}\n${pedido.enderecoEntrega}\n\n'
          'Confirme apenas após entregar o material ao destinatário.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );

    if (confirmar != true) return;

    setState(() => _acaoEmAndamentoId = pedido.id);
    try {
      await _api.confirmarEntrega(pedido.id);
      _carregarEntregas();
    } on LogisticsException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _acaoEmAndamentoId = null);
    }
  }

  Future<void> _abrirDialogoAtraso(Pedido pedido) async {
    final motivoController = TextEditingController();
    DateTime novaData = DateTime.now().add(const Duration(days: 1));

    final resultado = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setDialogState) {
            return AlertDialog(
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              title: const Text('Reportar atraso na entrega'),
              content: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Pedido #${pedido.idCurto}', style: const TextStyle(fontWeight: FontWeight.w700)),
                    const SizedBox(height: 12),
                    const Text(
                      'O aluno será notificado e poderá aceitar a nova data '
                      'ou cancelar o pedido.',
                      style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: motivoController,
                      maxLines: 2,
                      decoration: const InputDecoration(
                        labelText: 'Motivo do atraso',
                        hintText: 'Ex: trânsito intenso na região',
                        border: OutlineInputBorder(),
                      ),
                      onChanged: (_) => setDialogState(() {}),
                    ),
                    const SizedBox(height: 16),
                    InkWell(
                      onTap: () async {
                        final data = await showDatePicker(
                          context: context,
                          initialDate: novaData,
                          firstDate: DateTime.now(),
                          lastDate: DateTime.now().add(const Duration(days: 30)),
                        );
                        if (data != null) setDialogState(() => novaData = data);
                      },
                      child: Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: AppColors.inputFill,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.calendar_today, size: 18, color: AppColors.purple),
                            const SizedBox(width: 10),
                            Text(
                              'Nova data sugerida: '
                              '${novaData.day.toString().padLeft(2, '0')}/'
                              '${novaData.month.toString().padLeft(2, '0')}/'
                              '${novaData.year}',
                              style: const TextStyle(
                                fontSize: 14,
                                fontWeight: FontWeight.w600,
                                color: AppColors.textPrimary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancelar'),
                ),
                ElevatedButton(
                  onPressed: motivoController.text.trim().isEmpty
                      ? null
                      : () => Navigator.pop(context, {
                            'motivo': motivoController.text.trim(),
                            'novaData': novaData,
                          }),
                  child: const Text('Reportar'),
                ),
              ],
            );
          },
        );
      },
    );

    if (resultado == null) return;

    setState(() => _acaoEmAndamentoId = pedido.id);
    try {
      await _api.reportarAtrasoEntrega(
        pedidoId: pedido.id,
        motivo: resultado['motivo'] as String,
        novaDataSugerida: resultado['novaData'] as DateTime,
      );
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Atraso reportado. O aluno foi notificado.')),
        );
      }
    } on LogisticsException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _acaoEmAndamentoId = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return LogisticsScaffold(
      titulo: 'Entregas em Rota',
      body: RefreshIndicator(
        onRefresh: () async => _carregarEntregas(),
        child: FutureBuilder<List<Pedido>>(
          future: _entregasFuture,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  const SizedBox(height: 80),
                  FilaVaziaState(
                    mensagem: 'Erro ao carregar entregas:\n${snapshot.error}',
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
                    mensagem: 'Você não tem entregas em rota no momento.',
                    icon: Icons.map_outlined,
                  ),
                ],
              );
            }
            return ListView.builder(
              padding: const EdgeInsets.all(20),
              itemCount: pedidos.length,
              itemBuilder: (context, index) {
                final pedido = pedidos[index];
                final emAndamento = _acaoEmAndamentoId == pedido.id;

                return Card(
                  margin: const EdgeInsets.only(bottom: 12),
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                    side: const BorderSide(color: AppColors.inputBorder),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Container(
                              width: 44,
                              height: 44,
                              decoration: BoxDecoration(
                                color: const Color(0xFFEDE0FF),
                                borderRadius: BorderRadius.circular(12),
                              ),
                              child: const Icon(
                                Icons.local_shipping,
                                color: AppColors.purple,
                                size: 22,
                              ),
                            ),
                            const SizedBox(width: 12),
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
                                  const SizedBox(height: 2),
                                  Text(
                                    pedido.enderecoEntrega,
                                    maxLines: 1,
                                    overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(
                                      fontSize: 13,
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 14),
                        Row(
                          children: [
                            Expanded(
                              child: OutlinedButton.icon(
                                onPressed:
                                    emAndamento ? null : () => _abrirDialogoAtraso(pedido),
                                icon: const Icon(Icons.schedule, size: 18),
                                label: const Text(
                                  'Reportar atraso',
                                  style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
                                ),
                                style: OutlinedButton.styleFrom(
                                  foregroundColor: const Color(0xFFB86E00),
                                  side: const BorderSide(color: Color(0xFFFFD08A)),
                                  padding: const EdgeInsets.symmetric(vertical: 12),
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(10),
                                  ),
                                ),
                              ),
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: ElevatedButton.icon(
                                onPressed: emAndamento
                                    ? null
                                    : () => _confirmarEntregaComDialogo(pedido),
                                icon: emAndamento
                                    ? const SizedBox(
                                        width: 16,
                                        height: 16,
                                        child: CircularProgressIndicator(
                                          strokeWidth: 2,
                                          color: Colors.white,
                                        ),
                                      )
                                    : const Icon(Icons.check_circle_outline, size: 18),
                                label: Text(emAndamento ? '...' : 'Entregue'),
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                );
              },
            );
          },
        ),
      ),
    );
  }
}
