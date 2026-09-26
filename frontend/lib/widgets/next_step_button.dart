import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 입력 단계 화면 하단의 "다음 단계" 버튼. 필수 항목이 채워지기 전에는 비활성화된다.
class NextStepButton extends StatelessWidget {
  final bool enabled;
  final VoidCallback onPressed;

  const NextStepButton({super.key, required this.enabled, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return ElevatedButton(
      onPressed: enabled ? onPressed : null,
      style: ElevatedButton.styleFrom(
        backgroundColor: AppColors.lavender,
        disabledBackgroundColor: AppColors.lavender.withValues(alpha: 0.35),
        foregroundColor: Colors.white,
        disabledForegroundColor: Colors.white,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(24),
        ),
        textStyle: const TextStyle(fontSize: 15, fontWeight: FontWeight.bold),
      ),
      child: const Text('다음 단계'),
    );
  }
}
