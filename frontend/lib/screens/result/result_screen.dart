import 'package:flutter/material.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('맞춤형 포트폴리오')),
      body: const Center(child: Text('단순형 / 균형형 / 최대형 추천 결과가 여기에 표시됩니다')),
    );
  }
}
