import 'package:http/http.dart' as http;

/// 401 을 받으면 POST /auth/refresh 로 access 토큰을 한 번 새로 받고 같은 요청을 다시 보낸다.
///
/// access 토큰은 30분이면 만료돼서, 이게 없으면 로그인 30분 뒤부터 계정 기록(캘린더·로드맵 등)이
/// 안 보인다. 게스트는 refresh 쿠키가 없어 refresh 가 401 이고, 그러면 원래 401 을 그대로 돌려준다.
class RefreshingClient extends http.BaseClient {
  RefreshingClient(this._inner, this._refreshUri);

  final http.Client _inner;
  final Uri Function() _refreshUri;

  /// 화면을 열 때 요청 여러 개가 동시에 401 을 받아도 refresh 는 한 번만 보낸다.
  /// 백엔드는 refresh 토큰을 쓰면 바로 바꾸기 때문에, 두 번째 refresh 는 옛 토큰이라 실패하고
  /// 쿠키까지 지워져 로그아웃된다. 클라이언트가 여럿(ApiClient·AuthClient 등)이라 static 으로 둔다.
  static Future<bool>? _refreshing;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    // 보내고 나면 같은 요청 객체를 다시 쓸 수 없어서 미리 복사해 둔다
    final retry = request is http.Request ? _copy(request) : null;
    final response = await _inner.send(request);
    if (response.statusCode != 401 || retry == null || request.url.path.contains('/auth/')) {
      return response;
    }
    if (!await _refresh()) return response;
    await response.stream.drain<void>();
    return _inner.send(retry);
  }

  Future<bool> _refresh() {
    return _refreshing ??= _inner
        .post(_refreshUri())
        .then((r) => r.statusCode == 204)
        .catchError((_) => false)
        .whenComplete(() => _refreshing = null);
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
