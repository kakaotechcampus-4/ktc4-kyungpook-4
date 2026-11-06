import 'dart:convert';

import 'package:http/http.dart' as http;

import '../api_config.dart';
import '../token_storage.dart';

/// 네이티브(iOS/Android)에는 쿠키 저장소가 없어, 세션을 Authorization: Bearer
/// 헤더로 들고 다닌다. access 토큰이 있으면 그걸, 없으면 게스트 토큰을 붙인다.
/// 401 을 받으면 POST /auth/refresh 에 refresh 토큰을 보내 새 토큰을 받고
/// 같은 요청을 다시 보낸다.
class AppCredentialedClient extends http.BaseClient {
  AppCredentialedClient(this._inner);

  final http.Client _inner;

  /// 화면을 열 때 요청 여러 개가 동시에 401 을 받아도 refresh 는 한 번만 보낸다
  /// (RefreshingClient 와 같은 이유 - refresh 토큰은 쓰면 바로 바뀐다).
  static Future<bool>? _refreshing;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final token = await TokenStorage.accessToken ?? await TokenStorage.guestToken;
    if (token != null) request.headers['Authorization'] = 'Bearer $token';

    final retry = request is http.Request ? _copy(request) : null;
    final response = await _inner.send(request);
    if (response.statusCode != 401 || retry == null || request.url.path.contains('/auth/')) {
      return response;
    }
    if (!await _refresh()) return response;
    await response.stream.drain<void>();
    final newToken = await TokenStorage.accessToken;
    if (newToken != null) retry.headers['Authorization'] = 'Bearer $newToken';
    return _inner.send(retry);
  }

  Future<bool> _refresh() {
    return _refreshing ??= _doRefresh().whenComplete(() => _refreshing = null);
  }

  Future<bool> _doRefresh() async {
    final refreshToken = await TokenStorage.refreshToken;
    if (refreshToken == null) return false;
    final response = await _inner.post(
      Uri.parse('${ApiConfig.baseUrl}/auth/refresh'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh_token': refreshToken}),
    );
    if (response.statusCode != 200) {
      await TokenStorage.clearSession();
      return false;
    }
    final tokens = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    await TokenStorage.saveSession(
      accessToken: tokens['access_token'] as String,
      refreshToken: tokens['refresh_token'] as String,
    );
    return true;
  }

  static http.Request _copy(http.Request request) {
    return http.Request(request.method, request.url)
      ..headers.addAll(request.headers)
      ..bodyBytes = request.bodyBytes
      ..followRedirects = request.followRedirects
      ..maxRedirects = request.maxRedirects
      ..persistentConnection = request.persistentConnection;
  }

  @override
  void close() => _inner.close();
}

http.Client createCredentialedClient() => AppCredentialedClient(http.Client());

/// 로그인도 게스트 토큰도 없는 상태로 첫 요청(프로필 생성)을 보내기 전에 호출한다.
/// 안 하고 헤더 없이 보내면 서버가 게스트를 새로 만들어 쿠키로 주는데, 앱은 쿠키를
/// 못 받아서 그 기록을 다시 찾을 방법이 없어진다.
Future<void> ensureGuestToken() async {
  if (await TokenStorage.accessToken != null) return;
  if (await TokenStorage.guestToken != null) return;
  final response = await http.post(Uri.parse('${ApiConfig.baseUrl}/auth/app/guest'));
  if (response.statusCode != 201) return;
  final body = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  await TokenStorage.saveGuestToken(body['guest_token'] as String);
}
