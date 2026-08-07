import 'package:flutter/material.dart';

import '../../../core/theme/app_colors.dart';
import '../../../features/components/top_bar.dart';
import '../../components/nav_bar.dart';
import '../data/quiz_api.dart';
import '../domain/quiz_models.dart';

/// Tela inicial do Quiz: `GET /subjects` (matérias) e, ao tocar numa
/// matéria, `GET /subjects/{id}/topics` (temas) — substituiu o mapa
/// estático `data/subjects.dart`. Cada tema é um questionário de
/// diagnóstico completo (não um "assunto" solto como antes).
class QuizSubjetsScreen extends StatefulWidget {
  const QuizSubjetsScreen({super.key});

  @override
  State<QuizSubjetsScreen> createState() => _QuizSubjetsScreenState();
}

class _QuizSubjetsScreenState extends State<QuizSubjetsScreen> {
  final _api = QuizApi();
  late Future<List<Materia>> _materiasFuture;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  void _carregar() {
    setState(() {
      _materiasFuture = _api.fetchMaterias();
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
            child: FutureBuilder<List<Materia>>(
              future: _materiasFuture,
              builder: (context, snapshot) {
                return SingleChildScrollView(
                  physics: const AlwaysScrollableScrollPhysics(),
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const SizedBox(height: 18),
                      const Text(
                        'Escolha uma matéria',
                        style: TextStyle(
                          fontSize: 28,
                          fontWeight: FontWeight.w800,
                          color: AppColors.textPrimary,
                          height: 1.2,
                        ),
                      ),
                      const SizedBox(height: 40),
                      _buildConteudo(snapshot),
                    ],
                  ),
                );
              },
            ),
          ),
        ),
        bottomNavigationBar: const NavBar(currentIndex: 1),
      ),
    );
  }

  Widget _buildConteudo(AsyncSnapshot<List<Materia>> snapshot) {
    if (snapshot.connectionState == ConnectionState.waiting) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 60),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (snapshot.hasError) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 40),
        child: Column(
          children: [
            const Icon(Icons.error_outline, size: 40, color: AppColors.textSecondary),
            const SizedBox(height: 12),
            Text(
              'Não foi possível carregar as matérias.\n${snapshot.error}',
              textAlign: TextAlign.center,
              style: const TextStyle(color: AppColors.textSecondary),
            ),
            const SizedBox(height: 16),
            OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
          ],
        ),
      );
    }
    final materias = snapshot.data ?? const [];
    if (materias.isEmpty) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 40),
        child: Center(
          child: Text(
            'Nenhuma matéria disponível ainda.',
            style: TextStyle(color: AppColors.textSecondary),
          ),
        ),
      );
    }
    return GridView.count(
      crossAxisCount: 2,
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      mainAxisSpacing: 12,
      crossAxisSpacing: 12,
      childAspectRatio: 1.15,
      children: materias.map((m) => _MateriaCard(materia: m, api: _api)).toList(),
    );
  }
}

/// Mapa nome de matéria (como cadastrado no learning-service) -> asset já
/// existente em `assets/images/subjects/`. Cobre as 8 matérias do plano
/// original mais Física; qualquer nome novo cai no ícone genérico em vez
/// de quebrar — o backend hoje só tem "Biologia" cadastrada
/// (`scripts/seed_biologia_citologia.sql`), então isso cresce junto do
/// conteúdo sendo adicionado, sem precisar mexer no Flutter de novo.
String? _assetParaMateria(String nome) {
  const mapa = {
    'biologia': 'icon_biologia.png',
    'matemática': 'matematica.png',
    'matematica': 'matematica.png',
    'geografia': 'geografia.png',
    'história': 'historia.png',
    'historia': 'historia.png',
    'filosofia': 'filosofia.png',
    'português': 'portugues.png',
    'portugues': 'portugues.png',
    'química': 'quimica.png',
    'quimica': 'quimica.png',
    'sociologia': 'sociologia.png',
    'física': 'fisica.png',
    'fisica': 'fisica.png',
  };
  return mapa[nome.trim().toLowerCase()];
}

class _MateriaCard extends StatelessWidget {
  const _MateriaCard({required this.materia, required this.api});

  final Materia materia;
  final QuizApi api;

  @override
  Widget build(BuildContext context) {
    final asset = _assetParaMateria(materia.nome);
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: () => showModalBottomSheet(
        context: context,
        shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
        ),
        builder: (_) => _TemasModal(materia: materia, api: api),
      ),
      child: Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppColors.white,
          borderRadius: BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.04),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: asset != null
                  ? Image.asset(
                      'assets/images/subjects/$asset',
                      width: 56,
                      height: 56,
                      filterQuality: FilterQuality.high,
                    )
                  : Container(
                      width: 56,
                      height: 56,
                      decoration: BoxDecoration(
                        color: AppColors.purpleSoft,
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Icon(
                        Icons.menu_book_rounded,
                        color: AppColors.purple,
                      ),
                    ),
            ),
            const SizedBox(height: 12),
            Text(
              materia.nome,
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w700,
                color: AppColors.textPrimary,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Lista de temas de uma matéria, carregada sob demanda ao abrir a modal
/// (evita buscar os temas de todas as matérias de uma vez na tela
/// inicial). Cada tema aqui é um questionário de diagnóstico completo.
class _TemasModal extends StatefulWidget {
  const _TemasModal({required this.materia, required this.api});

  final Materia materia;
  final QuizApi api;

  @override
  State<_TemasModal> createState() => _TemasModalState();
}

class _TemasModalState extends State<_TemasModal> {
  late Future<List<Tema>> _temasFuture;

  @override
  void initState() {
    super.initState();
    _temasFuture = widget.api.fetchTemas(widget.materia.id);
  }

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: MediaQuery.of(context).size.height * 0.6,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Temas de ${widget.materia.nome}',
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: FutureBuilder<List<Tema>>(
                future: _temasFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Center(
                      child: Text(
                        'Erro ao carregar temas:\n${snapshot.error}',
                        textAlign: TextAlign.center,
                        style: const TextStyle(color: AppColors.textSecondary),
                      ),
                    );
                  }
                  final temas = snapshot.data ?? const [];
                  if (temas.isEmpty) {
                    return const Center(
                      child: Text(
                        'Nenhum tema disponível ainda para esta matéria.',
                        style: TextStyle(color: AppColors.textSecondary),
                      ),
                    );
                  }
                  return ListView.separated(
                    itemCount: temas.length,
                    separatorBuilder: (_, _) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final tema = temas[index];
                      return ListTile(
                        title: Text(tema.nome),
                        trailing: const Icon(Icons.chevron_right),
                        onTap: () {
                          Navigator.pop(context); // fecha a modal
                          Navigator.pushNamed(
                            context,
                            '/questions',
                            arguments: {
                              'materiaNome': widget.materia.nome,
                              'temaId': tema.id,
                              'temaNome': tema.nome,
                            },
                          );
                        },
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
