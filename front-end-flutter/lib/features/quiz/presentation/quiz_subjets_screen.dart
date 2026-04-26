import 'package:edu_ia/data/subjects.dart';
import 'package:edu_ia/features/components/nav_bar.dart';
import 'package:flutter/material.dart';
import '../../../core/theme/app_colors.dart';
import '../../../features/components/top_bar.dart';

class QuizSubjetsScreen extends StatefulWidget {
  const QuizSubjetsScreen({super.key});

  @override
  State<QuizSubjetsScreen> createState() => _QuizSubjetsScreenState();
}

class _QuizSubjetsScreenState extends State<QuizSubjetsScreen> {
  int _currentTabIndex = 1;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: const BoxDecoration(gradient: AppColors.headerGradient),
      child: Scaffold(
        backgroundColor: Colors.transparent,
        appBar: const TopBar(),
        body: SafeArea(
          child: SingleChildScrollView(
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
                const _SubjectsSection(),
              ],
            ),
          ),
        ),
        bottomNavigationBar: NavBar(
        currentIndex: _currentTabIndex,
        onTap: (index) {
          setState(() => _currentTabIndex = index);

          // Navegação de acordo com o índice
          switch (index) {
            case 0:
              Navigator.pushReplacementNamed(context, '/home');
              break;
            case 1:
              Navigator.pushReplacementNamed(context, '/quiz');
              break;
            case 2:
              Navigator.pushReplacementNamed(context, '/study');
              break;
            case 3:
              Navigator.pushReplacementNamed(context, '/review');
              break;
            case 4:
              Navigator.pushReplacementNamed(context, '/status');
              break;
          }
        },
        ),
      ),
    );
  }
}

class _SubjectsSection extends StatelessWidget {
  const _SubjectsSection();

  static const _subjects = [
    _SubjectData('Biologia', 'icon_biologia.png'),
    _SubjectData('Matemática', 'matematica.png'),
    _SubjectData('Geografia', 'geografia.png'),
    _SubjectData('História', 'historia.png'),
    _SubjectData('Filosofia', 'filosofia.png'),
    _SubjectData('Português', 'portugues.png'),
    _SubjectData('Química', 'quimica.png'),
    _SubjectData('Sociologia', 'sociologia.png')
  ];

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        const SizedBox(height: 40),
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          mainAxisSpacing: 12,
          crossAxisSpacing: 12,
          childAspectRatio: 1.15,
          children: _subjects
              .map((s) => _SubjectCard(
                    name: s.name,
                    image: 'assets/images/subjects/${s.image}',
                  ))
              .toList(),
        ),
      ],
    );
  }
}

class _SubjectData {
  const _SubjectData(this.name, this.image);
  final String name;
  final String image;
}

class _SubjectCard extends StatelessWidget {
  const _SubjectCard({
    required this.name,
    required this.image,
  });

  final String name;
  final String image;

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(20),
      onTap: () {
        showModalBottomSheet(
          context: context,
          shape: const RoundedRectangleBorder(
            borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
          ),
          builder: (context) {
            return _SubjectModal(name: name);
          },
        );
      },
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
              child: Image.asset(
                image,
                width: 56,
                height: 56,
                filterQuality: FilterQuality.high,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              name,
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

class _SubjectModal extends StatelessWidget {
  final String name;

  const _SubjectModal({required this.name});

  @override
  Widget build(BuildContext context) {
    final topics = subjects[name] ?? [];

    return SizedBox(
      height: MediaQuery.of(context).size.height * 0.6,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Assuntos de $name',
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: AppColors.textPrimary,
              ),
            ),
            const SizedBox(height: 16),
            Expanded(
              child: ListView.separated(
                itemCount: topics.length,
                separatorBuilder: (_, _) => const Divider(height: 1),
                itemBuilder: (context, index) {
                  final topic = topics[index];
                  return ListTile(
                    title: Text(topic),
                    onTap: () {
                      Navigator.pop(context); // fecha a modal
                      Navigator.pushNamed(
                        context,
                        '/questions',
                        arguments: {
                          'subject': name,
                          'topic': topic,
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

