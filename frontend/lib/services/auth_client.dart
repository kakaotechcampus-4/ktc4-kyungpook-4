import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/current_user.dart';
import 'api_client.dart';
import 'api_config.dart';
import 'http_client/credentialed_client_stub.dart'
    if (dart.library.html) 'http_client/credentialed_client_web.dart';

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
    final response = await _client.post(_uri('/auth/logout'));
    if (response.statusCode >= 400 && response.statusCode != 401) {
      throw ApiException('로그아웃 실패 (${response.statusCode}): ${response.body}');
    }
  }
}
