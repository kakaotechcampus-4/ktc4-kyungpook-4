import 'package:flutter/material.dart';

import '../theme/app_colors.dart';

/// 날짜 칸 아래에 찍는 일정 표시 점의 종류. 색은 범례(CalendarMarkerLegend)와 같다.
enum CalendarMarker {
  payment('납입', AppColors.labelPurple),
  maturity('만기', AppColors.accent),
  manual('직접 기록', AppColors.darkGray);

  const CalendarMarker(this.label, this.color);
  final String label;
  final Color color;
}

/// 시각을 뺀 날짜만으로 비교하기 위한 키.
DateTime calendarDayKey(DateTime d) => DateTime(d.year, d.month, d.day);

const _weekdayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
final _gridLineColor = AppColors.lavender.withValues(alpha: 0.25);

/// 한 달치 날짜를 7열 그리드로 보여준다. 이전/다음 달 날짜는 흐리게,
/// [highlightedDate]와 같은 날은 배경을 강조해서 표시한다.
class MonthCalendarGrid extends StatelessWidget {
  final DateTime month;
  final DateTime? highlightedDate;
  final ValueChanged<DateTime>? onDateSelected;

  /// 날짜(calendarDayKey) -> 그날 있는 일정 종류. 칸 아래에 색 점으로 표시한다.
  final Map<DateTime, Set<CalendarMarker>> markers;

  const MonthCalendarGrid({
    super.key,
    required this.month,
    this.highlightedDate,
    this.onDateSelected,
    this.markers = const {},
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
                      markers: markers[calendarDayKey(date)] ?? const {},
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
  final Set<CalendarMarker> markers;
  final VoidCallback? onTap;

  const _DayCell({
    required this.date,
    required this.inCurrentMonth,
    required this.isHighlighted,
    required this.markers,
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
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${date.day}',
              style: TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: textColor,
              ),
            ),
            const Spacer(),
            if (markers.isNotEmpty)
              Row(
                children: [
                  // enum 순서(납입 → 만기 → 직접 기록)로 늘 같은 자리에 찍는다
                  for (final marker in CalendarMarker.values)
                    if (markers.contains(marker))
                      Container(
                        width: 7,
                        height: 7,
                        margin: const EdgeInsets.only(right: 3),
                        decoration: BoxDecoration(
                          // 이전·다음 달 칸은 날짜처럼 흐리게
                          color: inCurrentMonth
                              ? marker.color
                              : marker.color.withValues(alpha: 0.35),
                          shape: BoxShape.circle,
                        ),
                      ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}

/// 달력 아래에 두는 점 색 범례.
class CalendarMarkerLegend extends StatelessWidget {
  const CalendarMarkerLegend({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        for (final marker in CalendarMarker.values) ...[
          const SizedBox(width: 12),
          Container(
            width: 7,
            height: 7,
            decoration: BoxDecoration(color: marker.color, shape: BoxShape.circle),
          ),
          const SizedBox(width: 4),
          Text(marker.label, style: const TextStyle(fontSize: 12, color: AppColors.gray)),
        ],
      ],
    );
  }
}
