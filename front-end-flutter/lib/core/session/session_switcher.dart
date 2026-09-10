import 'package:flutter/material.dart';

import '../../features/admin/presentation/admin_dashboard_screen.dart';
import '../../features/logistics/presentation/delivery_queue_screen.dart';
import '../../features/logistics/presentation/picking_queue_screen.dart';
import 'session_manager.dart';

/// Decide para onde navegar a partir do claim `role` do access token.
///
/// Extraída de `LoginScreen._redirecionarPorPapel` para que o
/// [SessionSwitcher] reuse exatamente o mesmo roteamento pós-autenticação em
/// vez de duplicar o `switch` — login e troca de sessão levam ao mesmo lugar
/// para o mesmo papel.
Future<void> irParaTelaDoPapel(BuildContext context, String? role) async {
  switch (role) {
    case 'separador':
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const SeparadorFilaScreen()),
      );
      break;
    case 'entregador':
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const EntregadorFilaScreen()),
      );
      break;
    case 'admin':
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const AdminDashboardScreen()),
      );
      break;
    case 'student':
    default:
      Navigator.pushReplacementNamed(
        context,
        '/home',
        arguments: {'justLoggedIn': true},
      );
  }
}

/// Seletor de sessões guardadas, para trocar de papel sem redigitar senha.
///
/// RECURSO DE DEMONSTRAÇÃO — ver a docstring de [SessionManager]. O widget só
/// se desenha quando [SessionManager.habilitado] é verdadeiro E há ao menos
/// uma sessão guardada; em qualquer build normal o primeiro `if` já faz o
/// widget não renderizar nada.
class SessionSwitcher extends StatefulWidget {
  const SessionSwitcher({super.key, this.manager});

  /// Injeção só para teste; o app sempre usa o default.
  final SessionManager? manager;

  @override
  State<SessionSwitcher> createState() => _SessionSwitcherState();
}

class _SessionSwitcherState extends State<SessionSwitcher> {
  late final SessionManager _manager = widget.manager ?? SessionManager();
  late Future<List<SessaoGuardada>> _sessoesFuture;

  @override
  void initState() {
    super.initState();
    _sessoesFuture = _manager.listar();
  }

  Future<void> _trocarPara(String papel) async {
    final trocou = await _manager.ativar(papel);
    if (!trocou || !mounted) return;
    await irParaTelaDoPapel(context, papel);
  }

  @override
  Widget build(BuildContext context) {
    if (!SessionManager.habilitado) return const SizedBox.shrink();

    return FutureBuilder<List<SessaoGuardada>>(
      future: _sessoesFuture,
      builder: (context, snapshot) {
        final sessoes = snapshot.data ?? const <SessaoGuardada>[];
        if (sessoes.isEmpty) return const SizedBox.shrink();

        return Padding(
          padding: const EdgeInsets.only(top: 24),
          child: Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final sessao in sessoes)
                ActionChip(
                  avatar: const Icon(Icons.swap_horiz, size: 16),
                  label: Text('${sessao.nome} (${sessao.papel})'),
                  onPressed: () => _trocarPara(sessao.papel),
                ),
            ],
          ),
        );
      },
    );
  }
}
