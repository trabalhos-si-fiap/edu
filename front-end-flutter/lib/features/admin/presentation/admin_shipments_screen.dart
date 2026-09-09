import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show Clipboard, ClipboardData;

import '../../../core/theme/app_colors.dart';
import '../../logistics/domain/order.dart';
import '../data/admin_api.dart';
import '../domain/shipment.dart';
import 'widgets/admin_scaffold.dart';
import 'widgets/admin_widgets.dart';

/// Aba Carregamentos: cria um carregamento (`POST /shipments`, escolhendo a
/// transportadora) e atribui pedidos a ele (`POST /shipments/{id}/orders`).
/// É a tela que a apresentação usa — um admin, no aparelho, montando o lote
/// que o entregador da transportadora vai retirar.
class AdminShipmentsScreen extends StatefulWidget {
  const AdminShipmentsScreen({super.key, AdminApi? api}) : _api = api;

  final AdminApi? _api;

  @override
  State<AdminShipmentsScreen> createState() => _AdminShipmentsScreenState();
}

class _AdminShipmentsScreenState extends State<AdminShipmentsScreen> {
  late final AdminApi _api = widget._api ?? AdminApi();
  late Future<List<Shipment>> _future;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  void _carregar() {
    setState(() {
      _future = _api.fetchCarregamentos();
    });
  }

  Future<void> _novoCarregamento() async {
    final criado = await showDialog<bool>(
      context: context,
      builder: (_) => _NovoCarregamentoDialog(api: _api),
    );
    if (criado == true) _carregar();
  }

  Future<void> _adicionarPedido(Shipment carregamento) async {
    final atribuido = await showDialog<bool>(
      context: context,
      builder: (_) =>
          _AtribuirPedidoDialog(api: _api, carregamentoId: carregamento.id),
    );
    if (atribuido == true) _carregar();
  }

  @override
  Widget build(BuildContext context) {
    return AdminScaffold(
      tab: AdminTab.carregamentos,
      titulo: 'Carregamentos',
      body: RefreshIndicator(
        onRefresh: () async => _carregar(),
        child: FutureBuilder<List<Shipment>>(
          future: _future,
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: CircularProgressIndicator());
            }
            if (snapshot.hasError) {
              return ListView(
                children: [
                  const SizedBox(height: 60),
                  AdminErrorState(
                    mensagem:
                        'Erro ao carregar carregamentos:\n${snapshot.error}',
                    onRetry: _carregar,
                  ),
                ],
              );
            }
            return _ListaCarregamentos(
              api: _api,
              carregamentos: snapshot.data!,
              onNovoCarregamento: _novoCarregamento,
              onAdicionarPedido: _adicionarPedido,
            );
          },
        ),
      ),
    );
  }
}

class _ListaCarregamentos extends StatelessWidget {
  const _ListaCarregamentos({
    required this.api,
    required this.carregamentos,
    required this.onNovoCarregamento,
    required this.onAdicionarPedido,
  });

  final AdminApi api;
  final List<Shipment> carregamentos;
  final VoidCallback onNovoCarregamento;
  final void Function(Shipment) onAdicionarPedido;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 32),
      children: [
        ElevatedButton.icon(
          onPressed: onNovoCarregamento,
          icon: const Icon(Icons.add),
          label: const Text('Novo carregamento'),
        ),
        const SizedBox(height: 16),
        if (carregamentos.isEmpty)
          const _ListaVazia()
        else
          ...carregamentos.map(
            (c) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _CarregamentoCard(
                api: api,
                carregamento: c,
                onAdicionarPedido: () => onAdicionarPedido(c),
              ),
            ),
          ),
      ],
    );
  }
}

class _ListaVazia extends StatelessWidget {
  const _ListaVazia();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(vertical: 40),
      child: Text(
        'Nenhum carregamento ainda. Crie um para começar a despachar '
        'pedidos.',
        textAlign: TextAlign.center,
        style: TextStyle(color: AppColors.textSecondary, fontSize: 13),
      ),
    );
  }
}

/// Card de um carregamento: código, origem, entregador (se já logado) e um
/// toggle para conferir os pedidos já atribuídos antes de adicionar mais —
/// evita que o admin tente atribuir o mesmo pedido duas vezes às cegas.
class _CarregamentoCard extends StatefulWidget {
  const _CarregamentoCard({
    required this.api,
    required this.carregamento,
    required this.onAdicionarPedido,
  });

  final AdminApi api;
  final Shipment carregamento;
  final VoidCallback onAdicionarPedido;

  @override
  State<_CarregamentoCard> createState() => _CarregamentoCardState();
}

class _CarregamentoCardState extends State<_CarregamentoCard> {
  bool _expandido = false;
  Future<List<Pedido>>? _pedidosFuture;

