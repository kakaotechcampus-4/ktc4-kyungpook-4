import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../router/app_router.dart';

/// 우대금리·비과세 자격 등을 묻는 챗봇 스타일 다단계 설문 (3-1 ~ 3-4).
class InputStep3Screen extends StatefulWidget {
  const InputStep3Screen({super.key});

  @override
  State<InputStep3Screen> createState() => _InputStep3ScreenState();
}

class _InputStep3ScreenState extends State<InputStep3Screen> {
  static const _totalSubSteps = 4;
  int _subStep = 0;

  void _next() {
    if (_subStep < _totalSubSteps - 1) {
      setState(() => _subStep++);
    } else {
      context.go(AppRoutes.result);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('맞춤 설문 (${_subStep + 1}/$_totalSubSteps)')),
      body: Center(child: Text('질문 ${_subStep + 1}')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _next,
        label: Text(_subStep < _totalSubSteps - 1 ? '다음' : '결과 보기'),
      ),
    );
  }
}
