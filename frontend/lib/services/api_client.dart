import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/calendar_event.dart';
import '../models/etc_question.dart';
import '../models/onboarding_input.dart';
import '../models/portfolio_option.dart';
import '../models/product_summary.dart';
import '../models/roadmap_stats.dart';
import '../models/single_plan.dart';
import 'api_config.dart';
import 'http_client/credentialed_client_stub.dart'
    if (dart.library.html) 'http_client/credentialed_client_web.dart';

class ApiException implements Exception {
  final String message;

  const ApiException(this.message);

  @override
  String toString() => message;
}

/// 백엔드(api/v1) 호출을 모아둔 곳.
/// 프로필·추천·확정·캘린더는 만든 사람(로그인 또는 게스트 쿠키)만 볼 수 있어서 쿠키를 싣는다.
/// 서버는 FE 와 주소가 같아 원래 실리지만, 로컬 개발(포트가 다름)에서는 이게 있어야 실린다.
class ApiClient {
  ApiClient._();

  static final ApiClient instance = ApiClient._();

  final http.Client _client = createCredentialedClient();

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

  /// STEP1~3 입력값으로 프로필을 만들고 profile_id 를 반환한다.
  /// STEP2·3 답변은 화면 선택지 문구를 그대로 보낸다 (백엔드 app/services/onboarding.py 가 해석).
  /// 안 물어본(비어 있는) 항목은 보내지 않는다 - 빈 문자열("")은 422 가 난다.
  Future<int> createProfile(OnboardingInput input) async {
    final body = <String, dynamic>{
      'lump_sum': input.lumpSum,
      'monthly_saving': input.monthlySaving,
      'period_months': input.periodMonths,
      if (input.currentBanks.isNotEmpty) 'current_banks': input.currentBanks,
      if (input.mainBank.isNotEmpty) 'main_bank': input.mainBank,
      'birth_date': ?_birthDate(input),
      if (input.salaryAccountTransferable.isNotEmpty)
        'salary_account_transferable': input.salaryAccountTransferable,
      if (input.autoTransferMovable.isNotEmpty)
        'auto_transfer_movable': input.autoTransferMovable,
      if (input.savingsAutoTransferPossible.isNotEmpty)
        'savings_auto_transfer_possible': input.savingsAutoTransferPossible,
      if (input.pensionAccountTransferable.isNotEmpty)
        'pension_account_transferable': input.pensionAccountTransferable,
      if (input.cooperativeInsuranceJoinStatus.isNotEmpty)
        'cooperative_insurance_join_status': input.cooperativeInsuranceJoinStatus,
      if (input.monthlyCardSpending.isNotEmpty)
        'monthly_card_spending': input.monthlyCardSpending,
      if (input.marketingConsent.isNotEmpty)
        'marketing_consent': input.marketingConsent,
      if (input.canInstallBankApp.isNotEmpty)
        'can_install_bank_app': input.canInstallBankApp,
      if (input.taxExemptEligibility.isNotEmpty)
        'tax_exempt_eligibility': input.taxExemptEligibility,
      if (input.specialHouseholdTypes.isNotEmpty)
        'special_household_types': input.specialHouseholdTypes,
      if (input.cooperativeMembershipStatus.isNotEmpty)
        'cooperative_membership_status': input.cooperativeMembershipStatus,
      if (input.cooperativeJoinChoices.isNotEmpty)
        'cooperative_join_choices': input.cooperativeJoinChoices,
      if (input.mutualFinanceTaxExemptEligible.isNotEmpty)
        'mutual_finance_tax_exempt_eligible': input.mutualFinanceTaxExemptEligible,
      'mutual_finance_existing_amount': ?_mutualFinanceExistingAmount(input),
      if (input.additionalNote.isNotEmpty) 'additional_note': input.additionalNote,
    };

    final response = await _client.post(
      _uri('/profiles'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decodeObject(response)['profile_id'] as int;
  }

  /// "YYYY-MM-DD" 형식. 날짜가 유효하지 않으면(달력에 없는 날짜 등) 보내지 않는다.
  String? _birthDate(OnboardingInput input) {
    if (!input.isBirthDateValid) return null;
    final month = input.birthMonth.padLeft(2, '0');
    final day = input.birthDay.padLeft(2, '0');
    return '${input.birthYear}-$month-$day';
  }

  /// "잘 모르겠어요"를 선택했으면 null. 숫자를 못 읽어도(미입력 등) null.
  int? _mutualFinanceExistingAmount(OnboardingInput input) {
    if (input.mutualFinanceExistingAmountUnknown) return null;
    return int.tryParse(input.mutualFinanceExistingAmountText);
  }

  /// with_reason: false 로 불러서 AI 추천 이유(26초 가량) 없이 숫자만 빠르게 받는다.
  /// 이유는 fetchPortfolioReasons 로 따로 받아서 화면에 나중에 채워 넣는다.
  Future<(List<PortfolioOption>, SinglePlan?)> recommendPortfolios(int profileId) async {
    final response = await _client.post(
      _uri('/portfolios/recommend'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'profile_id': profileId, 'with_reason': false}),
    );
    final body = _decodeObject(response);
    final options = (body['options'] as List<dynamic>)
        .map((o) => PortfolioOption.fromJson(o as Map<String, dynamic>))
        .toList();
    final baselineJson = body['baseline'] as Map<String, dynamic>?;
    final baseline = baselineJson != null ? SinglePlan.fromJson(baselineJson) : null;
    return (options, baseline);
  }

  /// 4안의 AI 추천 이유만 따로 받는다 (느림, ~26초). 티어 이름(PortfolioTier.apiValue) ->
  /// 이유 문장.
  Future<Map<String, String>> fetchPortfolioReasons(int profileId) async {
    final response = await _client.post(
      _uri('/portfolios/reasons'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'profile_id': profileId}),
    );
    final body = _decodeObject(response);
    return (body['reasons'] as Map<String, dynamic>).cast<String, String>();
  }

