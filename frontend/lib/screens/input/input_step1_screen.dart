import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/onboarding_provider.dart';
import '../../router/app_router.dart';
import '../../theme/app_colors.dart';
import '../../utils/thousands_input_formatter.dart';
import '../../widgets/next_step_button.dart';
import '../../widgets/step_indicator.dart';

final _fieldBorder = OutlineInputBorder(
  borderRadius: BorderRadius.circular(14),
  borderSide: const BorderSide(color: AppColors.gray, width: 1),
);

class InputStep1Screen extends ConsumerStatefulWidget {
  const InputStep1Screen({super.key});

  @override
  ConsumerState<InputStep1Screen> createState() => _InputStep1ScreenState();
}

class _InputStep1ScreenState extends ConsumerState<InputStep1Screen> {
  late final _lumpSumController = TextEditingController(
    text: _initialText(ref.read(onboardingProvider).lumpSum),
  );
  late final _monthlySavingController = TextEditingController(
    text: _initialText(ref.read(onboardingProvider).monthlySaving),
  );
  late final _periodMonthsController = TextEditingController(
    text: _initialText(ref.read(onboardingProvider).periodMonths),
  );

  static String _initialText(int value) {
    if (value == 0) return '';
    final digits = '$value';
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i != 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }

  static int _parseAmount(String value) =>
      int.tryParse(value.replaceAll(',', '')) ?? 0;

  @override
  void dispose() {
    _lumpSumController.dispose();
    _monthlySavingController.dispose();
    _periodMonthsController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final input = ref.watch(onboardingProvider);
    final notifier = ref.read(onboardingProvider.notifier);
    final canProceed =
        input.lumpSum > 0 && input.monthlySaving > 0 && input.periodMonths > 0;

    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(24, 24, 24, 32),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              StepIndicator(
                currentStep: 1,
                onStepTap: (step) => context.go(AppRoutes.inputStep(step)),
              ),
              const SizedBox(height: 48),
              _buildHeader(),
              const SizedBox(height: 40),
              _AmountField(
                label: '목돈',
                description: '한번에 최대 얼마까지 맡길 수 있으신가요?',
                suffixText: '원',
                controller: _lumpSumController,
                onChanged: (v) => notifier.updateLumpSum(_parseAmount(v)),
              ),
              const SizedBox(height: 28),
              _AmountField(
                label: '월저축액',
                description: '매달 얼마씩 꾸준하게 저축할 계획이신가요?',
                suffixText: '원',
                controller: _monthlySavingController,
                onChanged: (v) => notifier.updateMonthlySaving(_parseAmount(v)),
              ),
              const SizedBox(height: 28),
              _AmountField(
                label: '기간',
                description: '최대 몇 개월까지 저축해도 괜찮을까요?',
                suffixText: '개월',
                controller: _periodMonthsController,
                onChanged: (v) => notifier.updatePeriodMonths(_parseAmount(v)),
              ),
              const SizedBox(height: 32),
              Align(
                alignment: Alignment.centerRight,
                child: NextStepButton(
                  enabled: canProceed,
                  onPressed: () => context.push(AppRoutes.inputStep2),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() {
    return RichText(
      textAlign: TextAlign.center,
      text: const TextSpan(
        style: TextStyle(fontSize: 16, height: 1.5, color: AppColors.darkGray),
        children: [
          TextSpan(
            text: 'OO님',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          TextSpan(text: '을 위한 '),
          TextSpan(
            text: '정확한 상품 추천',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          TextSpan(text: '을 위해\n아래 항목들을 입력해주세요.'),
        ],
      ),
    );
  }
}

/// "목돈 / 월저축액 / 기간" 입력 한 항목을 이루는 라벨 + 설명 + 숫자 입력 필드.
class _AmountField extends StatelessWidget {
  final String label;
  final String description;
  final String suffixText;
  final TextEditingController controller;
  final ValueChanged<String> onChanged;

  const _AmountField({
    required this.label,
    required this.description,
    required this.suffixText,
    required this.controller,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: const TextStyle(
            fontSize: 20,
            fontWeight: FontWeight.bold,
            color: AppColors.labelPurple,
          ),
        ),
        const SizedBox(height: 6),
        Text(
          description,
          style: const TextStyle(fontSize: 13, color: AppColors.gray),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: controller,
          keyboardType: TextInputType.number,
          inputFormatters: [ThousandsInputFormatter()],
          onChanged: onChanged,
          textAlign: TextAlign.right,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppColors.darkGray,
          ),
          decoration: InputDecoration(
            // suffixText는 라벨이 플로팅될 때(포커스/입력값 있음)만 보이므로,
            // 빈 상태에서도 단위가 항상 보이도록 suffixIcon을 대신 쓴다.
            suffixIcon: Padding(
              padding: const EdgeInsets.only(right: 16),
              child: Align(
                alignment: Alignment.centerRight,
                widthFactor: 1,
                child: Text(
                  suffixText,
                  style: const TextStyle(fontSize: 15, color: AppColors.gray),
                ),
              ),
            ),
            suffixIconConstraints: const BoxConstraints(
              minWidth: 0,
              minHeight: 0,
            ),
            filled: true,
            fillColor: Colors.white,
            contentPadding: const EdgeInsets.symmetric(
              horizontal: 16,
              vertical: 14,
            ),
            border: _fieldBorder,
            enabledBorder: _fieldBorder,
            focusedBorder: _fieldBorder,
          ),
        ),
      ],
    );
  }
}
