class CurrencyFormatter {
  CurrencyFormatter._();

  /// 1234만원 -> "1,234만원" 형태로 표시
  static String toWon(int amountInManwon) {
    final text = amountInManwon.toString();
    final buffer = StringBuffer();
    for (var i = 0; i < text.length; i++) {
      if (i != 0 && (text.length - i) % 3 == 0) buffer.write(',');
      buffer.write(text[i]);
    }
    return '$buffer만원';
  }
}
