import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/auth_provider.dart';
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

/// 저축 기간은 60개월(5년)까지만 받는다(60개월은 가능, 그 초과는 불가).
/// 상품 최대 기간이 36개월 안팎이라 그 이상은 추천해줄 안이 없다.
const _maxPeriodMonths = 60;

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
    final isPeriodTooLong = input.periodMonths > _maxPeriodMonths;
    final canProceed = input.lumpSum > 0 &&
        input.monthlySaving > 0 &&
        input.periodMonths > 0 &&
        !isPeriodTooLong;

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
              _buildHeader(ref.watch(userDisplayNameProvider)),
              const SizedBox(height: 24),
              const _DepositSavingsHint(),
              const SizedBox(height: 32),
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
                errorText: isPeriodTooLong
                    ? '$_maxPeriodMonths개월 이하로 입력해주세요'
                    : null,
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

  Widget _buildHeader(String name) {
    return RichText(
      textAlign: TextAlign.center,
      text: TextSpan(
        style: const TextStyle(fontSize: 16, height: 1.5, color: AppColors.darkGray),
        children: [
          TextSpan(
            text: '$name님',
            style: const TextStyle(fontWeight: FontWeight.bold),
          ),
          const TextSpan(text: '을 위한 '),
          const TextSpan(
            text: '정확한 상품 추천',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          const TextSpan(text: '을 위해\n아래 항목들을 입력해주세요.'),
        ],
      ),
    );
  }
}

/// 처음 쓰는 사람은 목돈/월저축액이 왜 둘 다 필요한지 헷갈릴 수 있어,
/// 목돈은 예금을 월저축액은 적금을 찾는 데 쓰인다는 걸 짧게 짚어준다.
class _DepositSavingsHint extends StatelessWidget {
  const _DepositSavingsHint();

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppColors.lavenderPale,
        borderRadius: BorderRadius.circular(12),
      ),
      child: const Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.info_outline, size: 16, color: AppColors.labelPurple),
          SizedBox(width: 8),
          Expanded(
            child: Text(
              '목돈은 예금 상품을, 월저축액은 적금 상품을 찾는 데 활용돼요.',
              style: TextStyle(fontSize: 12, color: AppColors.darkGray, height: 1.4),
            ),
          ),
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
  final String? errorText;
  final TextEditingController controller;
  final ValueChanged<String> onChanged;

  const _AmountField({
    required this.label,
    required this.description,
    required this.suffixText,
    this.errorText,
    required this.controller,
    required this.onChanged,
  });

  @override
  Widget build(BuildContext context) {
    final isInvalid = errorText != null;
    final errorBorder = OutlineInputBorder(
      borderRadius: BorderRadius.circular(14),
      borderSide: BorderSide(color: Colors.red.shade400, width: 1),
    );

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
            border: isInvalid ? errorBorder : _fieldBorder,
            enabledBorder: isInvalid ? errorBorder : _fieldBorder,
            focusedBorder: isInvalid ? errorBorder : _fieldBorder,
          ),
        ),
        if (errorText != null) ...[
          const SizedBox(height: 8),
          Text(
            errorText!,
            style: TextStyle(fontSize: 12, color: Colors.red.shade400),
          ),
        ],
      ],
    );
  }
}
