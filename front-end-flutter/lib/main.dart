import 'package:edu_ia/features/intro/presentation/intro_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/add_payment_method_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/checkout_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/order_details_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/orders_screen.dart';
import 'package:edu_ia/features/marketplace/presentation/marketplace_screen.dart';
import 'package:edu_ia/features/notifications/presentation/notifications_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_screen.dart';
import 'package:edu_ia/features/quiz/presentation/quiz_subjets_screen.dart';
import 'package:flutter/material.dart';
import 'core/theme/app_theme.dart';
import 'features/auth/presentation/login_screen.dart';
import 'features/auth/presentation/logistics_login_screen.dart';
import 'features/logistics/presentation/logistics_dashboard_screen.dart';
import 'features/logistics/presentation/order_picking_screen.dart';
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
        '/logistics': (_) => const LogisticsLoginScreen(),
        '/logistics-dashboard': (_) => const LogisticsDashboardScreen(),
        '/logistics-picking': (_) => const OrderPickingScreen(),
        '/register': (_) => const RegisterScreen(),
        '/home': (_) => const HomeScreen(),
        '/profile': (_) => const ProfileScreen(),
        '/quiz' : (_) => const QuizSubjetsScreen(),
        '/questions' : (_) => const QuizScreen(),
        '/intro' : (_) => const IntroScreen(),
        '/notifications' : (_) => const NotificationsScreen(),
        '/marketplace' : (_) => const MarketplaceScreen(),
        '/checkout' : (_) => const CheckoutScreen(),
        '/add-payment-method' : (_) => const AddPaymentMethodScreen(),
        '/orders' : (_) => const OrdersScreen(),
        '/order-details' : (_) => const OrderDetailsScreen(),
      },
    );
  }
}
