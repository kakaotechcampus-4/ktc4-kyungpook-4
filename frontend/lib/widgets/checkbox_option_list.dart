import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 체크박스 다중 선택 리스트. [noneOption]을 선택하면 나머지가 모두 해제되고,
/// 반대로 다른 항목을 선택하면 [noneOption]이 자동으로 해제된다.
class CheckboxOptionList extends StatelessWidget {
  final List<String> options;
  final List<String> selected;
  final ValueChanged<String> onToggle;
  final String noneOption;

  const CheckboxOptionList({
    super.key,
    required this.options,
    required this.selected,
    required this.onToggle,
    required this.noneOption,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        for (final option in options) ...[
          if (option != options.first) const SizedBox(height: 8),
          _CheckboxRow(
            label: option,
            checked: selected.contains(option),
            onTap: () => onToggle(option),
          ),
        ],
      ],
    );
  }
}

class _CheckboxRow extends StatelessWidget {
  final String label;
  final bool checked;
  final VoidCallback onTap;

  const _CheckboxRow({
    required this.label,
    required this.checked,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: checked ? AppColors.lavender.withValues(alpha: 0.2) : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: checked ? AppColors.lavender : Colors.grey.shade300,
            width: checked ? 1.5 : 1,
          ),
        ),
        child: Row(
          children: [
            Expanded(
              child: Text(
                label,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: checked ? FontWeight.w600 : FontWeight.normal,
                  color: checked ? AppColors.labelPurple : Colors.black87,
                ),
              ),
            ),
            Icon(
              checked ? Icons.check_box : Icons.check_box_outline_blank,
              color: checked ? AppColors.lavender : Colors.grey.shade400,
            ),
          ],
        ),
      ),
    );
  }
}
