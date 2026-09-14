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
}

final onboardingProvider =
    NotifierProvider<OnboardingNotifier, OnboardingInput>(
  OnboardingNotifier.new,
);
