import 'package:edu_ia/features/intro/presentation/intro_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_subjets_screen.dart';
import 'package:flutter/material.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/register_screen.dart';
import 'features/home/presentation/home_screen.dart';
import 'features/profile/presentation/profile_screen.dart';

void main() {
  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Edu IA',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light,
      initialRoute: '/intro',
      routes: {
        '/login': (_) => const LoginScreen(),
        '/register': (_) => const RegisterScreen(),
        '/home': (_) => const HomeScreen(),
        '/profile': (_) => const ProfileScreen(),
        '/quiz' : (_) => const QuizSubjetsScreen(),
        '/questions' : (_) => const QuizScreen(),
        '/intro' : (_) => const IntroScreen(),
      },
    );
  }
}
