import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../models/calendar_event.dart';
import '../../models/manual_product_entry.dart';
import '../../providers/auth_provider.dart';
import '../../providers/calendar_provider.dart';
import '../../providers/manual_entry_provider.dart';
import '../../router/app_router.dart';
import '../../services/auth_client.dart';
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
            onSubmit: ({
              required date,
              required institutionName,
              productId,
              required productName,
              required amount,
              required memo,
            }) async {
              try {
                await ref.read(manualEntryProvider.notifier).add(
                      date: date,
                      institutionName: institutionName,
                      productId: productId,
                      productName: productName,
                      amount: amount,
                      memo: memo,
                    );
                if (!sheetContext.mounted) return;
                Navigator.of(sheetContext).pop();
                if (!mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('상품 정보를 기록했어요.')),
                );
              } catch (e) {
                if (!sheetContext.mounted) return;
                ScaffoldMessenger.of(sheetContext).showSnackBar(
                  SnackBar(content: Text('기록에 실패했어요: $e')),
                );
              }
            },
          ),
        ),
      ),
    );
  }

  Future<void> _logout() async {
    await AuthClient.instance.logout();
    ref.invalidate(currentUserProvider);
    if (mounted) context.go(AppRoutes.login);
  }

  Future<void> _deleteManualEntry(int entryId) async {
    try {
      await ref.read(manualEntryProvider.notifier).remove(entryId);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('삭제에 실패했어요: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final eventsAsync = ref.watch(upcomingEventsProvider);
    final manualEntriesAsync = ref.watch(manualEntryProvider);
    final userAsync = ref.watch(currentUserProvider);

    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.only(bottom: 24),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 8, 16, 0),
              child: Row(
                children: [
                  Expanded(
                    child: userAsync.when(
                      data: (user) => user == null
                          ? const SizedBox.shrink()
                          : Text(
                              '${user.nickname}님 안녕하세요',
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(fontSize: 14, color: Colors.grey),
                            ),
                      loading: () => const SizedBox.shrink(),
                      error: (_, _) => const SizedBox.shrink(),
                    ),
                  ),
                  IconButton(
                    onPressed: () => context.push(AppRoutes.roadmap),
                    icon: const Icon(Icons.route_outlined),
                  ),
                  IconButton(
                    onPressed: _openMonthYearPicker,
                    icon: const Icon(Icons.calendar_month_outlined),
                  ),
                  if (userAsync.value != null)
                    IconButton(
                      onPressed: _logout,
                      icon: const Icon(Icons.logout),
                      tooltip: '로그아웃',
                    ),
                ],
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
            _buildScheduleSection(eventsAsync, manualEntriesAsync),
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

  /// 서버 일정(upcomingEventsProvider)과 직접 기록(manualEntryProvider) 둘 다
  /// 비동기라, 어느 한쪽이라도 로딩/에러면 그 상태를 먼저 보여주고
  /// 둘 다 데이터가 있을 때만 합쳐서 타일 목록을 만든다.
  Widget _buildScheduleSection(
    AsyncValue<List<CalendarEvent>> eventsAsync,
    AsyncValue<List<ManualProductEntry>> manualEntriesAsync,
  ) {
    if (eventsAsync.isLoading || manualEntriesAsync.isLoading) {
      return const Padding(
        padding: EdgeInsets.symmetric(vertical: 24),
        child: Center(child: CircularProgressIndicator()),
      );
    }
    if (eventsAsync.hasError || manualEntriesAsync.hasError) {
      final error = eventsAsync.error ?? manualEntriesAsync.error;
      return Padding(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
        child: Text('일정을 불러오지 못했습니다: $error'),
      );
    }

    final tiles = _buildScheduleTiles(
      eventsAsync.requireValue,
      manualEntriesAsync.requireValue,
    );
    return tiles.isEmpty
        ? const Padding(
            padding: EdgeInsets.symmetric(horizontal: 20, vertical: 24),
            child: Text('다가오는 일정이 여기에 표시됩니다'),
          )
        : Column(children: tiles);
  }

  /// 서버에서 온 일정(확정 가입 상품)과 사용자가 직접 기록한 항목 중
  /// 오늘 이후(오늘 포함) 것만 날짜순으로 합쳐서 타일 위젯 목록으로 만든다.
  /// 지난 일정은 "다가오는 일정"에 보일 이유가 없어서 여기서 걸러낸다.
  List<Widget> _buildScheduleTiles(
    List<CalendarEvent> events,
    List<ManualProductEntry> manualEntries,
  ) {
    final today = DateTime.now();
    final startOfToday = DateTime(today.year, today.month, today.day);
    bool isUpcoming(DateTime date) => !date.isBefore(startOfToday);

    final items = <({DateTime date, Widget tile})>[
      for (final event in events.where((e) => isUpcoming(e.date)))
        (date: event.date, tile: UpcomingEventTile(event: event)),
      for (final entry in manualEntries.where((e) => isUpcoming(e.date)))
        (
          date: entry.date,
          tile: ManualEntryTile(
            entry: entry,
            onDelete: () => _deleteManualEntry(entry.entryId),
          ),
        ),
    ]..sort((a, b) => a.date.compareTo(b.date));
    return [for (final item in items) item.tile];
  }
}
