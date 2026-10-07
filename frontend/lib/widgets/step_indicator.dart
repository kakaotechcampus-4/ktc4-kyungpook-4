import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 입력 단계(1~3) 화면 상단에 쓰이는 진행 표시.
/// 현재 단계까지의 원이 순서대로 하나씩 채워지고(1→2→3 색이 각각 다름),
/// 아직 안 지난 단계는 빈 원으로 표시한다. 현재 단계가 아닌 원을 탭하면
/// (이전이든 다음이든) [onStepTap]으로 그 단계 번호를 알려준다
/// (입력값은 전역 상태에 있어서 어느 방향으로 이동해도 그대로 남아있다).
class StepIndicator extends StatelessWidget {
  final int currentStep;
  final int totalSteps;
  final ValueChanged<int>? onStepTap;

  const StepIndicator({
    super.key,
    required this.currentStep,
    this.totalSteps = 3,
    this.onStepTap,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var step = 1; step <= totalSteps; step++) ...[
          if (step > 1) const _StepConnector(),
          _StepNode(
            step: step,
            isFilled: step <= currentStep,
            isActive: step == currentStep,
            onTap: step != currentStep && onStepTap != null
                ? () => onStepTap!(step)
                : null,
          ),
        ],
      ],
    );
  }
}

class _StepConnector extends StatelessWidget {
  const _StepConnector();

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 19, left: 4, right: 4),
      child: SizedBox(
        width: 32,
        child: Divider(
          height: 1,
          thickness: 0.7,
          color: AppColors.lineGray,
        ),
      ),
    );
  }
}

class _StepNode extends StatelessWidget {
  static const _fillColors = [
    AppColors.lavenderPale,
    AppColors.lavenderLight,
    AppColors.skyLavender,
  ];

  final int step;
  final bool isFilled;
  final bool isActive;
  final VoidCallback? onTap;

  const _StepNode({
    required this.step,
    required this.isFilled,
    required this.isActive,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final fillColor = _fillColors[(step - 1) % _fillColors.length];

    return Column(
      children: [
        InkWell(
          onTap: onTap,
          customBorder: const CircleBorder(),
          child: Container(
            width: 40,
            height: 40,
            alignment: Alignment.center,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: isFilled ? fillColor : Colors.white,
              border: isFilled ? null : Border.all(color: AppColors.lineGray),
            ),
            child: Text(
              '$step',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: isFilled ? AppColors.darkGray : AppColors.gray,
              ),
            ),
          ),
        ),
        if (isActive) ...[
          const SizedBox(height: 6),
          Text(
            'STEP $step',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppColors.lavender,
            ),
          ),
        ],
      ],
    );
  }
}
