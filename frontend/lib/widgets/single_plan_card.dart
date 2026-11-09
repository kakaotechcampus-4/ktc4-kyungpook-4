import 'package:flutter/material.dart';

import '../models/single_plan.dart';
import '../theme/app_colors.dart';
import '../utils/currency_formatter.dart';

/// 주거래은행 단일 상품에 전액을 넣었을 때의 비교 기준 카드.
class SinglePlanCard extends StatelessWidget {
  final SinglePlan plan;

  const SinglePlanCard({super.key, required this.plan});

  @override
  Widget build(BuildContext context) {
    final amountManwon = plan.allocatedAmount ~/ 10000;
    final amountLabel = plan.productType == '적금'
        ? '${CurrencyFormatter.manwon(amountManwon)}씩 ${plan.termMonths}개월 납부'
        : '${CurrencyFormatter.manwon(amountManwon)} ${plan.termMonths}개월 예치';

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            plan.institutionName,
            style: const TextStyle(fontSize: 13, color: AppColors.gray),
          ),
          const SizedBox(height: 4),
          Text(
            plan.productName,
            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          const Text(
            singlePlanDescription,
            style: TextStyle(fontSize: 12, color: Colors.black54, height: 1.4),
          ),
          const SizedBox(height: 16),
          Text(
            '$amountLabel 시 세후 이자',
            style: const TextStyle(fontSize: 14, color: Colors.black54),
          ),
          const SizedBox(height: 4),
          Text(
            CurrencyFormatter.won(plan.afterTaxInterest),
            style: const TextStyle(
              fontSize: 28,
              fontWeight: FontWeight.bold,
              color: AppColors.accent,
            ),
          ),
          const SizedBox(height: 12),
          Text(
            '(${plan.annualRatePercent.toStringAsFixed(1)}%를 공표한 기간 후 실제로 받는 금액입니다.)',
            style: const TextStyle(fontSize: 12, color: AppColors.gray),
          ),
          if (plan.periodNote != null) ...[
            const SizedBox(height: 8),
            Text(
              plan.periodNote!,
              style: const TextStyle(fontSize: 12, color: Colors.orange),
            ),
          ],
        ],
      ),
    );
  }
}
