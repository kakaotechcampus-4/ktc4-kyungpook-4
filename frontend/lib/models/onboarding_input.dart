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
      specialHouseholdTypes.isNotEmpty;
}
