import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';

class InputStep2Screen extends StatelessWidget {
  const InputStep2Screen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('상황에 맞는 질문')),
      body: const Center(child: Text('전세 계약을 앞두고 계신가요?')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => context.push(AppRoutes.inputStep3),
        label: const Text('다음 단계'),
      ),
    );
  }
}
