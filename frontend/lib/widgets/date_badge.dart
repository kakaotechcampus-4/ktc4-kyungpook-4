import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

const _monthAbbreviations = [
  'JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
  'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC',
];

/// "다가오는 일정" 목록에서 각 항목 왼쪽에 붙는 월/일 표시.
/// 배경 배지가 아니라 얇은 강조 바 + 텍스트 조합이다.
class DateBadge extends StatelessWidget {
  final DateTime date;

  const DateBadge({super.key, required this.date});

  @override
  Widget build(BuildContext context) {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            width: 4,
            decoration: BoxDecoration(
              color: AppColors.lavender,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          const SizedBox(width: 14),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '${date.day}',
                style: const TextStyle(
                  color: AppColors.lavender,
                  fontSize: 22,
                  fontWeight: FontWeight.bold,
                ),
              ),
              Text(
                _monthAbbreviations[date.month - 1],
                style: const TextStyle(
                  color: AppColors.lavender,
                  fontSize: 13,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
