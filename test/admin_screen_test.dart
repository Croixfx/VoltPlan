import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:voltplan/app/theme.dart';
import 'package:voltplan/core/network/api_client.dart';
import 'package:voltplan/core/network/server_waker.dart';
import 'package:voltplan/features/admin/admin_screen.dart';
import 'package:voltplan/shared/state/app_state.dart';

void main() {
  testWidgets('the admin sees accounts and projects, and can deactivate an account', (tester) async {
    tester.view.physicalSize = const Size(900, 1800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    final calls = <String>[];
    var deactivated = false;
    final client = ApiClient(
      waker: ServerWaker.disabled(),
      client: MockClient((req) async {
        calls.add('${req.method} ${req.url.path}');
        http.Response json(Object body) => http.Response(jsonEncode(body), 200);
        final path = req.url.path;
        if (path.endsWith('/admin/overview')) {
          return json({
            'users': 2, 'new_users_7d': 1, 'deactivated_users': deactivated ? 1 : 0, 'projects': 1,
            'new_projects_7d': 1, 'unowned_projects': 0,
            'projects_by_status': {'created': 1}, 'analyses_by_status': {},
          });
        }
        if (path.endsWith('/admin/users')) {
          return json([
            {'id': 'a', 'email': 'boss@example.com', 'name': '', 'is_admin': true, 'is_owner': true, 'project_count': 0},
            {
              'id': 'u1', 'email': 'ana@example.com', 'name': 'Ana', 'is_admin': false, 'project_count': 1,
              'deactivated_at': deactivated ? '2026-10-16T10:00:00' : null,
              'deactivated_reason': deactivated ? 'spam' : null,
            },
          ]);
        }
        if (path.endsWith('/admin/projects')) {
          return json([
            {'id': 'p1', 'name': 'Ana villa', 'client': 'Client', 'location': 'Kigali', 'status': 'created',
             'owner_email': 'ana@example.com'},
          ]);
        }
        if (path.endsWith('/make-admin')) return json({'id': 'u1', 'is_admin': true});
        if (path.endsWith('/deactivate')) {
          deactivated = true;
          return json({'id': 'u1', 'deactivated': true});
        }
        return http.Response('{}', 404);
      }),
    );

    await tester.pumpWidget(MaterialApp(
      theme: AppTheme.light(),
      home: AdminScreen(state: AppState(), client: client),
    ));
    await tester.pumpAndSettle();

    expect(find.text('Accounts'), findsWidgets);
    await tester.tap(find.text('Accounts').last);
    await tester.pumpAndSettle();
    expect(find.text('ana@example.com'), findsOneWidget);
    expect(find.textContaining('(admin)'), findsOneWidget);

    // the owner admin has no actions at all; an ordinary account can be promoted or deactivated
    expect(tester.widget<PopupMenuButton<String>>(find.byType(PopupMenuButton<String>).first).enabled, isFalse);

    await tester.tap(find.byType(PopupMenuButton<String>).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Make admin'));
    await tester.pumpAndSettle();
    expect(calls, contains('POST /api/admin/users/u1/make-admin'));

    await tester.tap(find.byType(PopupMenuButton<String>).last);
    await tester.pumpAndSettle();
    await tester.tap(find.text('Deactivate'));
    await tester.pumpAndSettle();
    await tester.tap(find.widgetWithText(FilledButton, 'Deactivate'));
    await tester.pumpAndSettle();

    expect(calls, contains('POST /api/admin/users/u1/deactivate'));
    await tester.tap(find.byType(PopupMenuButton<String>).last);
    await tester.pumpAndSettle();
    expect(find.text('Reactivate'), findsOneWidget);
    await tester.tapAt(const Offset(5, 5));
    await tester.pumpAndSettle();
    expect(find.textContaining('DEACTIVATED: spam'), findsOneWidget);

    await tester.tap(find.text('Projects').last);
    await tester.pumpAndSettle();
    expect(find.text('Ana villa'), findsOneWidget);
    expect(find.textContaining('ana@example.com'), findsWidgets);
  });
}
