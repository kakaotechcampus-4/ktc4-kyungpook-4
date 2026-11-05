import 'dart:async';

import 'package:flutter_test/flutter_test.dart';
import 'package:frontend/services/http_client/refreshing_client.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

final _refreshUri = Uri.parse('http://api/auth/refresh');

RefreshingClient _client(Future<http.Response> Function(http.Request) handler) {
  return RefreshingClient(MockClient(handler), () => _refreshUri);
}

void main() {
  test('401 이면 refresh 하고 같은 요청을 다시 보낸다 (본문 포함)', () async {
    var loggedIn = false;
    final bodies = <String>[];
    final client = _client((req) async {
      if (req.url == _refreshUri) {
        loggedIn = true;
        return http.Response('', 204);
      }
      bodies.add(req.body);
      return loggedIn ? http.Response('ok', 200) : http.Response('', 401);
    });

    final res = await client.post(Uri.parse('http://api/profiles'), body: '{"a":1}');
    expect(res.statusCode, 200);
    expect(bodies, ['{"a":1}', '{"a":1}']);
  });

  test('동시에 여러 요청이 401 이어도 refresh 는 한 번만', () async {
    var refreshes = 0;
    var loggedIn = false;
    final gate = Completer<void>();
    final client = _client((req) async {
      if (req.url == _refreshUri) {
        refreshes++;
        await gate.future;
        loggedIn = true;
        return http.Response('', 204);
      }
      return loggedIn ? http.Response('ok', 200) : http.Response('', 401);
    });

    final pending = [
      client.get(Uri.parse('http://api/users/me/calendar')),
      client.get(Uri.parse('http://api/users/me/roadmap')),
      client.get(Uri.parse('http://api/manual-entries')),
    ];
    await Future<void>.delayed(Duration.zero);
    gate.complete();
    final results = await Future.wait(pending);
    expect(results.map((r) => r.statusCode), [200, 200, 200]);
    expect(refreshes, 1);
  });

  test('refresh 도 실패하면(게스트·만료) 원래 401 을 돌려준다', () async {
    var calls = 0;
    final client = _client((req) async {
      calls++;
      return http.Response('', 401);
    });
    final res = await client.get(Uri.parse('http://api/users/me/roadmap'));
    expect(res.statusCode, 401);
    expect(calls, 2); // 원래 요청 + refresh, 재시도는 없음
  });

  test('/auth/ 요청은 다시 보내지 않는다', () async {
    var calls = 0;
    final client = _client((req) async {
      calls++;
      return http.Response('', 401);
    });
    await client.post(Uri.parse('http://api/auth/logout'));
    expect(calls, 1);
  });
}
