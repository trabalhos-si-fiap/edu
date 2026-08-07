import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../../core/theme/app_colors.dart';
import '../../components/nav_bar.dart';
import '../domain/support_message.dart';
import 'support_provider.dart';

/// Entrada de rota do chat de suporte. Cria o [SupportProvider] e dispara o
/// carregamento inicial; a UI vive em [SupportView] para facilitar testes.
class SupportScreen extends StatelessWidget {
  const SupportScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return ChangeNotifierProvider(
      create: (_) => SupportProvider()..load(),
      child: const SupportView(),
    );
  }
}

/// Corpo do chat de suporte. Espera um [SupportProvider] já disponível.
class SupportView extends StatelessWidget {
  const SupportView({super.key});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        resizeToAvoidBottomInset: true,
        appBar: AppBar(
          backgroundColor: Colors.transparent,
          elevation: 0,
          centerTitle: true,
          leading: IconButton(
            onPressed: () => Navigator.maybePop(context),
            icon: const Icon(Icons.arrow_back, color: AppColors.textPrimary),
          ),
          title: const Text(
            'Suporte de Pedidos',
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.w800,
              color: AppColors.textPrimary,
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(
          mode: NavBarMode.store,
          currentIndex: 2,
        ),
        body: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: Consumer<SupportProvider>(
              builder: (context, provider, _) {
                switch (provider.state) {
                  case SupportViewState.loading:
                    return const Center(
                      child: CircularProgressIndicator(color: AppColors.purple),
                    );
                  case SupportViewState.error:
                    return _ErrorView(
                      message: provider.errorMessage ?? 'Erro desconhecido.',
                      onRetry: provider.load,
                    );
                  case SupportViewState.success:
                    return _ChatPanel(provider: provider);
                }
              },
            ),
          ),
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Text(
            'Não foi possível carregar o chat.',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: AppColors.textPrimary,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            message,
            textAlign: TextAlign.center,
            style: const TextStyle(color: AppColors.textSecondary),
          ),
          const SizedBox(height: 16),
          TextButton(
            onPressed: onRetry,
            child: const Text(
              'Tentar novamente',
              style: TextStyle(color: AppColors.purple),
            ),
          ),
        ],
      ),
    );
  }
}

class _ChatPanel extends StatelessWidget {
  const _ChatPanel({required this.provider});

  final SupportProvider provider;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: Container(
            width: double.infinity,
            decoration: BoxDecoration(
              color: AppColors.inputFill,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.04),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
            ),
            child: provider.messages.isEmpty
                ? const _EmptyState()
                : _MessageList(messages: provider.messages),
          ),
        ),
        const SizedBox(height: 8),
        _InputBar(
          sending: provider.sending,
          onSend: provider.send,
        ),
        const _Disclaimer(),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 56,
              height: 56,
              decoration: const BoxDecoration(
                color: AppColors.background,
                shape: BoxShape.circle,
              ),
              child: const Icon(
                Icons.support_agent,
                color: AppColors.white,
              ),
            ),
            const SizedBox(height: 12),
            const Text(
              'Olá! Como posso ajudar com seus pedidos hoje?',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppColors.textSecondary),
            ),
          ],
        ),
      ),
    );
  }
}

class _MessageList extends StatefulWidget {
  const _MessageList({required this.messages});

  final List<SupportMessage> messages;

  @override
  State<_MessageList> createState() => _MessageListState();
}

class _MessageListState extends State<_MessageList> {
  final _controller = ScrollController();

  void _jumpToEnd() {
    if (!_controller.hasClients) return;
    _controller.jumpTo(_controller.position.maxScrollExtent);
  }

  @override
  void didUpdateWidget(covariant _MessageList oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (widget.messages.length != oldWidget.messages.length) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _jumpToEnd());
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView.separated(
      controller: _controller,
      padding: const EdgeInsets.all(16),
      itemCount: widget.messages.length,
      separatorBuilder: (context, index) => const SizedBox(height: 12),
      itemBuilder: (_, i) => _MessageBubble(message: widget.messages[i]),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.message});

  final SupportMessage message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.sender == SupportSender.user;
    final time = formatMessageTime(message.createdAt);

    final bubble = Container(
      constraints: const BoxConstraints(maxWidth: 280),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 4,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!isUser) ...[
            const Text(
              'SUPORTE EDU',
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.bold,
                color: AppColors.purple,
              ),
            ),
            const SizedBox(height: 4),
          ],
          Text(
            message.body,
            style: const TextStyle(
              fontSize: 14,
              color: AppColors.textPrimary,
            ),
          ),
          if (time.isNotEmpty) ...[
            const SizedBox(height: 4),
            Align(
              alignment: Alignment.centerRight,
              child: Text(
                time,
                style: const TextStyle(
                  fontSize: 11,
                  color: AppColors.textSecondary,
                ),
              ),
            ),
          ],
        ],
      ),
    );

    return Row(
      mainAxisAlignment:
          isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (!isUser) ...[
          Container(
            width: 32,
            height: 32,
            decoration: const BoxDecoration(
              color: AppColors.primary,
              shape: BoxShape.circle,
            ),
            child: const Icon(
              Icons.support_agent,
              size: 18,
              color: AppColors.white,
            ),
          ),
          const SizedBox(width: 8),
        ],
        Flexible(child: bubble),
      ],
    );
  }
}

class _InputBar extends StatefulWidget {
  const _InputBar({required this.sending, required this.onSend});

  final bool sending;
  final ValueChanged<String> onSend;

  @override
  State<_InputBar> createState() => _InputBarState();
}

class _InputBarState extends State<_InputBar> {
  final _controller = TextEditingController();

  bool get _canSend =>
      _controller.text.trim().isNotEmpty && !widget.sending;

  void _submit() {
    if (!_canSend) return;
    final text = _controller.text;
    _controller.clear();
    widget.onSend(text);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.06),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: TextField(
              controller: _controller,
              enabled: !widget.sending,
              minLines: 1,
              maxLines: 4,
              onChanged: (_) => setState(() {}),
              decoration: const InputDecoration(
                hintText: 'Escreva sua mensagem aqui...',
                hintStyle: TextStyle(color: AppColors.textSecondary),
                border: InputBorder.none,
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 12, vertical: 14),
              ),
              style: const TextStyle(color: AppColors.textPrimary),
            ),
          ),
          const SizedBox(width: 8),
          GestureDetector(
            onTap: _canSend ? _submit : null,
            child: Container(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: _canSend
                    ? AppColors.primary
                    : AppColors.primary.withValues(alpha: 0.4),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.send, color: AppColors.white, size: 20),
            ),
          ),
        ],
      ),
    );
  }
}

class _Disclaimer extends StatelessWidget {
  const _Disclaimer();

  @override
  Widget build(BuildContext context) {
    return const Padding(
      padding: EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Text(
        'Mentor Edu pode cometer erros, verifique informações importantes.',
        textAlign: TextAlign.center,
        style: TextStyle(fontSize: 12, color: AppColors.textSecondary),
      ),
    );
  }
}
