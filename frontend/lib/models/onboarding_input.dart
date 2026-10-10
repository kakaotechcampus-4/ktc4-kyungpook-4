class OnboardingInput {
  // 실제 상품 데이터(ai/output/erd) 기준 상한. product_option.period_months는
  // 1~60개월 범위(최댓값 60)이고, product.amount_cap은 대부분 10억원 이하다.
  // 이 범위를 벗어나는 입력은 어떤 상품으로도 추천할 수 없으므로 미리 막는다.
  static const maxLumpSum = 1000000; // 천원 단위 = 10억원
  static const maxMonthlySaving = 10000; // 천원 단위 = 1천만원
  static const maxPeriodMonths = 60; // 개월

  final int lumpSum;
  final int monthlySaving;
  final int periodMonths;

  // Step 2
  final String earlyWithdrawalPossibility;
  final List<String> currentBanks;
  final String mainBank;
  final String residenceSido;
  final String residenceSigungu;
  final String birthYear;
  final String birthMonth;
  final String birthDay;
  final String salaryAccountTransferable;
  final String autoTransferMovable;
  final String monthlyCardSpending;
  final String marketingConsent;
  final String canInstallBankApp;
  final List<String> taxExemptEligibility;
  final List<String> specialHouseholdTypes;

  // Step 3
  final String cooperativeMembershipStatus;
  final List<String> cooperativeJoinChoices;
  final String mutualFinanceTaxExemptEligible;
  final String mutualFinanceExistingAmountText;
  final bool mutualFinanceExistingAmountUnknown;
  final String additionalNote;

  const OnboardingInput({
    this.lumpSum = 0,
    this.monthlySaving = 0,
    this.periodMonths = 0,
    this.earlyWithdrawalPossibility = '',
    this.currentBanks = const [],
    this.mainBank = '',
    this.residenceSido = '',
    this.residenceSigungu = '',
    this.birthYear = '',
    this.birthMonth = '',
    this.birthDay = '',
    this.salaryAccountTransferable = '',
    this.autoTransferMovable = '',
    this.monthlyCardSpending = '',
    this.marketingConsent = '',
    this.canInstallBankApp = '',
    this.taxExemptEligibility = const [],
    this.specialHouseholdTypes = const [],
    this.cooperativeMembershipStatus = '',
    this.cooperativeJoinChoices = const [],
    this.mutualFinanceTaxExemptEligible = '',
    this.mutualFinanceExistingAmountText = '',
    this.mutualFinanceExistingAmountUnknown = false,
    this.additionalNote = '',
  });

  OnboardingInput copyWith({
    int? lumpSum,
    int? monthlySaving,
    int? periodMonths,
    String? earlyWithdrawalPossibility,
    List<String>? currentBanks,
    String? mainBank,
    String? residenceSido,
    String? residenceSigungu,
    String? birthYear,
    String? birthMonth,
    String? birthDay,
    String? salaryAccountTransferable,
    String? autoTransferMovable,
    String? monthlyCardSpending,
    String? marketingConsent,
    String? canInstallBankApp,
    List<String>? taxExemptEligibility,
    List<String>? specialHouseholdTypes,
    String? cooperativeMembershipStatus,
    List<String>? cooperativeJoinChoices,
    String? mutualFinanceTaxExemptEligible,
    String? mutualFinanceExistingAmountText,
    bool? mutualFinanceExistingAmountUnknown,
    String? additionalNote,
  }) {
    return OnboardingInput(
      lumpSum: lumpSum ?? this.lumpSum,
      monthlySaving: monthlySaving ?? this.monthlySaving,
      periodMonths: periodMonths ?? this.periodMonths,
      earlyWithdrawalPossibility:
          earlyWithdrawalPossibility ?? this.earlyWithdrawalPossibility,
      currentBanks: currentBanks ?? this.currentBanks,
      mainBank: mainBank ?? this.mainBank,
      residenceSido: residenceSido ?? this.residenceSido,
      residenceSigungu: residenceSigungu ?? this.residenceSigungu,
      birthYear: birthYear ?? this.birthYear,
      birthMonth: birthMonth ?? this.birthMonth,
      birthDay: birthDay ?? this.birthDay,
      salaryAccountTransferable:
          salaryAccountTransferable ?? this.salaryAccountTransferable,
      autoTransferMovable: autoTransferMovable ?? this.autoTransferMovable,
      monthlyCardSpending: monthlyCardSpending ?? this.monthlyCardSpending,
      marketingConsent: marketingConsent ?? this.marketingConsent,
      canInstallBankApp: canInstallBankApp ?? this.canInstallBankApp,
      taxExemptEligibility: taxExemptEligibility ?? this.taxExemptEligibility,
      specialHouseholdTypes: specialHouseholdTypes ?? this.specialHouseholdTypes,
      cooperativeMembershipStatus:
          cooperativeMembershipStatus ?? this.cooperativeMembershipStatus,
      cooperativeJoinChoices: cooperativeJoinChoices ?? this.cooperativeJoinChoices,
      mutualFinanceTaxExemptEligible:
          mutualFinanceTaxExemptEligible ?? this.mutualFinanceTaxExemptEligible,
      mutualFinanceExistingAmountText: mutualFinanceExistingAmountText ??
          this.mutualFinanceExistingAmountText,
      mutualFinanceExistingAmountUnknown: mutualFinanceExistingAmountUnknown ??
          this.mutualFinanceExistingAmountUnknown,
      additionalNote: additionalNote ?? this.additionalNote,
    );
  }

  bool get isStep1Complete =>
      lumpSum > 0 &&
      lumpSum <= maxLumpSum &&
      monthlySaving > 0 &&
      monthlySaving <= maxMonthlySaving &&
      periodMonths > 0 &&
      periodMonths <= maxPeriodMonths;

  /// 년/월/일이 실제 달력에 존재하는 날짜를 이루는지 확인한다.
  /// (예: 13월, 2월 30일, 자리수가 덜 채워진 연도 등은 전부 false)
  bool get isBirthDateValid {
    if (birthYear.length != 4 || birthMonth.isEmpty || birthDay.isEmpty) {
      return false;
    }
    final year = int.tryParse(birthYear);
    final month = int.tryParse(birthMonth);
    final day = int.tryParse(birthDay);
    if (year == null || month == null || day == null) return false;
    if (year < 1900 || year > DateTime.now().year) return false;
    if (month < 1 || month > 12) return false;
    if (day < 1 || day > _daysInMonth(year, month)) return false;
    return true;
  }

  static int _daysInMonth(int year, int month) {
    if (month == 2) {
      final isLeapYear =
          (year % 4 == 0 && year % 100 != 0) || year % 400 == 0;
      return isLeapYear ? 29 : 28;
    }
    const thirtyDayMonths = {4, 6, 9, 11};
    return thirtyDayMonths.contains(month) ? 30 : 31;
  }

  bool get isStep2Complete =>
      earlyWithdrawalPossibility.isNotEmpty &&
      currentBanks.isNotEmpty &&
      mainBank.isNotEmpty &&
      residenceSido.isNotEmpty &&
      residenceSigungu.isNotEmpty &&
      isBirthDateValid &&
      salaryAccountTransferable.isNotEmpty &&
      autoTransferMovable.isNotEmpty &&
      monthlyCardSpending.isNotEmpty &&
      marketingConsent.isNotEmpty &&
      canInstallBankApp.isNotEmpty &&
      taxExemptEligibility.isNotEmpty &&
      specialHouseholdTypes.isNotEmpty;
}
