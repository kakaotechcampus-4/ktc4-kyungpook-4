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

  void toggleCurrentBank(String bank) {
    final banks = List<String>.from(state.currentBanks);
    final wasSelected = banks.remove(bank);
    if (!wasSelected) banks.add(bank);
    // 주거래은행은 보유 은행 중에서만 고를 수 있으니, 방금 뺀 은행이 주거래은행이었다면
    // 같이 비운다 (다시 보유 목록에 없는 은행을 주거래로 들고 있지 않게).
    final mainBank = wasSelected && state.mainBank == bank ? '' : state.mainBank;
    state = state.copyWith(currentBanks: banks, mainBank: mainBank);
  }

  void updateMainBank(String value) =>
      state = state.copyWith(mainBank: value);

  void updateBirthYear(String value) =>
      state = state.copyWith(birthYear: value);

  void updateBirthMonth(String value) =>
      state = state.copyWith(birthMonth: value);

  void updateBirthDay(String value) => state = state.copyWith(birthDay: value);

  void updateSalaryAccountTransferable(String value) =>
      state = state.copyWith(salaryAccountTransferable: value);

  void updateAutoTransferMovable(String value) =>
      state = state.copyWith(autoTransferMovable: value);

  void updateSavingsAutoTransferPossible(String value) =>
      state = state.copyWith(savingsAutoTransferPossible: value);

  void updatePensionAccountTransferable(String value) =>
      state = state.copyWith(pensionAccountTransferable: value);

  void updateCooperativeInsuranceJoinStatus(String value) =>
      state = state.copyWith(cooperativeInsuranceJoinStatus: value);

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

  void toggleCooperativeJoinChoice(String option, {required String noneOption}) {
    final current = List<String>.from(state.cooperativeJoinChoices);
    if (option == noneOption) {
      state = state.copyWith(
        cooperativeJoinChoices: current.contains(noneOption) ? [] : [noneOption],
      );
      return;
    }
    current.remove(noneOption);
    if (!current.remove(option)) current.add(option);
    state = state.copyWith(cooperativeJoinChoices: current);
  }

  void updateMutualFinanceTaxExemptEligible(String value) =>
      state = state.copyWith(mutualFinanceTaxExemptEligible: value);

  void updateMutualFinanceExistingAmountText(String value) => state = state.copyWith(
        mutualFinanceExistingAmountText: value,
        mutualFinanceExistingAmountUnknown: false,
      );

  void setMutualFinanceExistingAmountUnknown() => state = state.copyWith(
        mutualFinanceExistingAmountText: '',
        mutualFinanceExistingAmountUnknown: true,
      );

  void updateAdditionalNote(String value) =>
      state = state.copyWith(additionalNote: value);
}

final onboardingProvider =
    NotifierProvider<OnboardingNotifier, OnboardingInput>(
  OnboardingNotifier.new,
);