  void _alternarExpandido() {
    setState(() {
      _expandido = !_expandido;
      _pedidosFuture ??= widget.api.fetchPedidosDoCarregamento(
        widget.carregamento.id,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = widget.carregamento;
    return AdminSectionCard(
      title: c.codigo,
      subtitle: c.origemRotulo,
      trailing: TextButton.icon(
        onPressed: widget.onAdicionarPedido,
        icon: const Icon(Icons.add_box_outlined, size: 18),
        label: const Text('Pedido'),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            c.entregadorNome != null
                ? 'Entregador: ${c.entregadorNome}'
                : 'Aguardando entregador logar',
            style: const TextStyle(
              fontSize: 13,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Criado em ${_formatarData(c.criadoEm)}',
            style: const TextStyle(
              fontSize: 12,
              color: AppColors.textSecondary,
            ),
          ),
          const SizedBox(height: 8),
          InkWell(
            onTap: _alternarExpandido,
            child: Text(
              _expandido ? 'Ocultar pedidos' : 'Ver pedidos',
              style: const TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.w700,
                color: AppColors.purple,
              ),
            ),
          ),
          if (_expandido) _PedidosDoCarregamento(future: _pedidosFuture!),
        ],
      ),
    );
  }
}

class _PedidosDoCarregamento extends StatelessWidget {
  const _PedidosDoCarregamento({required this.future});

  final Future<List<Pedido>> future;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 8),
      child: FutureBuilder<List<Pedido>>(
        future: future,
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Padding(
              padding: EdgeInsets.symmetric(vertical: 8),
              child: SizedBox(
                width: 16,
                height: 16,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            );
          }
          final pedidos = snapshot.data!;
          if (pedidos.isEmpty) {
            return const Text(
              'Nenhum pedido atribuído ainda.',
              style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: pedidos
                .map(
                  (p) => Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Text(
                      '${p.idCurto} · ${p.status.label}',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
                )
                .toList(),
          );
        },
      ),
    );
  }
}

/// Cria o carregamento em duas etapas dentro do mesmo diálogo: escolher a
/// transportadora, depois mostrar código+senha uma vez. Duas telas num só
/// `showDialog` — mais simples de testar do que encadear dois diálogos.
class _NovoCarregamentoDialog extends StatefulWidget {
  const _NovoCarregamentoDialog({required this.api});

  final AdminApi api;

  @override
  State<_NovoCarregamentoDialog> createState() =>
      _NovoCarregamentoDialogState();
}

class _NovoCarregamentoDialogState extends State<_NovoCarregamentoDialog> {
  late final Future<List<Carrier>> _transportadorasFuture;

  Carrier? _selecionada;
  ShipmentCriado? _criado;
  String? _erro;
  bool _criando = false;

  @override
  void initState() {
    super.initState();
    _transportadorasFuture = widget.api.fetchTransportadoras();
    // Pré-seleciona a primeira: a lista de transportadoras costuma ser
    // pequena, e evitar uma interação a mais no seletor importa mais aqui
    // (é a tela que a apresentação usa ao vivo) do que forçar uma escolha
    // explícita quando há só uma opção. `setState` é obrigatório aqui —
    // sem ele o botão "Criar" (construído no `build` deste State, não no
    // do `FutureBuilder` abaixo) continuava lendo o `_selecionada` antigo
    // e ficava permanentemente desabilitado.
    _transportadorasFuture.then((lista) {
      if (!mounted || lista.isEmpty) return;
      setState(() => _selecionada = lista.first);
    });
  }

  Future<void> _criar() async {
    final transportadora = _selecionada;
    if (transportadora == null) return;
    setState(() {
      _criando = true;
      _erro = null;
    });
    try {
      final criado = await widget.api.criarCarregamento(transportadora.id);
      if (!mounted) return;
      setState(() {
        _criado = criado;
        _criando = false;
      });
    } on AdminApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _erro = e.message;
        _criando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final criado = _criado;
    if (criado != null) {
      return _SenhaDialog(
        criado: criado,
        onFechar: () => Navigator.pop(context, true),
      );
    }
    return AlertDialog(
      title: const Text('Novo carregamento'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _SeletorTransportadora(
              future: _transportadorasFuture,
              selecionada: _selecionada,
              onChanged: (v) => setState(() => _selecionada = v),
            ),
            if (_erro != null) ...[
              const SizedBox(height: 8),
              Text(_erro!, style: const TextStyle(color: AppColors.danger)),
            ],
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        ElevatedButton(
          onPressed: _selecionada == null || _criando ? null : _criar,
          child: _criando
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Criar'),
        ),
      ],
    );
  }
}

class _SeletorTransportadora extends StatelessWidget {
  const _SeletorTransportadora({
    required this.future,
    required this.selecionada,
    required this.onChanged,
  });

