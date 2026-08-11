import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../logistics/data/logistics_api.dart';
import '../../logistics/domain/occurrence.dart';

/// Tela onde o aluno resolve uma ocorrência aberta pelo separador (item em
/// falta) ou pelo entregador (atraso na entrega).
///
/// Navegada a partir da tela de notificações, usando o `ocorrencia_id` que
/// vem em `NotificationModel.data['ocorrencia_id']`.
class OcorrenciaResolucaoScreen extends StatefulWidget {
  const OcorrenciaResolucaoScreen({super.key, required this.ocorrenciaId});

  final int ocorrenciaId;

  @override
  State<OcorrenciaResolucaoScreen> createState() => _OcorrenciaResolucaoScreenState();
}

class _OcorrenciaResolucaoScreenState extends State<OcorrenciaResolucaoScreen> {
  final _api = LogisticsApi();
  late Future<Ocorrencia> _ocorrenciaFuture;
  String? _produtoSelecionadoId;
  bool _enviando = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  void _carregar() {
    // Corpo em bloco, não em seta: `() => _x = umFuture` devolve o Future
    // atribuído, e o `setState` derruba a tela ao ver um retorno não nulo.
    setState(() {
      _ocorrenciaFuture = _api.fetchOcorrencia(widget.ocorrenciaId);
    });
  }

  Future<void> _resolver(String resolucao, {String? produtoEscolhidoId}) async {
    setState(() => _enviando = true);
    try {
      await _api.resolverOcorrencia(
        ocorrenciaId: widget.ocorrenciaId,
        resolucao: resolucao,
        produtoEscolhidoId: produtoEscolhidoId,
      );
      if (mounted) Navigator.pop(context, true);
    } on LogisticsException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _enviando = false);
    }
  }

  Future<void> _confirmarCancelamento() async {
    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Cancelar pedido?'),
        content: const Text(
          'Essa ação não pode ser desfeita. O pedido inteiro será cancelado.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Voltar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.red,
              foregroundColor: Colors.white,
            ),
            child: const Text('Cancelar pedido'),
          ),
        ],
      ),
    );

    if (confirmar == true) {
      await _resolver('cancelar_pedido');
    }
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
          title: const Text(
            'Resolver Pendência',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        body: SafeArea(
          child: FutureBuilder<Ocorrencia>(
            future: _ocorrenciaFuture,
            builder: (context, snapshot) {
              if (snapshot.connectionState == ConnectionState.waiting) {
                return const Center(child: CircularProgressIndicator());
              }
              if (snapshot.hasError) {
                return Center(
                  child: Padding(
                    padding: const EdgeInsets.all(24),
                    child: Text(
                      'Erro ao carregar: ${snapshot.error}',
                      textAlign: TextAlign.center,
                      style: const TextStyle(color: AppColors.textSecondary),
                    ),
                  ),
                );
              }

              final ocorrencia = snapshot.data!;
              if (!ocorrencia.aberta) return _JaResolvidaState(ocorrencia: ocorrencia);

              return ocorrencia.tipo == 'FALTA_ESTOQUE'
                  ? _FaltaEstoqueContent(
                      ocorrencia: ocorrencia,
                      produtoSelecionadoId: _produtoSelecionadoId,
                      enviando: _enviando,
                      onSelecionarProduto: (id) => setState(() => _produtoSelecionadoId = id),
                      onSubstituir: () =>
                          _resolver('substituir', produtoEscolhidoId: _produtoSelecionadoId),
                      onRemoverItem: () => _resolver('remover_item'),
                      onCancelarPedido: _confirmarCancelamento,
                    )
                  : _AtrasoEntregaContent(
                      ocorrencia: ocorrencia,
                      enviando: _enviando,
                      onAceitarNovaData: () => _resolver('aceitar_nova_data'),
                      onCancelarPedido: _confirmarCancelamento,
                    );
            },
          ),
        ),
      ),
    );
  }
}

class _JaResolvidaState extends StatelessWidget {
  const _JaResolvidaState({required this.ocorrencia});

  final Ocorrencia ocorrencia;

  String get _mensagem {
    switch (ocorrencia.resolucao) {
      case 'substituir':
        return 'Você optou por substituir o item por um produto similar.';
      case 'remover_item':
        return 'Você optou por remover o item do pedido.';
      case 'cancelar_pedido':
        return 'O pedido foi cancelado.';
      case 'aceitar_nova_data':
        return 'Você aceitou a nova data de entrega.';
      default:
        return 'Esta pendência já foi resolvida.';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle, size: 64, color: AppColors.purple),
            const SizedBox(height: 16),
            Text(
              _mensagem,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 15, color: AppColors.textPrimary),
            ),
          ],
        ),
      ),
    );
  }
}

