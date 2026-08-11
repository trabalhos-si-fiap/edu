import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../data/demo_itens.dart';
import '../data/logistics_api.dart';
import '../domain/occurrence.dart';
import '../domain/order.dart';

/// Tela de picking: o separador confere item a item do pedido antes de
/// finalizar. O checklist é controle local (UX de conferência); o backend
/// só registra a transição de estado do pedido como um todo no MVP.
///
/// Se um item estiver em falta no estoque, o separador pode reportar a
/// ocorrência aqui mesmo — o backend sugere produtos similares e notifica
/// o aluno para decidir (substituir, remover item ou cancelar o pedido).
/// Enquanto essa decisão não chega, a separação não pode ser finalizada.
class SeparadorPickingScreen extends StatefulWidget {
  const SeparadorPickingScreen({super.key, required this.pedido});

  final Pedido pedido;

  @override
  State<SeparadorPickingScreen> createState() => _SeparadorPickingScreenState();
}

class _SeparadorPickingScreenState extends State<SeparadorPickingScreen> {
  final _api = LogisticsApi();
  late Set<int> _itensConferidos;
  bool _separacaoIniciada = false;
  bool _carregando = false;
  String? _erro;

  List<Ocorrencia> _ocorrenciasAbertas = [];
  bool _carregandoOcorrencias = true;

  @override
  void initState() {
    super.initState();
    _itensConferidos = {};
    _separacaoIniciada = widget.pedido.status == StatusPedido.emSeparacao;
    _carregarOcorrencias();
  }

  Future<void> _carregarOcorrencias() async {
    setState(() => _carregandoOcorrencias = true);
    try {
      final ocorrencias = await _api.fetchOcorrenciasPedido(
        widget.pedido.id,
        apenasAbertas: true,
      );
      if (mounted) setState(() => _ocorrenciasAbertas = ocorrencias);
    } on LogisticsException {
      // Silencioso: se falhar, o backend ainda valida no finalizar.
    } finally {
      if (mounted) setState(() => _carregandoOcorrencias = false);
    }
  }

  bool _temOcorrenciaAbertaPara(String produtoId) {
    return _ocorrenciasAbertas.any(
      (o) => o.tipo == 'FALTA_ESTOQUE' && o.produtoId == produtoId,
    );
  }

  bool get _temOcorrenciaAbertaGeral => _ocorrenciasAbertas.isNotEmpty;

  /// Itens que a tela exibe e confere. Normalmente são os do pedido; numa
  /// build de demonstração (`--dart-define=DEMO_ITENS_MOCK=true`) um pedido
  /// que chega sem itens recebe a lista de vitrine — ver
  /// `data/demo_itens.dart`. Fora dessa build isto é exatamente
  /// `widget.pedido.itens`.
  List<PedidoItem> get _itens => itensParaExibir(widget.pedido.itens);

  bool get _todosConferidos =>
      _itens.isNotEmpty && _itensConferidos.length == _itens.length;

