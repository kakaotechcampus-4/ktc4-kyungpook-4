import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';

class CalendarScreen extends StatelessWidget {
  const CalendarScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('내 만기 캘린더')),
      body: const Center(child: Text('다가오는 일정이 여기에 표시됩니다')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push(AppRoutes.tutorial),
        label: const Text('안정형 포트폴리오 추천 받기'),
      ),
    );
  }
}
