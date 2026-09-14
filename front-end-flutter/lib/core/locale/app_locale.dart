import 'package:flutter/material.dart';
import 'package:flutter_localizations/flutter_localizations.dart';

/// Idioma do app: português do Brasil, fixo.
///
/// Sem isto o `MaterialApp` cai no inglês embutido do Flutter, e todo widget
/// que traz texto próprio — o seletor de data do cadastro e do onboarding
/// ("Select date", "Cancel", "January 2000") — aparece em inglês no meio de
/// uma interface em português. Os delegates globais trazem as traduções do
/// Material, do Cupertino e dos widgets básicos (direção do texto).
class AppLocale {
  AppLocale._();

  static const locale = Locale('pt', 'BR');

  static const supportedLocales = [locale];

  static const localizationsDelegates = <LocalizationsDelegate<dynamic>>[
    GlobalMaterialLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
  ];
}
