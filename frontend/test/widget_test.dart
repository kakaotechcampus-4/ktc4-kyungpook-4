import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:frontend/main.dart';
import 'package:frontend/utils/app_images.dart';

void main() {
  testWidgets('splash shows briefly then navigates to the calendar home',
      (WidgetTester tester) async {
    await tester.pumpWidget(const ProviderScope(child: App()));

    expect(
      find.byWidgetPredicate(
        (widget) =>
            widget is Image &&
            widget.image is AssetImage &&
            (widget.image as AssetImage).assetName == AppImages.titleIcon,
      ),
      findsOneWidget,
    );

    // precacheImage는 실제 비동기 디코딩을 거치므로 실제 시간이 흘러야 끝난다
    // (runAsync). 최소 노출 시간(Future.delayed)은 테스트의 가짜 시계를
    // 직접 돌려야(pump) 끝난다 — 두 종류를 각각 흘려보내야 둘 다 끝난다.
    await tester.runAsync(() => Future.delayed(const Duration(milliseconds: 200)));
    await tester.pump(const Duration(seconds: 2));
    await tester.pumpAndSettle();

    expect(find.text('다가오는 일정'), findsOneWidget);
  });
}
