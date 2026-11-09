import 'package:flutter/material.dart';

import '../models/portfolio_option.dart';
import '../theme/app_colors.dart';
import '../utils/currency_formatter.dart';

/// 포트폴리오를 구성하는 상품 한 개를 보여주는 타일.
class ProductDetailTile extends StatelessWidget {
  final int index;
  final PortfolioProduct product;

  const ProductDetailTile({
    super.key,
    required this.index,
    required this.product,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppColors.background,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppColors.lavender.withValues(alpha: 0.4)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 20,
                height: 20,
                alignment: Alignment.center,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  border: Border.all(color: Colors.black54),
                ),
                child: Text(
                  '$index',
                  style: const TextStyle(fontSize: 11, fontWeight: FontWeight.bold),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  '${product.institutionName} ${product.productName}',
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text('→ ${product.amountDescription}',
              style: const TextStyle(fontSize: 13, color: Colors.black87)),
          const SizedBox(height: 2),
          Text('→ ${product.conditionDescription}',
              style: const TextStyle(fontSize: 13, color: Colors.black87)),
          const SizedBox(height: 6),
          Row(
            children: [
              const Text('→ 세후 이자 ', style: TextStyle(fontSize: 13, color: Colors.black87)),
              Text(
                CurrencyFormatter.won(product.afterTaxInterest),
                style: const TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.bold,
                  color: AppColors.accent,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
