import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 입력 단계(1~3) 화면 상단에 쓰이는 진행 표시.
/// 현재 단계만 채워진 원 + "STEP n" 라벨로 강조하고, 나머지는 빈 원으로 표시한다.
class StepIndicator extends StatelessWidget {
  final int currentStep;
  final int totalSteps;

  const StepIndicator({
    super.key,
    required this.currentStep,
    this.totalSteps = 3,
  });

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        for (var step = 1; step <= totalSteps; step++) ...[
          if (step > 1) const _StepConnector(),
          _StepNode(step: step, isActive: step == currentStep),
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
          thickness: 1,
          color: AppColors.lavender.withValues(alpha: 0.4),
        ),
      ),
    );
  }
}

class _StepNode extends StatelessWidget {
  final int step;
  final bool isActive;

  const _StepNode({required this.step, required this.isActive});

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          width: 40,
          height: 40,
          alignment: Alignment.center,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isActive ? AppColors.lavender : Colors.white,
            border: isActive
                ? null
                : Border.all(color: AppColors.lavender.withValues(alpha: 0.4)),
          ),
          child: Text(
            '$step',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: isActive ? Colors.black87 : AppColors.gray,
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
