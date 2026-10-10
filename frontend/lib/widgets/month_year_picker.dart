import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

const _monthLabels = [
  '1월', '2월', '3월', '4월', '5월', '6월',
  '7월', '8월', '9월', '10월', '11월', '12월',
];

/// 연도를 앞뒤로 넘기면서 월을 고르는 다이얼로그. 고르면 그 달의 1일을
/// 가리키는 DateTime을 반환하고, 취소하면 null을 반환한다.
Future<DateTime?> showMonthYearPicker({
  required BuildContext context,
  required DateTime initialMonth,
}) {
  return showDialog<DateTime>(
    context: context,
    builder: (context) => _MonthYearPickerDialog(initialMonth: initialMonth),
  );
}

class _MonthYearPickerDialog extends StatefulWidget {
  final DateTime initialMonth;

  const _MonthYearPickerDialog({required this.initialMonth});

  @override
  State<_MonthYearPickerDialog> createState() => _MonthYearPickerDialogState();
}

class _MonthYearPickerDialogState extends State<_MonthYearPickerDialog> {
  late int _year = widget.initialMonth.year;

  @override
  Widget build(BuildContext context) {
    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                IconButton(
                  onPressed: () => setState(() => _year--),
                  icon: const Icon(Icons.chevron_left),
                ),
                SizedBox(
                  width: 80,
                  child: Text(
                    '$_year년',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  onPressed: () => setState(() => _year++),
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
            const SizedBox(height: 8),
            GridView.count(
              shrinkWrap: true,
              crossAxisCount: 3,
              mainAxisSpacing: 8,
              crossAxisSpacing: 8,
              childAspectRatio: 1.6,
              children: [
                for (var month = 1; month <= 12; month++)
                  _MonthCell(
                    label: _monthLabels[month - 1],
                    isSelected: _year == widget.initialMonth.year &&
                        month == widget.initialMonth.month,
                    onTap: () => Navigator.of(context).pop(DateTime(_year, month)),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _MonthCell extends StatelessWidget {
  final String label;
  final bool isSelected;
  final VoidCallback onTap;

  const _MonthCell({
    required this.label,
    required this.isSelected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Container(
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: isSelected ? AppColors.lavender : Colors.grey.shade100,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
            color: isSelected ? Colors.white : Colors.black87,
          ),
        ),
      ),
    );
  }
}
