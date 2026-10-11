import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/manual_product_entry.dart';

/// MOCK: 캘린더에서 직접 기록한 상품 정보를 로컬 메모리에만 보관한다.
/// 백엔드에 수동 등록 API(예: POST /portfolios/{id}/holdings)가 생기면
/// add()에서 ApiClient 호출로 바꾸고, 목록은 서버 조회로 바꾸면 된다.
/// 그 전까지는 앱을 새로고침하면 사라진다.
class ManualEntryNotifier extends Notifier<List<ManualProductEntry>> {
  @override
  List<ManualProductEntry> build() => [];

  void add(ManualProductEntry entry) {
    state = [...state, entry];
  }

  void remove(String id) {
    state = state.where((e) => e.id != id).toList();
  }
}

final manualEntryProvider =
    NotifierProvider<ManualEntryNotifier, List<ManualProductEntry>>(
  ManualEntryNotifier.new,
);