  /// 지금 추천 결과 상품의 '기타' 우대조건 중 아직 안 물은 것을 질문으로 받는다.
  /// 빈 리스트면 더 물을 게 없다는 뜻 - 챗봇을 건너뛰고 바로 결과로 가면 된다.
  Future<List<EtcQuestion>> fetchEtcQuestions(int profileId) async {
    final response = await _client.post(
      _uri('/profiles/$profileId/etc-questions'),
      headers: {'Content-Type': 'application/json'},
    );
    final body = _decodeObject(response);
    return (body['questions'] as List<dynamic>)
        .map((q) => EtcQuestion.fromJson(q as Map<String, dynamic>))
        .toList();
  }

  /// '기타' 우대조건 질문의 답을 저장한다. 저장 후 recommendPortfolios 를 다시 부르면
  /// 반영된 결과가 나온다.
  Future<void> sendEtcAnswers(int profileId, List<EtcAnswerSubmission> answers) async {
    final response = await _client.post(
      _uri('/profiles/$profileId/etc-answers'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'answers': answers.map((a) => a.toJson()).toList()}),
    );
    _decodeObject(response);
  }

  /// 추천안 중 하나를 확정 가입한다. 반환값은 이후 캘린더 조회에 쓰는 portfolio_id.
  Future<int> selectPortfolio({required int profileId, required PortfolioTier tier}) async {
    final response = await _client.post(
      _uri('/portfolios'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'profile_id': profileId, 'tier': tier.apiValue}),
    );
    return _decodeObject(response)['portfolio_id'] as int;
  }

  Future<List<CalendarEvent>> getCalendar(int portfolioId) async {
    final response = await _client.get(_uri('/portfolios/$portfolioId/calendar'));
    return _decodeList(response).map((e) => CalendarEvent.fromJson(e as Map<String, dynamic>)).toList();
  }

  /// 기관(필수)·상품유형(선택, 예금/적금/예탁금)으로 실제 상품을 검색한다.
  /// 로그인 불필요. 빈 목록이면(기관이 상품 데이터에 없거나 등) 직접 입력으로
  /// 유도하면 된다.
  Future<ProductSearchResult> searchProducts({
    required String institution,
    String? productType,
  }) async {
    final uri = _uri('/products').replace(queryParameters: {
      'institution': institution,
      'product_type': ?productType,
    });
    final response = await _client.get(uri);
    return ProductSearchResult.fromJson(_decodeObject(response));
  }

  /// 로드맵 숫자(경과 개월·총 이자·현재 이자). 이 브라우저에서 만든 기록이 없으면(401) null.
  Future<RoadmapStats?> fetchRoadmap() async {
    final response = await _client.get(_uri('/users/me/roadmap'));
    if (response.statusCode == 401) return null;
    return RoadmapStats.fromJson(_decodeObject(response));
  }

  /// 지금 사용자(로그인 또는 게스트 쿠키)의 진행중 안 일정. 포트폴리오 번호를 기억하지 않아도 돼서
  /// 새로고침·로그인 뒤에도, 같은 계정이면 다른 브라우저에서도 같은 일정이 나온다.
  /// 이 브라우저에 기록이 없으면(401) 빈 목록.
  Future<List<CalendarEvent>> getMyCalendar() async {
    final response = await _client.get(_uri('/users/me/calendar'));
    if (response.statusCode == 401) return const [];
    return _decodeList(response).map((e) => CalendarEvent.fromJson(e as Map<String, dynamic>)).toList();
  }
}
