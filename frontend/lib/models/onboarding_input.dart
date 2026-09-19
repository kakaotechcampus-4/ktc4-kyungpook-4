class OnboardingInput {
  final int lumpSum;
  final int monthlySaving;
  final int periodMonths;

  const OnboardingInput({
    this.lumpSum = 0,
    this.monthlySaving = 0,
    this.periodMonths = 0,
  });

  OnboardingInput copyWith({
    int? lumpSum,
    int? monthlySaving,
    int? periodMonths,
  }) {
    return OnboardingInput(
      lumpSum: lumpSum ?? this.lumpSum,
      monthlySaving: monthlySaving ?? this.monthlySaving,
      periodMonths: periodMonths ?? this.periodMonths,
    );
  }
}
