import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/calendar_event.dart';
import '../models/portfolio_option.dart';
import 'api_config.dart';

class ApiException implements Exception {
  final String message;

  const ApiException(this.message);

  @override
  String toString() => message;
}

/// 백엔드(api/v1) 호출을 모아둔 곳. 인증은 아직 없어서 헤더에 토큰을 싣지 않는다.
class ApiClient {
  ApiClient._();

  static final ApiClient instance = ApiClient._();

  Uri _uri(String path) => Uri.parse('${ApiConfig.baseUrl}$path');

  Map<String, dynamic> _decodeObject(http.Response response) {
    if (response.statusCode >= 400) {
      throw ApiException('요청 실패 (${response.statusCode}): ${response.body}');
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
  }

  List<dynamic> _decodeList(http.Response response) {
    if (response.statusCode >= 400) {
      throw ApiException('요청 실패 (${response.statusCode}): ${response.body}');
    }
    return jsonDecode(utf8.decode(response.bodyBytes)) as List<dynamic>;
  }

  /// STEP1 입력값으로 프로필을 만들고 profile_id 를 반환한다.
  /// 금액은 원 단위로 넘겨야 한다 (화면 입력은 "천 원" 단위이므로 호출부에서 1000을 곱한다).
  Future<int> createProfile({
    required int lumpSumWon,
    required int monthlySavingWon,
    required int periodMonths,
  }) async {
    final response = await http.post(
      _uri('/profiles'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'lump_sum': lumpSumWon,
        'monthly_saving': monthlySavingWon,
        'period_months': periodMonths,
      }),
    );
    return _decodeObject(response)['profile_id'] as int;
  }

  Future<List<PortfolioOption>> recommendPortfolios(int profileId) async {
    final response = await http.post(
      _uri('/portfolios/recommend'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'profile_id': profileId}),
    );
    final options = _decodeObject(response)['options'] as List<dynamic>;
    return options.map((o) => PortfolioOption.fromJson(o as Map<String, dynamic>)).toList();
  }

  /// 추천안 중 하나를 확정 가입한다. 반환값은 이후 캘린더 조회에 쓰는 portfolio_id.
  Future<int> selectPortfolio({required int profileId, required PortfolioTier tier}) async {
    final response = await http.post(
      _uri('/portfolios'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'profile_id': profileId, 'tier': tier.apiValue}),
    );
    return _decodeObject(response)['portfolio_id'] as int;
  }

  Future<List<CalendarEvent>> getCalendar(int portfolioId) async {
    final response = await http.get(_uri('/portfolios/$portfolioId/calendar'));
    return _decodeList(response).map((e) => CalendarEvent.fromJson(e as Map<String, dynamic>)).toList();
  }
}
