import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/manual_product_entry.dart';
import 'api_client.dart';
import 'api_config.dart';
import 'http_client/credentialed_client_stub.dart'
    if (dart.library.html) 'http_client/credentialed_client_web.dart';

/// `/api/v1/manual-entries` 호출을 모아둔 곳. 로그인한 사용자 소유의 기록이라
/// 쿠키 세션이 필요해서(AuthClient 와 동일하게) 전용 크리덴셜 클라이언트를 쓴다.
class ManualEntryClient {
  ManualEntryClient._();

  static final ManualEntryClient instance = ManualEntryClient._();

  final http.Client _client = createCredentialedClient();

  Uri _uri(String path) => Uri.parse('${ApiConfig.baseUrl}$path');

  String _formatDate(DateTime date) {
    final y = date.year.toString().padLeft(4, '0');
    final m = date.month.toString().padLeft(2, '0');
    final d = date.day.toString().padLeft(2, '0');
    return '$y-$m-$d';
  }

  /// [start]~[end] 기간에 기록된 항목을 조회한다. 로그인 안 되어 있으면(401)
  /// 빈 목록으로 취급한다.
  Future<List<ManualProductEntry>> list({
    required DateTime start,
    required DateTime end,
  }) async {
    final uri = _uri('/manual-entries').replace(queryParameters: {
      'start': _formatDate(start),
      'end': _formatDate(end),
    });
    final response = await _client.get(uri);
    if (response.statusCode == 401) return const [];
    if (response.statusCode >= 400) {
      throw ApiException('직접 기록 조회 실패 (${response.statusCode}): ${response.body}');
    }
    return (jsonDecode(utf8.decode(response.bodyBytes)) as List<dynamic>)
        .map((e) => ManualProductEntry.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<ManualProductEntry> create({
    required DateTime date,
    required String institutionName,
    String? productId,
    required String productName,
    required int amount,
    String memo = '',
  }) async {
    final body = <String, dynamic>{
      'entry_date': _formatDate(date),
      'institution_name': institutionName,
      'product_id': ?productId,
      'product_name': productName,
      'amount': amount,
      if (memo.isNotEmpty) 'memo': memo,
    };
    final response = await _client.post(
      _uri('/manual-entries'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    if (response.statusCode >= 400) {
      throw ApiException('직접 기록 추가 실패 (${response.statusCode}): ${response.body}');
    }
    return ManualProductEntry.fromJson(
      jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>,
    );
  }

  Future<void> delete(int entryId) async {
    final response = await _client.delete(_uri('/manual-entries/$entryId'));
    if (response.statusCode >= 400 && response.statusCode != 404) {
      throw ApiException('직접 기록 삭제 실패 (${response.statusCode}): ${response.body}');
    }
  }
}
