import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/app_colors.dart';
import '../../auth/data/auth_api.dart';
import '../../components/nav_bar.dart';
import '../domain/quiz_models.dart';

/// Tela de resultado do diagnóstico — substitui o card fixo
/// "X/Y acertos" por tudo que `POST /diagnostic/answer` de fato devolve:
/// domínio calculado por subtema, ação recomendada pro tema, conteúdo
/// sugerido e a mensagem do tutor gerada por IA.
class ReportScreen extends StatefulWidget {
  const ReportScreen({
    super.key,
    required this.temaNome,
    required this.resultado,
    required this.totalTime,
  });

  final String temaNome;
  final DiagnosticoResultado resultado;
  final Duration totalTime;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  final _authApi = AuthApi();
  String? _firstName;

  @override
  void initState() {
    super.initState();
    _loadName();
  }

  Future<void> _loadName() async {
    final name = await _authApi.currentDisplayName();
    if (!mounted || name == null || name.isEmpty) return;
    setState(() => _firstName = name.split(' ').first);
  }

  @override
  Widget build(BuildContext context) {
    final r = widget.resultado;
    final greeting = _firstName == null || _firstName!.isEmpty
        ? 'Excelente progresso!'
        : 'Excelente progresso, $_firstName!';

    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: AppBar(
          backgroundColor: Colors.white,
          elevation: 0,
          title: const Row(
            children: [
              Icon(Icons.check_circle, color: AppColors.purple),
              SizedBox(width: 8),
              Text(
                'QUESTIONÁRIO CONCLUÍDO',
                style: TextStyle(
                  color: AppColors.purple,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
        ),
        body: SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                const SizedBox(height: 12),
                Text(
                  greeting,
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                ),
                const SizedBox(height: 8),
                Text(
                  'Você completou o questionário sobre ${widget.temaNome}. '
                  'Seus dados já foram analisados pela nossa IA.',
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 16),
                ),
                const SizedBox(height: 24),

                _CardDominio(dominioTema: r.dominioTema),
                const SizedBox(height: 16),

                _CardAcaoRecomendada(resultado: r),
                const SizedBox(height: 16),

                Card(
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: ListTile(
                    leading: const Icon(Icons.access_time, color: AppColors.purple),
                    title: Text(
                      'Tempo total levado: ${widget.totalTime.inMinutes} min',
                    ),
                  ),
                ),
                const SizedBox(height: 16),

                if (r.subtemasAvaliados.isNotEmpty) ...[
                  _CardDesempenhoPorSubtema(subtemas: r.subtemasAvaliados),
                  const SizedBox(height: 16),
                ],

                // Mensagem do tutor, gerada por IA a partir do resultado já
                // calculado acima (nunca influencia domínio/ação, só
                // reescreve em tom natural) — ver
                // learning-service/app/services/tutor_llm.py.
                Card(
                  color: AppColors.purple,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.auto_awesome, color: Colors.white),
                            SizedBox(width: 8),
                            Text(
                              'Mensagem do seu tutor IA',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          r.mensagemTutor,
                          style: const TextStyle(color: Colors.white, fontSize: 15, height: 1.4),
                        ),
                      ],
                    ),
                  ),
                ),

                if (r.recomendacoesConteudo.isNotEmpty) ...[
                  const SizedBox(height: 16),
                  _CardRecomendacoesConteudo(recomendacoes: r.recomendacoesConteudo),
                ],

                const SizedBox(height: 24),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppColors.purple,
                    minimumSize: const Size(double.infinity, 48),
                  ),
                  onPressed: () => Navigator.pushReplacementNamed(context, '/home'),
                  child: const Text('Finalizar simulado'),
                ),
              ],
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 1),
      ),
    );
  }
}

class _CardDominio extends StatelessWidget {
  const _CardDominio({required this.dominioTema});

  final double dominioTema;

  @override
  Widget build(BuildContext context) {
    final percentual = (dominioTema * 100).clamp(0, 100);
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            SizedBox(
              height: 120,
              width: 120,
              child: CircularProgressIndicator(
                value: dominioTema.clamp(0, 1),
                strokeWidth: 12,
                color: AppColors.purple,
                backgroundColor: Colors.grey[200],
              ),
            ),
            const SizedBox(height: 16),
            Text(
              '${percentual.toStringAsFixed(0)}%',
              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            const Text('Domínio do tema', style: TextStyle(fontSize: 16)),
          ],
        ),
      ),
    );
  }
}

