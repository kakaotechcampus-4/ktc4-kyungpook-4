import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/manual_product_entry.dart';
import '../services/manual_entry_client.dart';

/// 캘린더에서 직접 기록한 상품 정보. 서버(/manual-entries)에 저장되는
/// 로그인 사용자 전용 데이터라, 오늘 기준 한 달 전~6개월 뒤 범위로 한 번에
/// 불러온다 ("다가오는 일정"에 필요한 미래 구간 + 지난 달까지의 과거 조회를
/// 함께 커버하기 위함).
class ManualEntryNotifier extends AsyncNotifier<List<ManualProductEntry>> {
  @override
  Future<List<ManualProductEntry>> build() {
    final now = DateTime.now();
    return ManualEntryClient.instance.list(
      start: now.subtract(const Duration(days: 35)),
      end: now.add(const Duration(days: 180)),
    );
  }

  Future<void> add({
    required DateTime date,
    required String institutionName,
    String? productId,
    required String productName,
    required int amount,
    String memo = '',
  }) async {
    final created = await ManualEntryClient.instance.create(
      date: date,
      institutionName: institutionName,
      productId: productId,
      productName: productName,
      amount: amount,
      memo: memo,
    );
    state = AsyncData([...?state.value, created]);
  }

  Future<void> remove(int entryId) async {
    await ManualEntryClient.instance.delete(entryId);
    state = AsyncData(
      (state.value ?? const []).where((e) => e.entryId != entryId).toList(),
    );
  }
}

final manualEntryProvider =
    AsyncNotifierProvider<ManualEntryNotifier, List<ManualProductEntry>>(
  ManualEntryNotifier.new,
);
