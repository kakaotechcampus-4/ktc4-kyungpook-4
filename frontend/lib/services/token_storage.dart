import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// 네이티브(iOS/Android)에서 로그인 세션을 들고 다니는 토큰 3종 저장소.
/// 웹은 쿠키로 세션을 유지하므로 이 클래스를 쓰지 않는다.
class TokenStorage {
  TokenStorage._();

  static const _storage = FlutterSecureStorage();

  static Future<String?> get accessToken => _storage.read(key: 'access_token');
  static Future<String?> get refreshToken => _storage.read(key: 'refresh_token');
  static Future<String?> get guestToken => _storage.read(key: 'guest_token');

  static Future<void> saveSession({
    required String accessToken,
    required String refreshToken,
  }) async {
    await _storage.write(key: 'access_token', value: accessToken);
    await _storage.write(key: 'refresh_token', value: refreshToken);
  }

  static Future<void> saveGuestToken(String token) =>
      _storage.write(key: 'guest_token', value: token);

  static Future<void> clearGuestToken() => _storage.delete(key: 'guest_token');

  /// 로그아웃 또는 refresh 실패 시 로그인 세션만 지운다 (게스트 토큰은 건드리지 않음).
  static Future<void> clearSession() async {
    await _storage.delete(key: 'access_token');
    await _storage.delete(key: 'refresh_token');
  }
}
