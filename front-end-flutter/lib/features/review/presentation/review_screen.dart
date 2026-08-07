import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../../core/theme/app_colors.dart';
import '../../../features/components/top_bar.dart';
import '../../components/nav_bar.dart';
import '../data/review_api.dart';
import '../domain/review.dart';

/// Tela "Revisão" — GET /reviews/today. Lista os subtemas com repetição
/// espaçada (SM-2) vencida hoje. Cada subtema aqui já passou por um
/// diagnóstico em algum tema (ver features/quiz) — esta tela só mostra o
/// que está devido revisar, sem reabrir o questionário completo do tema
/// (o backend não expõe qual tema um subtema pertence neste endpoint).
class ReviewScreen extends StatefulWidget {
  const ReviewScreen({super.key});

  @override
  State<ReviewScreen> createState() => _ReviewScreenState();
}

class _ReviewScreenState extends State<ReviewScreen> {
  final _api = ReviewApi();
  late Future<List<Review>> _revisoesFuture;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  void _carregar() {
    setState(() {
      _revisoesFuture = _api.fetchReviewsToday();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: const TopBar(),
        body: SafeArea(
          child: RefreshIndicator(
            onRefresh: () async => _carregar(),
            child: FutureBuilder<List<Review>>(
              future: _revisoesFuture,
              builder: (context, snapshot) {
                return CustomScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  slivers: [
                    SliverPadding(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 0),
                      sliver: SliverToBoxAdapter(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const SizedBox(height: 18),
                            const Text(
                              'Revisão de hoje',
                              style: TextStyle(
                                fontSize: 28,
                                fontWeight: FontWeight.w800,
                                color: AppColors.textPrimary,
                                height: 1.2,
                              ),
                            ),
                            const SizedBox(height: 4),
                            const Text(
                              'Conteúdos que você já estudou e estão no '
                              'momento certo de revisar, segundo nosso '
                              'algoritmo de repetição espaçada.',
                              style: TextStyle(
                                fontSize: 14,
                                color: AppColors.textSecondary,
                              ),
                            ),
                            const SizedBox(height: 24),
                          ],
                        ),
                      ),
                    ),
                    _buildConteudo(snapshot),
                    const SliverToBoxAdapter(child: SizedBox(height: 24)),
                  ],
                );
              },
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 2),
      ),
    );
  }

  Widget _buildConteudo(AsyncSnapshot<List<Review>> snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const SliverToBoxAdapter(
        child: Padding(
          padding: EdgeInsets.symmetric(vertical: 60),
          child: Center(child: CircularProgressIndicator()),
        ),
      );
    }
    if (snapshot.hasError) {
      return SliverToBoxAdapter(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 40),
          child: Column(
            children: [
              const Icon(Icons.error_outline, size: 40, color: AppColors.textSecondary),
              const SizedBox(height: 12),
              Text(
                'Não foi possível carregar suas revisões.\n${snapshot.error}',
                textAlign: TextAlign.center,
                style: const TextStyle(color: AppColors.textSecondary),
              ),
              const SizedBox(height: 16),
              OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
            ],
          ),
        ),
      );
    }
    final revisoes = snapshot.data ?? const [];
    if (revisoes.isEmpty) {
      return const SliverToBoxAdapter(
        child: Padding(
          padding: EdgeInsets.symmetric(horizontal: 20, vertical: 40),
          child: Column(
            children: [
              Icon(Icons.celebration_outlined, size: 48, color: AppColors.purple),
              SizedBox(height: 12),
              Text(
                'Nenhuma revisão pendente por hoje!',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 16, fontWeight: FontWeight.w700),
              ),
              SizedBox(height: 4),
              Text(
                'Volte amanhã ou faça um novo diagnóstico no Quiz.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 13, color: AppColors.textSecondary),
              ),
            ],
          ),
        ),
      );
    }
    return SliverPadding(
      padding: const EdgeInsets.symmetric(horizontal: 20),
      sliver: SliverList.separated(
        itemCount: revisoes.length,
        separatorBuilder: (_, _) => const SizedBox(height: 12),
        itemBuilder: (context, index) => _RevisaoCard(revisao: revisoes[index]),
      ),
    );
  }
}

class _RevisaoCard extends StatelessWidget {
  const _RevisaoCard({required this.revisao});

  final Review revisao;

  @override
  Widget build(BuildContext context) {
    final percentual = (revisao.nivelDominio * 100).clamp(0, 100).toStringAsFixed(0);
    final vencidaHa = revisao.proximaRevisao == null
        ? null
        : DateTime.now().difference(revisao.proximaRevisao!);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppColors.inputBorder),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: AppColors.purpleSoft,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: const Icon(
                  Icons.assignment_turned_in_outlined,
                  color: AppColors.purple,
                  size: 20,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      revisao.nome,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w700,
                        color: AppColors.textPrimary,
                      ),
                    ),
                    Text(
                      vencidaHa == null
                          ? 'Domínio: $percentual%'
                          : vencidaHa.inDays > 0
                          ? 'Domínio: $percentual% · vencida há ${vencidaHa.inDays} dia(s)'
                          : 'Domínio: $percentual% · venceu hoje',
                      style: const TextStyle(fontSize: 12, color: AppColors.textSecondary),
                    ),
                  ],
                ),
              ),
            ],
          ),
          if (revisao.videoUrl != null) ...[
            const SizedBox(height: 12),
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                onPressed: () {
                  Clipboard.setData(ClipboardData(text: revisao.videoUrl!));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Link do vídeo copiado')),
                  );
                },
                icon: const Icon(Icons.play_circle_outline, size: 18),
                label: const Text('Copiar link do vídeo de revisão'),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