  final Future<List<Carrier>> future;
  final Carrier? selecionada;
  final ValueChanged<Carrier?> onChanged;

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<Carrier>>(
      future: future,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const Padding(
            padding: EdgeInsets.symmetric(vertical: 16),
            child: Center(child: CircularProgressIndicator()),
          );
        }
        final transportadoras = snapshot.data!;
        return DropdownButtonFormField<Carrier>(
          // ignore: deprecated_member_use
          value: selecionada,
          decoration: const InputDecoration(labelText: 'Transportadora'),
          items: transportadoras
              .map((t) => DropdownMenuItem(value: t, child: Text(t.name)))
              .toList(),
          onChanged: onChanged,
        );
      },
    );
  }
}

/// O cartão de senha da task: mostrado UMA vez, nunca persistido pelo app
/// (nem storage, nem log — só este estado efêmero do diálogo, que some ao
/// fechar). A frase de aviso é a mesma do brief da task, verbatim.
class _SenhaDialog extends StatelessWidget {
  const _SenhaDialog({required this.criado, required this.onFechar});

  final ShipmentCriado criado;
  final VoidCallback onFechar;

  void _copiar(BuildContext context, String valor, String rotulo) {
    Clipboard.setData(ClipboardData(text: valor));
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text('$rotulo copiado')));
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Carregamento criado'),
      content: SizedBox(
        width: double.maxFinite,
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _CampoCopiavel(
              rotulo: 'Código',
              valor: criado.codigo,
              onCopiar: () => _copiar(context, criado.codigo, 'Código'),
            ),
            const SizedBox(height: 12),
            _CampoCopiavel(
              rotulo: 'Senha',
              valor: criado.senha,
              onCopiar: () => _copiar(context, criado.senha, 'Senha'),
            ),
            const SizedBox(height: 16),
            const Text(
              'A transportadora também recebeu estes dados por e-mail. '
              'Esta senha não pode ser consultada depois.',
              style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
      actions: [
        ElevatedButton(onPressed: onFechar, child: const Text('Fechar')),
      ],
    );
  }
}

class _CampoCopiavel extends StatelessWidget {
  const _CampoCopiavel({
    required this.rotulo,
    required this.valor,
    required this.onCopiar,
  });

  final String rotulo;
  final String valor;
  final VoidCallback onCopiar;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      decoration: BoxDecoration(
        color: AppColors.inputFill,
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: AppColors.inputBorder),
      ),
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  rotulo,
                  style: const TextStyle(
                    fontSize: 11,
                    color: AppColors.textSecondary,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                Text(
                  valor,
                  style: const TextStyle(
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    color: AppColors.textPrimary,
                  ),
                ),
              ],
            ),
          ),
          IconButton(
            onPressed: onCopiar,
            icon: const Icon(Icons.copy, size: 18),
            tooltip: 'Copiar $rotulo',
          ),
        ],
      ),
    );
  }
}

/// Atribui um pedido (por ID) ao carregamento. O 409 de origem
/// divergente/pedido já carregado chega em [AdminApiException.message] com
/// a frase do servidor, e é isso — só isso — que este diálogo mostra.
class _AtribuirPedidoDialog extends StatefulWidget {
  const _AtribuirPedidoDialog({
    required this.api,
    required this.carregamentoId,
  });

  final AdminApi api;
  final int carregamentoId;

  @override
  State<_AtribuirPedidoDialog> createState() => _AtribuirPedidoDialogState();
}

class _AtribuirPedidoDialogState extends State<_AtribuirPedidoDialog> {
  final _controller = TextEditingController();
  String? _erro;
  bool _enviando = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _atribuir() async {
    final pedidoId = _controller.text.trim();
    if (pedidoId.isEmpty) return;
    setState(() {
      _enviando = true;
      _erro = null;
    });
    try {
      await widget.api.atribuirPedido(
        carregamentoId: widget.carregamentoId,
        pedidoId: pedidoId,
      );
      if (!mounted) return;
      Navigator.pop(context, true);
    } on AdminApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _erro = e.message;
        _enviando = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Adicionar pedido ao carregamento'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          TextField(
            controller: _controller,
            decoration: const InputDecoration(labelText: 'ID do pedido'),
          ),
          if (_erro != null) ...[
            const SizedBox(height: 8),
            Text(
              _erro!,
              style: const TextStyle(color: AppColors.danger, fontSize: 13),
            ),
          ],
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancelar'),
        ),
        ElevatedButton(
          onPressed: _enviando ? null : _atribuir,
          child: _enviando
              ? const SizedBox(
                  width: 16,
                  height: 16,
                  child: CircularProgressIndicator(strokeWidth: 2),
                )
              : const Text('Adicionar'),
        ),
      ],
    );
  }
}

String _formatarData(DateTime d) {
  final dia = d.day.toString().padLeft(2, '0');
  final mes = d.month.toString().padLeft(2, '0');
  final hora = d.hour.toString().padLeft(2, '0');
  final min = d.minute.toString().padLeft(2, '0');
  return '$dia/$mes $hora:$min';
}