class _CardAcaoRecomendada extends StatelessWidget {
  const _CardAcaoRecomendada({required this.resultado});

  final DiagnosticoResultado resultado;

  @override
  Widget build(BuildContext context) {
    final (icone, cor, titulo, descricao) = switch (resultado.acao) {
      'avancar' => (
        Icons.trending_up_rounded,
        AppColors.success,
        'Você pode avançar!',
        resultado.temaRecomendado != null
            ? 'Próximo tema sugerido: ${resultado.temaRecomendado!.nome}'
            : 'Você concluiu a trilha desta matéria até aqui.',
      ),
      'retroceder' => (
        Icons.replay_rounded,
        AppColors.danger,
        'Vale revisar a base primeiro',
        resultado.temaRecomendado != null
            ? 'Tema recomendado antes de continuar: ${resultado.temaRecomendado!.nome}'
            : 'Reforce os conceitos deste tema antes de seguir.',
      ),
      _ => (
        Icons.menu_book_rounded,
        AppColors.purple,
        'Continue estudando este tema',
        'Ainda há pontos a reforçar antes de avançar.',
      ),
    };

    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(icone, color: cor, size: 32),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    titulo,
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 2),
                  Text(descricao, style: const TextStyle(fontSize: 13, color: AppColors.textSecondary)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _CardDesempenhoPorSubtema extends StatelessWidget {
  const _CardDesempenhoPorSubtema({required this.subtemas});

  final List<SubtemaAvaliado> subtemas;

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Desempenho por subtema',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            ...subtemas.map((s) => _LinhaSubtema(subtema: s)),
          ],
        ),
      ),
    );
  }
}

class _LinhaSubtema extends StatelessWidget {
  const _LinhaSubtema({required this.subtema});

  final SubtemaAvaliado subtema;

  @override
  Widget build(BuildContext context) {
    final (label, cor) = switch (subtema.classificacao) {
      'dominado' => ('Dominado', AppColors.success),
      'revisar' => ('Revisar', AppColors.purple),
      _ => ('Começar do zero', AppColors.danger),
    };
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          Expanded(
            child: Text(subtema.nome, style: const TextStyle(fontSize: 14)),
          ),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: cor.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(20),
            ),
            child: Text(
              '$label · ${(subtema.dominio * 100).toStringAsFixed(0)}%',
              style: TextStyle(color: cor, fontSize: 11, fontWeight: FontWeight.w700),
            ),
          ),
        ],
      ),
    );
  }
}

class _CardRecomendacoesConteudo extends StatelessWidget {
  const _CardRecomendacoesConteudo({required this.recomendacoes});

  final List<RecomendacaoConteudo> recomendacoes;

  @override
  Widget build(BuildContext context) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Row(
              children: [
                Icon(Icons.lightbulb, color: AppColors.purple),
                SizedBox(width: 8),
                Text(
                  'Recomendações de estudo',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...recomendacoes.map((rec) => _RecomendacaoCard(recomendacao: rec)),
          ],
        ),
      ),
    );
  }
}

class _RecomendacaoCard extends StatelessWidget {
  const _RecomendacaoCard({required this.recomendacao});

  final RecomendacaoConteudo recomendacao;

  @override
  Widget build(BuildContext context) {
    final motivoLabel = recomendacao.motivo == 'estudar_do_zero'
        ? 'Comece do zero'
        : 'Revise este conteúdo';

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 8),
      color: AppColors.inputFill,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              recomendacao.nome,
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
            ),
            const SizedBox(height: 4),
            Text(motivoLabel, style: const TextStyle(fontSize: 14)),
            if (recomendacao.videoUrl != null) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: recomendacao.videoUrl!));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Link do vídeo copiado')),
                  );
                },
                icon: const Icon(Icons.play_circle_outline, size: 18),
                label: const Text('Copiar link do vídeo'),
              ),
            ],
            if (recomendacao.subtemasRelacionados.isNotEmpty) ...[
              const SizedBox(height: 8),
              const Text(
                'Conteúdo relacionado:',
                style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600),
              ),
              const SizedBox(height: 4),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: recomendacao.subtemasRelacionados
                    .map(
                      (rel) => Chip(
                        label: Text(rel.nome, style: const TextStyle(fontSize: 12)),
                        backgroundColor: AppColors.purpleSoft,
                        materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                      ),
                    )
                    .toList(),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
