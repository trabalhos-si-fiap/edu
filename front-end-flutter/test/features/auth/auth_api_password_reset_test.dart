import 'dart:convert';

import 'package:edu_ia/features/auth/data/auth_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/testing.dart';
import 'package:http/http.dart' as http;

void main() {
  group('requestPasswordReset', () {
    test('posts the email to the request endpoint and succeeds on 200',
        () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(
          jsonEncode({'detail': 'If the email exists, a reset code was sent.'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = AuthApi(client: client);

      await api.requestPasswordReset(email: 'maria@example.com');

      expect(captured.method, 'POST');
      expect(captured.url.path, endsWith('/auth/password-reset/request'));
      expect(jsonDecode(captured.body), {'email': 'maria@example.com'});
    });

    test('throws AuthException on 429', () async {
      final client = MockClient((req) async => http.Response('', 429));
      final api = AuthApi(client: client);

      expect(
        () => api.requestPasswordReset(email: 'maria@example.com'),
        throwsA(isA<AuthException>()),
      );
    });
  });

  group('confirmPasswordReset', () {
    test('posts email, code and new_password and succeeds on 200', () async {
      late http.Request captured;
      final client = MockClient((req) async {
        captured = req;
        return http.Response(
          jsonEncode({'detail': 'Password updated.'}),
          200,
          headers: {'content-type': 'application/json'},
        );
      });
      final api = AuthApi(client: client);

      await api.confirmPasswordReset(
        email: 'maria@example.com',
        code: '123456',
        newPassword: 'NovaSenha!9',
      );

      expect(captured.url.path, endsWith('/auth/password-reset/confirm'));
      expect(jsonDecode(captured.body), {
        'email': 'maria@example.com',
        'code': '123456',
        'new_password': 'NovaSenha!9',
      });
    });

    test('throws AuthException with the invalid-code message on 400', () async {
      final client = MockClient((req) async => http.Response('', 400));
      final api = AuthApi(client: client);

      expect(
        () => api.confirmPasswordReset(
          email: 'maria@example.com',
          code: '000000',
          newPassword: 'NovaSenha!9',
        ),
        throwsA(isA<AuthException>().having(
            (e) => e.message, 'message', 'Código inválido ou expirado')),
      );
    });

    test('throws AuthException on 422', () async {
      final client = MockClient((req) async => http.Response('', 422));
      final api = AuthApi(client: client);

      expect(
        () => api.confirmPasswordReset(
          email: 'maria@example.com',
          code: '123',
          newPassword: 'weak',
        ),
        throwsA(isA<AuthException>()),
      );
    });
  });
}
