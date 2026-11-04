import 'package:http/http.dart' as http;

/// 웹이 아닌 플랫폼(iOS/Android)에서는 쿠키를 시스템이 알아서 들고 다니지
/// 않는다 — 네이티브 앱에서 세션 쿠키를 쓰려면 별도 쿠키 저장소가
/// 필요하지만, 지금은 웹이 1차 타깃이라 기본 클라이언트만 둔다.
http.Client createCredentialedClient() => http.Client();
