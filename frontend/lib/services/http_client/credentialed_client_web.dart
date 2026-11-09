import 'package:http/browser_client.dart';
import 'package:http/http.dart' as http;

import '../api_config.dart';
import 'refreshing_client.dart';

/// 백엔드가 세션을 쿠키(refresh_token/access_token)로 굽기 때문에,
/// 웹에서는 요청에 쿠키를 실어 보내도록 withCredentials 를 켜야 한다.
/// (안 켜면 로그인 직후에도 /users/me 가 항상 401 로 보인다)
/// access 토큰이 만료되면 refresh 하고 다시 보내는 것까지 여기서 한다.
http.Client createCredentialedClient() => RefreshingClient(
      BrowserClient()..withCredentials = true,
      () => Uri.parse('${ApiConfig.baseUrl}/auth/refresh'),
    );

/// 웹은 쿠키로 게스트를 식별하므로(서버가 첫 요청에 알아서 구워 준다) 따로 할 일이 없다.
Future<void> ensureGuestToken() async {}
