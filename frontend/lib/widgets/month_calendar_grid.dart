import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

const _weekdayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
final _gridLineColor = AppColors.lavender.withValues(alpha: 0.25);

/// 한 달치 날짜를 7열 그리드로 보여준다. 이전/다음 달 날짜는 흐리게,
/// [highlightedDate]와 같은 날은 배경을 강조해서 표시한다.
class MonthCalendarGrid extends StatelessWidget {
  final DateTime month;
  final DateTime? highlightedDate;
  final ValueChanged<DateTime>? onDateSelected;

  const MonthCalendarGrid({
    super.key,
    required this.month,
    this.highlightedDate,
    this.onDateSelected,
  });

  @override
  Widget build(BuildContext context) {
    final firstOfMonth = DateTime(month.year, month.month, 1);
    final daysInMonth = DateTime(month.year, month.month + 1, 0).day;
    // DateTime.weekday: Mon=1..Sun=7. 이 그리드는 일요일을 첫 칸으로 쓴다.
    final leadingEmptyDays = firstOfMonth.weekday % 7;
    final totalCells = ((leadingEmptyDays + daysInMonth) / 7).ceil() * 7;
    final firstGridDate =
        firstOfMonth.subtract(Duration(days: leadingEmptyDays));

    final weeks = <List<DateTime>>[];
    for (var i = 0; i < totalCells; i += 7) {
      weeks.add(List.generate(7, (j) => firstGridDate.add(Duration(days: i + j))));
    }

    return Column(
      children: [
        Row(
          children: List.generate(7, (i) {
            final isWeekend = i == 0 || i == 6;
            return Expanded(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text(
                  _weekdayLabels[i],
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontWeight: FontWeight.w600,
                    color: isWeekend ? AppColors.accent : AppColors.gray,
                  ),
                ),
              ),
            );
          }),
        ),
        Table(
          border: TableBorder.all(color: _gridLineColor, width: 1),
          children: [
            for (final week in weeks)
              TableRow(
                children: [
                  for (final date in week)
                    _DayCell(
                      date: date,
                      inCurrentMonth: date.month == month.month,
                      isHighlighted: highlightedDate != null &&
                          date.year == highlightedDate!.year &&
                          date.month == highlightedDate!.month &&
                          date.day == highlightedDate!.day,
                      onTap: onDateSelected == null
                          ? null
                          : () => onDateSelected!(date),
                    ),
                ],
              ),
          ],
        ),
      ],
    );
  }
}

class _DayCell extends StatelessWidget {
  final DateTime date;
  final bool inCurrentMonth;
  final bool isHighlighted;
  final VoidCallback? onTap;

  const _DayCell({
    required this.date,
    required this.inCurrentMonth,
    required this.isHighlighted,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final textColor = !inCurrentMonth
        ? AppColors.skyLavender
        : (date.weekday == DateTime.sunday || date.weekday == DateTime.saturday
            ? AppColors.accent
            : Colors.black87);

    return InkWell(
      onTap: onTap,
      child: Container(
        height: 72,
        padding: const EdgeInsets.all(8),
        color: isHighlighted ? AppColors.lavender.withValues(alpha: 0.3) : null,
        alignment: Alignment.topLeft,
        child: Text(
          '${date.day}',
          style: TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: textColor,
          ),
        ),
      ),
    );
  }
}
