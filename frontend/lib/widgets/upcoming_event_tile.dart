import 'package:flutter/material.dart';

import '../models/calendar_event.dart';
import '../theme/app_colors.dart';
import '../utils/currency_formatter.dart';
import 'date_badge.dart';

class UpcomingEventTile extends StatelessWidget {
  final CalendarEvent event;

  const UpcomingEventTile({super.key, required this.event});

  /// '# 3회차 납입 · 41,000원' / '# 만기 · 원금 10,000,000원'
  String get _detail {
    final amount = event.amount;
    if (event.isMaturity) {
      return amount == null ? '# 만기' : '# 만기 · 원금 ${CurrencyFormatter.won(amount)}';
    }
    final round = '# ${event.installmentRound}회차 납입';
    return amount == null ? round : '$round · ${CurrencyFormatter.won(amount)}';
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
      child: Row(
        children: [
          DateBadge(date: event.date),
          const SizedBox(width: 18),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${event.institutionName} ${event.productName}',
                  style: const TextStyle(
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 4),
                Text(
                  _detail,
                  style: const TextStyle(
                    fontSize: 14,
                    color: AppColors.gray,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
