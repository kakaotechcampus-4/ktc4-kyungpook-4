class OnboardingInput {
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
  final String existingTaxExemptAmountText;
  final bool existingTaxExemptAmountUnknown;
  final List<String> specialHouseholdTypes;

  // Step 3
  final String cooperativeMembershipStatus;

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
    this.existingTaxExemptAmountText = '',
    this.existingTaxExemptAmountUnknown = false,
    this.specialHouseholdTypes = const [],
    this.cooperativeMembershipStatus = '',
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
    String? existingTaxExemptAmountText,
    bool? existingTaxExemptAmountUnknown,
    List<String>? specialHouseholdTypes,
    String? cooperativeMembershipStatus,
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
      existingTaxExemptAmountText:
          existingTaxExemptAmountText ?? this.existingTaxExemptAmountText,
      existingTaxExemptAmountUnknown:
          existingTaxExemptAmountUnknown ?? this.existingTaxExemptAmountUnknown,
      specialHouseholdTypes: specialHouseholdTypes ?? this.specialHouseholdTypes,
      cooperativeMembershipStatus:
          cooperativeMembershipStatus ?? this.cooperativeMembershipStatus,
    );
  }

  bool get isStep2Complete =>
      earlyWithdrawalPossibility.isNotEmpty &&
      currentBanks.isNotEmpty &&
      mainBank.isNotEmpty &&
      residenceSido.isNotEmpty &&
      residenceSigungu.isNotEmpty &&
      birthYear.isNotEmpty &&
      birthMonth.isNotEmpty &&
      birthDay.isNotEmpty &&
      salaryAccountTransferable.isNotEmpty &&
      autoTransferMovable.isNotEmpty &&
      monthlyCardSpending.isNotEmpty &&
      marketingConsent.isNotEmpty &&
      canInstallBankApp.isNotEmpty &&
      taxExemptEligibility.isNotEmpty &&
      (existingTaxExemptAmountUnknown || existingTaxExemptAmountText.isNotEmpty) &&
      specialHouseholdTypes.isNotEmpty;
}
