import 'package:http/browser_client.dart';
import 'package:http/http.dart' as http;

/// 백엔드가 세션을 쿠키(refresh_token/access_token)로 굽기 때문에,
/// 웹에서는 요청에 쿠키를 실어 보내도록 withCredentials 를 켜야 한다.
/// (안 켜면 로그인 직후에도 /users/me 가 항상 401 로 보인다)
http.Client createCredentialedClient() => BrowserClient()..withCredentials = true;