  Future<void> _iniciarSeparacao() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      await _api.iniciarSeparacao(widget.pedido.id);
      if (mounted) setState(() => _separacaoIniciada = true);
    } on LogisticsException catch (e) {
      if (mounted) setState(() => _erro = e.message);
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  Future<void> _finalizarSeparacao() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      await _api.finalizarSeparacao(widget.pedido.id);
      if (mounted) Navigator.pop(context, true);
    } on LogisticsException catch (e) {
      if (mounted) setState(() => _erro = e.message);
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  Future<void> _abrirDialogoFaltaEstoque(String produtoId, String nomeProduto) async {
    final motivoController = TextEditingController();

    final confirmar = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Text('Reportar falta de estoque'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(nomeProduto, style: const TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 12),
            const Text(
              'O aluno será notificado e poderá escolher um produto '
              'similar, remover o item ou cancelar o pedido.',
              style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: motivoController,
              maxLines: 2,
              decoration: const InputDecoration(
                labelText: 'Motivo (opcional)',
                hintText: 'Ex: sem unidades neste fornecedor',
                border: OutlineInputBorder(),
              ),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancelar'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Reportar'),
          ),
        ],
      ),
    );

    if (confirmar != true) return;

    setState(() => _carregando = true);
    try {
      await _api.reportarFaltaEstoque(
        pedidoId: widget.pedido.id,
        produtoId: produtoId,
        motivo: motivoController.text.trim().isEmpty
            ? 'Item sem estoque disponível'
            : motivoController.text.trim(),
      );
      await _carregarOcorrencias();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Ocorrência registrada. O aluno foi notificado.')),
        );
      }
    } on LogisticsException catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.message)));
      }
    } finally {
      if (mounted) setState(() => _carregando = false);
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
          title: Text(
            'Pedido #${widget.pedido.idCurto}',
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
                      _EnderecoCard(endereco: widget.pedido.enderecoEntrega),
                      if (_temOcorrenciaAbertaGeral) ...[
                        const SizedBox(height: 16),
                        _AvisoOcorrenciaAberta(quantidade: _ocorrenciasAbertas.length),
                      ],
                      const SizedBox(height: 24),
                      const Text(
                        'Itens do pedido',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          color: AppColors.textPrimary,
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        _separacaoIniciada
                            ? 'Marque cada item conforme for separando.'
                            : 'Inicie a separação para começar a conferência.',
                        style: const TextStyle(fontSize: 13, color: AppColors.textSecondary),
                      ),
                      const SizedBox(height: 16),
                      if (_itens.isEmpty)
                        const Padding(
                          padding: EdgeInsets.symmetric(vertical: 12),
                          child: Text(
                            'Este pedido não retornou itens detalhados '
                            '(ver STATUS.md — Commerce Service precisa expor '
                            'itens com nome do produto).',
                            style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
                          ),
                        )
                      else
                        ..._itens.asMap().entries.map((entry) {
                          final index = entry.key;
                          final item = entry.value;
                          final conferido = _itensConferidos.contains(index);
                          final emFalta = _temOcorrenciaAbertaPara(item.produtoId);
                          final nome = item.nomeProduto ?? 'Produto #${item.produtoId}';

                          return _ItemChecklistTile(
                            nome: nome,
                            quantidade: item.quantidade,
                            conferido: conferido,
                            habilitado: _separacaoIniciada && !emFalta,
                            emFalta: emFalta,
                            onChanged: (valor) {
                              setState(() {
                                if (valor) {
                                  _itensConferidos.add(index);
                                } else {
                                  _itensConferidos.remove(index);
                                }
                              });
                            },
                            onReportarFalta: _separacaoIniciada && !emFalta
                                ? () => _abrirDialogoFaltaEstoque(item.produtoId, nome)
                                : null,
                          );
                        }),
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
                  child: ElevatedButton(
                    onPressed: (_carregando || _carregandoOcorrencias)
                        ? null
                        : (_separacaoIniciada
                            ? ((_todosConferidos && !_temOcorrenciaAbertaGeral)
                                ? _finalizarSeparacao
                                : null)
                            : _iniciarSeparacao),
                    child: _carregando
                        ? const SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : Text(
                            _separacaoIniciada
                                ? (_temOcorrenciaAbertaGeral
                                    ? 'Aguardando decisão do aluno'
                                    : 'Finalizar Separação')
                                : 'Iniciar Separação',
                          ),
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

class _AvisoOcorrenciaAberta extends StatelessWidget {
  const _AvisoOcorrenciaAberta({required this.quantidade});

  final int quantidade;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF4E5),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFFFFD08A)),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber_rounded, color: Color(0xFFB86E00), size: 22),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              quantidade == 1
                  ? 'Há 1 ocorrência aguardando decisão do aluno.'
                  : 'Há $quantidade ocorrências aguardando decisão do aluno.',
              style: const TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Color(0xFF8A5300),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _EnderecoCard extends StatelessWidget {
  const _EnderecoCard({required this.endereco});

  final String endereco;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          const Icon(Icons.place_outlined, color: AppColors.purple, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              endereco,
              style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: AppColors.textPrimary,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _ItemChecklistTile extends StatelessWidget {
  const _ItemChecklistTile({
    required this.nome,
    required this.quantidade,
    required this.conferido,
    required this.habilitado,
    required this.emFalta,
    required this.onChanged,
    required this.onReportarFalta,
  });

  final String nome;
  final int quantidade;
  final bool conferido;
  final bool habilitado;
  final bool emFalta;
  final ValueChanged<bool> onChanged;
  final VoidCallback? onReportarFalta;

  @override
  Widget build(BuildContext context) {
    return Opacity(
      opacity: habilitado || emFalta ? 1.0 : 0.5,
      child: Card(
        margin: const EdgeInsets.only(bottom: 10),
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(12),
          side: BorderSide(
            color: emFalta
                ? const Color(0xFFFFD08A)
                : (conferido ? AppColors.purple : AppColors.inputBorder),
            width: conferido || emFalta ? 1.5 : 1,
          ),
        ),
        child: Column(
          children: [
            CheckboxListTile(
              value: conferido,
              onChanged: habilitado ? (v) => onChanged(v ?? false) : null,
              controlAffinity: ListTileControlAffinity.leading,
              activeColor: AppColors.purple,
              title: Text(
                nome,
                style: const TextStyle(
                  fontSize: 15,
                  fontWeight: FontWeight.w600,
                  color: AppColors.textPrimary,
                ),
              ),
              subtitle: Text(
                emFalta
                    ? 'Aguardando decisão do aluno sobre este item'
                    : 'Quantidade: $quantidade',
                style: TextStyle(
                  fontSize: 13,
                  color: emFalta ? const Color(0xFFB86E00) : AppColors.textSecondary,
                  fontWeight: emFalta ? FontWeight.w600 : FontWeight.normal,
                ),
              ),
            ),
            if (onReportarFalta != null)
              Padding(
                padding: const EdgeInsets.only(left: 8, right: 8, bottom: 8),
                child: Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: onReportarFalta,
                    icon: const Icon(Icons.report_problem_outlined, size: 16),
                    label: const Text('Reportar falta de estoque'),
                    style: TextButton.styleFrom(
                      foregroundColor: const Color(0xFFB86E00),
                      textStyle: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}
