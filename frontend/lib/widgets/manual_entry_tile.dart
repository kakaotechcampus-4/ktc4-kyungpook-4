import 'package:flutter/material.dart';

import '../models/manual_product_entry.dart';
import '../theme/app_colors.dart';
import '../utils/currency_formatter.dart';
import 'date_badge.dart';

/// "다가오는 일정" 목록에서, 서버가 아니라 사용자가 직접 기록한 항목을
/// 보여주는 타일. UpcomingEventTile과 레이아웃은 같지만 "직접 기록" 표시와
/// 삭제 버튼이 붙는다.
class ManualEntryTile extends StatelessWidget {
  final ManualProductEntry entry;
  final VoidCallback onDelete;

  const ManualEntryTile({super.key, required this.entry, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      child: Row(
        children: [
          DateBadge(date: entry.date),
          const SizedBox(width: 18),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Flexible(
                      child: Text(
                        '${entry.institutionName} ${entry.productName}',
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w700,
                        ),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppColors.lavender.withValues(alpha: 0.25),
                        borderRadius: BorderRadius.circular(6),
                      ),
                      child: const Text(
                        '직접 기록',
                        style: TextStyle(fontSize: 10, color: AppColors.labelPurple),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text(
                  CurrencyFormatter.won(entry.amount),
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.gray,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (entry.memo.isNotEmpty) ...[
                  const SizedBox(height: 2),
                  Text(
                    entry.memo,
                    style: TextStyle(fontSize: 12, color: Colors.grey.shade500),
                  ),
                ],
              ],
            ),
          ),
          IconButton(
            onPressed: onDelete,
            icon: Icon(Icons.close, size: 18, color: Colors.grey.shade400),
          ),
        ],
      ),
    );
  }
}
