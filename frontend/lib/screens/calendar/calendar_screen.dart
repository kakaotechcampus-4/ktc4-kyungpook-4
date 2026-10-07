import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/calendar_event.dart';
import '../../models/manual_product_entry.dart';
import '../../providers/calendar_provider.dart';
import '../../providers/manual_entry_provider.dart';
import '../../router/app_router.dart';
import '../../widgets/manual_entry_tile.dart';
import '../../widgets/month_calendar_grid.dart';
import '../../widgets/month_year_picker.dart';
import '../../widgets/primary_button.dart';
import '../../widgets/product_entry_form.dart';
import '../../widgets/upcoming_event_tile.dart';

class CalendarScreen extends ConsumerStatefulWidget {
  const CalendarScreen({super.key});

  @override
  ConsumerState<CalendarScreen> createState() => _CalendarScreenState();
}

class _CalendarScreenState extends ConsumerState<CalendarScreen> {
  late DateTime _selectedDate = DateTime.now();
  late DateTime _displayedMonth =
      DateTime(DateTime.now().year, DateTime.now().month);

  void _goToPreviousMonth() {
    setState(() {
      _displayedMonth = DateTime(_displayedMonth.year, _displayedMonth.month - 1);
    });
  }

  void _goToNextMonth() {
    setState(() {
      _displayedMonth = DateTime(_displayedMonth.year, _displayedMonth.month + 1);
    });
  }

  Future<void> _openMonthYearPicker() async {
    final picked = await showMonthYearPicker(
      context: context,
      initialMonth: _displayedMonth,
    );
    if (picked != null) setState(() => _displayedMonth = picked);
  }

  void _openEntrySheet(DateTime date) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (sheetContext) => Padding(
        padding: EdgeInsets.only(
          left: 24,
          right: 24,
          top: 24,
          bottom: MediaQuery.of(sheetContext).viewInsets.bottom + 24,
        ),
        child: SingleChildScrollView(
          child: ProductEntryForm(
            initialDate: date,
            onSubmit: (entry) {
              ref.read(manualEntryProvider.notifier).add(entry);
              Navigator.of(sheetContext).pop();
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('상품 정보를 기록했어요.')),
              );
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final eventsAsync = ref.watch(upcomingEventsProvider);
    final manualEntries = ref.watch(manualEntryProvider);

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            Align(
              alignment: Alignment.topRight,
              child: Padding(
                padding: const EdgeInsets.fromLTRB(16, 8, 16, 0),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      onPressed: () => context.push(AppRoutes.roadmap),
                      icon: const Icon(Icons.route_outlined),
                    ),
                    IconButton(
                      onPressed: _openMonthYearPicker,
                      icon: const Icon(Icons.calendar_month_outlined),
                    ),
                  ],
                ),
              ),
            ),
            Row(
              children: [
                IconButton(
                  onPressed: _goToPreviousMonth,
                  icon: const Icon(Icons.chevron_left),
                ),
                // 화살표는 항상 양쪽 끝에 고정하고, 그 사이 공간 안에서만
                // 글자를 가운데 정렬한다. "1월"/"10월"처럼 글자 수가 달라도
                // 화살표 위치가 글자 너비에 따라 움직이지 않는다.
                Expanded(
                  child: Text(
                    '${_displayedMonth.year}년 ${_displayedMonth.month}월',
                    textAlign: TextAlign.center,
                    style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold),
                  ),
                ),
                IconButton(
                  onPressed: _goToNextMonth,
                  icon: const Icon(Icons.chevron_right),
                ),
              ],
            ),
            const SizedBox(height: 12),
            MonthCalendarGrid(
              month: _displayedMonth,
              highlightedDate: _selectedDate,
              onDateSelected: (date) {
                setState(() => _selectedDate = date);
                _openEntrySheet(date);
              },
            ),
            const Padding(
              padding: EdgeInsets.fromLTRB(20, 32, 20, 8),
              child: Text(
                '다가오는 일정',
                style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
              ),
            ),
            eventsAsync.when(
              data: (events) {
                final tiles = _buildScheduleTiles(events, manualEntries);
                return tiles.isEmpty
                    ? const Padding(
                        padding: EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                        child: Text('다가오는 일정이 여기에 표시됩니다'),
                      )
                    : Column(children: tiles);
              },
              loading: () => const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(child: CircularProgressIndicator()),
              ),
              error: (error, _) => Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                child: Text('일정을 불러오지 못했습니다: $error'),
              ),
            ),
          ],
        ),
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
          child: PrimaryButton(
            label: '안정형 포트폴리오 추천 받기',
            onPressed: () => context.push(AppRoutes.tutorial),
          ),
        ),
      ),
    );
  }

  /// 서버에서 온 일정(확정 가입 상품)과 사용자가 직접 기록한 항목을
  /// 날짜순으로 합쳐서 타일 위젯 목록으로 만든다.
  List<Widget> _buildScheduleTiles(
    List<CalendarEvent> events,
    List<ManualProductEntry> manualEntries,
  ) {
    final items = <({DateTime date, Widget tile})>[
      for (final event in events) (date: event.date, tile: UpcomingEventTile(event: event)),
      for (final entry in manualEntries)
        (
          date: entry.date,
          tile: ManualEntryTile(
            entry: entry,
            onDelete: () => ref.read(manualEntryProvider.notifier).remove(entry.id),
          ),
        ),
    ]..sort((a, b) => a.date.compareTo(b.date));
    return [for (final item in items) item.tile];
  }
}
