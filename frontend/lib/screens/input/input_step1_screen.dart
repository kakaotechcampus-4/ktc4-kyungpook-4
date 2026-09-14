import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../providers/onboarding_provider.dart';
import '../../router/app_router.dart';

class InputStep1Screen extends ConsumerWidget {
  const InputStep1Screen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final notifier = ref.read(onboardingProvider.notifier);

    return Scaffold(
      appBar: AppBar(title: const Text('목돈 · 월저축액 · 기간')),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text('목돈'),
            TextField(
              keyboardType: TextInputType.number,
              onChanged: (v) => notifier.updateLumpSum(int.tryParse(v) ?? 0),
            ),
            const SizedBox(height: 16),
            const Text('월저축액'),
            TextField(
              keyboardType: TextInputType.number,
              onChanged: (v) =>
                  notifier.updateMonthlySaving(int.tryParse(v) ?? 0),
            ),
            const SizedBox(height: 16),
            const Text('기간(개월)'),
            TextField(
              keyboardType: TextInputType.number,
              onChanged: (v) =>
                  notifier.updatePeriodMonths(int.tryParse(v) ?? 0),
            ),
            const Spacer(),
            ElevatedButton(
              onPressed: () => context.push(AppRoutes.inputStep2),
              child: const Text('다음 단계'),
            ),
          ],
        ),
      ),
    );
  }
}
