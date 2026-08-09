import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/logistics_api.dart';
import '../domain/order.dart';

class EntregadorDetalheScreen extends StatefulWidget {
  const EntregadorDetalheScreen({super.key, required this.pedido});

  final Pedido pedido;

  @override
  State<EntregadorDetalheScreen> createState() => _EntregadorDetalheScreenState();
}

class _EntregadorDetalheScreenState extends State<EntregadorDetalheScreen> {
  final _api = LogisticsApi();
  bool _carregando = false;
  String? _erro;

  Future<void> _confirmarColeta() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      await _api.confirmarColeta(widget.pedido.id);
      if (mounted) Navigator.pop(context, true);
    } on LogisticsException catch (e) {
      if (mounted) setState(() => _erro = e.message);
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final pedido = widget.pedido;

    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: Text(
            'Pedido #${pedido.idCurto}',
            style: const TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        body: SafeArea(
          child: Column(
            children: [
              Expanded(
                child: SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'Endereço de entrega',
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w700,
                          color: AppColors.textSecondary,
                          letterSpacing: 0.5,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(20),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          boxShadow: [
                            BoxShadow(
                              color: Colors.black.withValues(alpha: 0.05),
                              blurRadius: 12,
                              offset: const Offset(0, 4),
                            ),
                          ],
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.place, color: AppColors.purple, size: 28),
                            const SizedBox(width: 14),
                            Expanded(
                              child: Text(
                                pedido.enderecoEntrega,
                                style: const TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w700,
                                  color: AppColors.textPrimary,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 24),
                      const Text(
                        'Itens a coletar',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 12),
                      Container(
                        width: double.infinity,
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: AppColors.inputFill,
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: Column(
                          children: pedido.itens.isEmpty
                              ? [
                                  const Text(
                                    'Kit já conferido pelo separador.',
                                    style: TextStyle(
                                      fontSize: 14,
                                      color: AppColors.textSecondary,
                                    ),
                                  ),
                                ]
                              : pedido.itens
                                  .map(
                                    (item) => Padding(
                                      padding: const EdgeInsets.symmetric(vertical: 6),
                                      child: Row(
                                        children: [
                                          const Icon(
                                            Icons.check_circle,
                                            size: 18,
                                            color: AppColors.purple,
                                          ),
                                          const SizedBox(width: 10),
                                          Expanded(
                                            child: Text(
                                              '${item.nomeProduto ?? 'Produto #${item.produtoId}'} '
                                              '(x${item.quantidade})',
                                              style: const TextStyle(
                                                fontSize: 14,
                                                color: AppColors.textPrimary,
                                              ),
                                            ),
                                          ),
                                        ],
                                      ),
                                    ),
                                  )
                                  .toList(),
                        ),
                      ),
                      if (_erro != null) ...[
                        const SizedBox(height: 16),
                        Text(_erro!, style: const TextStyle(color: Colors.red, fontSize: 13)),
                      ],
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(24),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton.icon(
                    onPressed: _carregando ? null : _confirmarColeta,
                    icon: _carregando
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          )
                        : const Icon(Icons.check, color: Colors.white),
                    label: const Text('Confirmar Coleta'),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
