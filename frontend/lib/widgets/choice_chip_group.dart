import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 단일 선택 옵션 하나("있어요", "잘 모르겠어요" 등)를 나타내는 칩.
/// [ChoiceChipGroup] 안에서 쓰이거나, Q12처럼 단독으로도 쓰인다.
class OptionChip extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback onTap;

  const OptionChip({
    super.key,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 8),
        decoration: BoxDecoration(
          color: selected ? AppColors.lavender.withValues(alpha: 0.35) : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(
            color: selected ? AppColors.lavender : Colors.grey.shade300,
            width: selected ? 1.5 : 1,
          ),
        ),
        child: Text(
          label,
          textAlign: TextAlign.center,
          style: TextStyle(
            fontSize: 14,
            fontWeight: FontWeight.w600,
            color: selected ? AppColors.labelPurple : Colors.black87,
          ),
        ),
      ),
    );
  }
}

/// 옵션들을 [itemsPerRow]개씩 한 줄에 배치하는 단일 선택 칩 그룹.
/// 3개짜리 예/아니오/모름 질문과 6개짜리 카드 사용액 질문에 공통으로 쓰인다.
class ChoiceChipGroup extends StatelessWidget {
  final List<String> options;
  final String selected;
  final ValueChanged<String> onSelected;
  final int itemsPerRow;

  const ChoiceChipGroup({
    super.key,
    required this.options,
    required this.selected,
    required this.onSelected,
    this.itemsPerRow = 3,
  });

  @override
  Widget build(BuildContext context) {
    final rows = <Widget>[];
    for (var i = 0; i < options.length; i += itemsPerRow) {
      final rowOptions = options.skip(i).take(itemsPerRow).toList();
      if (rows.isNotEmpty) rows.add(const SizedBox(height: 8));
      rows.add(
        Row(
          children: [
            for (final option in rowOptions) ...[
              if (option != rowOptions.first) const SizedBox(width: 8),
              Expanded(
                child: OptionChip(
                  label: option,
                  selected: option == selected,
                  onTap: () => onSelected(option),
                ),
              ),
            ],
          ],
        ),
      );
    }
    return Column(children: rows);
  }
}