class _FaltaEstoqueContent extends StatelessWidget {
  const _FaltaEstoqueContent({
    required this.ocorrencia,
    required this.produtoSelecionadoId,
    required this.enviando,
    required this.onSelecionarProduto,
    required this.onSubstituir,
    required this.onRemoverItem,
    required this.onCancelarPedido,
  });

  final Ocorrencia ocorrencia;
  final String? produtoSelecionadoId;
  final bool enviando;
  final ValueChanged<String> onSelecionarProduto;
  final VoidCallback onSubstituir;
  final VoidCallback onRemoverItem;
  final VoidCallback onCancelarPedido;

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF4E5),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFFFD08A)),
            ),
            child: Row(
              children: [
                const Icon(Icons.warning_amber_rounded, color: Color(0xFFB86E00)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    'O item "${ocorrencia.produtoOriginal?.nome ?? 'do seu pedido'}" '
                    'está em falta. ${ocorrencia.motivo}',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF8A5300),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          if (ocorrencia.produtosSugeridos.isNotEmpty) ...[
            const Text(
              'Produtos similares disponíveis',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 12),
            ...ocorrencia.produtosSugeridos.map((produto) {
              final selecionado = produtoSelecionadoId == produto.id;
              return Card(
                margin: const EdgeInsets.only(bottom: 10),
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(
                    color: selecionado ? AppColors.purple : AppColors.inputBorder,
                    width: selecionado ? 1.5 : 1,
                  ),
                ),
                child: RadioListTile<String>(
                  value: produto.id,
                  groupValue: produtoSelecionadoId,
                  onChanged: (id) => onSelecionarProduto(id!),
                  activeColor: AppColors.purple,
                  title: Text(
                    produto.nome,
                    style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  subtitle: Text(
                    'R\$ ${produto.preco.toStringAsFixed(2)}',
                    style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                  ),
                ),
              );
            }),
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed:
                    (enviando || produtoSelecionadoId == null) ? null : onSubstituir,
                child: const Text('Confirmar substituição'),
              ),
            ),
            const SizedBox(height: 24),
          ] else ...[
            const Text(
              'No momento não encontramos produtos similares disponíveis.',
              style: TextStyle(fontSize: 14, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 24),
          ],
          SizedBox(
            width: double.infinity,
            child: OutlinedButton(
              onPressed: enviando ? null : onRemoverItem,
              style: OutlinedButton.styleFrom(
                foregroundColor: AppColors.purple,
                side: const BorderSide(color: AppColors.purple),
                padding: const EdgeInsets.symmetric(vertical: 16),
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              ),
              child: const Text('Remover item do pedido'),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              onPressed: enviando ? null : onCancelarPedido,
              style: TextButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('Cancelar pedido inteiro'),
            ),
          ),
        ],
      ),
    );
  }
}

class _AtrasoEntregaContent extends StatelessWidget {
  const _AtrasoEntregaContent({
    required this.ocorrencia,
    required this.enviando,
    required this.onAceitarNovaData,
    required this.onCancelarPedido,
  });

  final Ocorrencia ocorrencia;
  final bool enviando;
  final VoidCallback onAceitarNovaData;
  final VoidCallback onCancelarPedido;

  @override
  Widget build(BuildContext context) {
    final novaData = ocorrencia.novaDataSugerida;

    return SingleChildScrollView(
      padding: const EdgeInsets.all(24),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF4E5),
              borderRadius: BorderRadius.circular(14),
              border: Border.all(color: const Color(0xFFFFD08A)),
            ),
            child: Row(
              children: [
                const Icon(Icons.schedule, color: Color(0xFFB86E00)),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    ocorrencia.motivo,
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF8A5300),
                    ),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
          const Text(
            'Nova data sugerida',
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 20),
            decoration: BoxDecoration(
              color: AppColors.inputFill,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Center(
              child: Text(
                novaData != null
                    ? '${novaData.day.toString().padLeft(2, '0')}/'
                        '${novaData.month.toString().padLeft(2, '0')}/'
                        '${novaData.year}'
                    : '--/--/----',
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.w800,
                  color: AppColors.purple,
                ),
              ),
            ),
          ),
          const SizedBox(height: 32),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: enviando ? null : onAceitarNovaData,
              child: const Text('Aceitar nova data'),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            width: double.infinity,
            child: TextButton(
              onPressed: enviando ? null : onCancelarPedido,
              style: TextButton.styleFrom(foregroundColor: Colors.red),
              child: const Text('Cancelar pedido inteiro'),
            ),
          ),
        ],
      ),
    );
  }
}
