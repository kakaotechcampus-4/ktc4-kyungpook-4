import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/onboarding_input.dart';

class OnboardingNotifier extends Notifier<OnboardingInput> {
  @override
  OnboardingInput build() => const OnboardingInput();

  void updateLumpSum(int value) => state = state.copyWith(lumpSum: value);

  void updateMonthlySaving(int value) =>
      state = state.copyWith(monthlySaving: value);

  void updatePeriodMonths(int value) =>
      state = state.copyWith(periodMonths: value);

  void updateEarlyWithdrawalPossibility(String value) =>
      state = state.copyWith(earlyWithdrawalPossibility: value);

  void toggleCurrentBank(String bank) {
    final banks = List<String>.from(state.currentBanks);
    if (!banks.remove(bank)) banks.add(bank);
    state = state.copyWith(currentBanks: banks);
  }

  void updateMainBank(String value) =>
      state = state.copyWith(mainBank: value);

  void updateResidenceSido(String value) => state = state.copyWith(
        residenceSido: value,
        residenceSigungu: '',
      );

  void updateResidenceSigungu(String value) =>
      state = state.copyWith(residenceSigungu: value);

  void updateBirthYear(String value) =>
      state = state.copyWith(birthYear: value);

  void updateBirthMonth(String value) =>
      state = state.copyWith(birthMonth: value);

  void updateBirthDay(String value) => state = state.copyWith(birthDay: value);

  void updateSalaryAccountTransferable(String value) =>
      state = state.copyWith(salaryAccountTransferable: value);

  void updateAutoTransferMovable(String value) =>
      state = state.copyWith(autoTransferMovable: value);

  void updateMonthlyCardSpending(String value) =>
      state = state.copyWith(monthlyCardSpending: value);

  void updateMarketingConsent(String value) =>
      state = state.copyWith(marketingConsent: value);

  void updateCanInstallBankApp(String value) =>
      state = state.copyWith(canInstallBankApp: value);

  void toggleTaxExemptEligibility(String option, {required String noneOption}) {
    final current = List<String>.from(state.taxExemptEligibility);
    if (option == noneOption) {
      state = state.copyWith(
        taxExemptEligibility: current.contains(noneOption) ? [] : [noneOption],
      );
      return;
    }
    current.remove(noneOption);
    if (!current.remove(option)) current.add(option);
    state = state.copyWith(taxExemptEligibility: current);
  }

  void updateExistingTaxExemptAmountText(String value) => state = state.copyWith(
        existingTaxExemptAmountText: value,
        existingTaxExemptAmountUnknown: false,
      );

  void setExistingTaxExemptAmountUnknown() => state = state.copyWith(
        existingTaxExemptAmountText: '',
        existingTaxExemptAmountUnknown: true,
      );

  void toggleSpecialHouseholdType(String option, {required String noneOption}) {
    final current = List<String>.from(state.specialHouseholdTypes);
    if (option == noneOption) {
      state = state.copyWith(
        specialHouseholdTypes: current.contains(noneOption) ? [] : [noneOption],
      );
      return;
    }
    current.remove(noneOption);
    if (!current.remove(option)) current.add(option);
    state = state.copyWith(specialHouseholdTypes: current);
  }

  void updateCooperativeMembershipStatus(String value) =>
      state = state.copyWith(cooperativeMembershipStatus: value);
}

final onboardingProvider =
    NotifierProvider<OnboardingNotifier, OnboardingInput>(
  OnboardingNotifier.new,
);
