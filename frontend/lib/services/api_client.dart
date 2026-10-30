import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/calendar_event.dart';
import '../models/onboarding_input.dart';
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

    final response = await http.post(
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
