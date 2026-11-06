import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import 'package:http/http.dart' as http;

import '../models/current_user.dart';
import 'api_client.dart';
import 'api_config.dart';
import 'http_client/credentialed_client_stub.dart'
    if (dart.library.html) 'http_client/credentialed_client_web.dart';
import 'token_storage.dart';

/// 지금 백엔드가 지원하는 소셜 로그인 제공자. 네이버는 /auth/{provider}/login
/// 쪽에 아직 없어서(Available values: google, kakao) 뺐다 - 버튼은 화면에
/// 남겨두되 눌러도 여기로 연결하면 안 된다.
enum SocialProvider { google, kakao }

extension on SocialProvider {
  String get apiValue => switch (this) {
    SocialProvider.google => 'google',
    SocialProvider.kakao => 'kakao',
  };
}

/// 인증(`/auth`, `/users/me`) 관련 호출을 모아둔 곳. 로그인 세션이 쿠키
/// (refresh_token/access_token)로 관리되기 때문에, 다른 API 와 달리
/// 요청에 쿠키를 실어 보내야 해서 전용 클라이언트를 쓴다.
class AuthClient {
  AuthClient._();

  static final AuthClient instance = AuthClient._();

  final http.Client _client = createCredentialedClient();

  Uri _uri(String path) => Uri.parse('${ApiConfig.baseUrl}$path');

  /// 소셜 로그인 시작 URL. 버튼 탭 시 현재 탭을 이 주소로 이동시켜야 한다
  /// (서버가 구글/카카오 로그인 화면으로 리다이렉트하므로 fetch 로는 안 됨).
  /// [next] 는 로그인 완료 후 돌아올 FE 경로.
  Uri socialLoginUrl(SocialProvider provider, {required String next}) {
    return _uri('/auth/${provider.apiValue}/login').replace(
      queryParameters: {'next': next},
    );
  }

  /// 안드로이드/iOS 전용 로그인. 외부 브라우저(Custom Tab)를 열어 로그인시키고
  /// safebrother://auth 로 돌아오면 일회용 코드를 PKCE verifier 와 함께 토큰으로
  /// 교환한다. 게스트 토큰이 있으면 그 기록(프로필·포트폴리오 등)을 로그인한
  /// 계정으로 승계한다. 구글은 앱 내장 웹뷰 로그인을 막기 때문에 반드시 외부
  /// 브라우저여야 한다 (flutter_web_auth_2 가 이렇게 동작한다).
  Future<void> loginWithApp(SocialProvider provider) async {
    final verifier = _newPkceVerifier();
    final url = _uri('/auth/${provider.apiValue}/login').replace(
      queryParameters: {'client': 'app', 'code_challenge': _pkceChallenge(verifier)},
    );

    final result = await FlutterWebAuth2.authenticate(
      url: url.toString(),
      callbackUrlScheme: 'safebrother',
    );
    final params = Uri.parse(result).queryParameters;
    if (params['error'] != null) {
      throw ApiException('로그인 실패: ${params['error']}');
    }

    final guestToken = await TokenStorage.guestToken;
    final response = await _client.post(
      _uri('/auth/app/token'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'code': params['code'],
        'code_verifier': verifier,
        'guest_token': ?guestToken,
      }),
    );
    if (response.statusCode != 200) {
      throw ApiException('로그인 실패 (${response.statusCode}): ${response.body}');
    }
    final tokens = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    await TokenStorage.saveSession(
      accessToken: tokens['access_token'] as String,
      refreshToken: tokens['refresh_token'] as String,
    );
    await TokenStorage.clearGuestToken();
  }

  String _newPkceVerifier() {
    final random = Random.secure();
    return base64UrlEncode(List<int>.generate(32, (_) => random.nextInt(256))).replaceAll('=', '');
  }

  String _pkceChallenge(String verifier) =>
      base64UrlEncode(sha256.convert(ascii.encode(verifier)).bytes).replaceAll('=', '');

  /// 로그인 여부 확인. 로그인 안 되어 있으면(401) null.
  Future<CurrentUser?> fetchCurrentUser() async {
    final response = await _client.get(_uri('/users/me'));
    if (response.statusCode == 401) return null;
    if (response.statusCode >= 400) {
      throw ApiException('로그인 상태 확인 실패 (${response.statusCode}): ${response.body}');
    }
    return CurrentUser.fromJson(
      jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>,
    );
  }

  Future<void> logout() async {
    final refreshToken = kIsWeb ? null : await TokenStorage.refreshToken;
    final response = await _client.post(
      _uri('/auth/logout'),
      headers: refreshToken != null ? {'Content-Type': 'application/json'} : null,
      body: refreshToken != null ? jsonEncode({'refresh_token': refreshToken}) : null,
    );
    if (!kIsWeb) await TokenStorage.clearSession();
    if (response.statusCode >= 400 && response.statusCode != 401) {
      throw ApiException('로그아웃 실패 (${response.statusCode}): ${response.body}');
    }
  }
}
