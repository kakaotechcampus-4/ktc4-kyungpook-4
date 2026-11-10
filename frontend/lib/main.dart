import 'package:flutter/material.dart';
import 'package:flutter_native_splash/flutter_native_splash.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'router/app_router.dart';
import 'theme/app_theme.dart';

void main() {
  runApp(const ProviderScope(child: App()));
  // 웹: index.html 의 첫 로딩 화면(보라 배경 #EDE8F4)을 걷어낸다. 안 걷으면 앱이 뜬 뒤에도
  // body 배경이 보라색으로 남아, 아이폰 Safari 가 상단 상태바·하단 영역을 그 색으로 칠한다.
  FlutterNativeSplash.remove();
}

class App extends StatelessWidget {
  const App({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp.router(
      title: '안정형',
      theme: AppTheme.light,
      routerConfig: appRouter,
    );
  }
}
