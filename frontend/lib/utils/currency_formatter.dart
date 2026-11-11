class CurrencyFormatter {
  CurrencyFormatter._();

  /// 1234 -> "1,234", -1234 -> "-1,234" 로 3자리마다 콤마를 찍는다.
  static String _withCommas(int amount) {
    final isNegative = amount < 0;
    final text = amount.abs().toString();
    final buffer = StringBuffer();
    for (var i = 0; i < text.length; i++) {
      if (i != 0 && (text.length - i) % 3 == 0) buffer.write(',');
      buffer.write(text[i]);
    }
    return isNegative ? '-$buffer' : buffer.toString();
  }

  /// 240565 -> "240,565원", -240565 -> "-240,565원"
  static String won(int amountInWon) => '${_withCommas(amountInWon)}원';

  /// 1234 -> "1,234만원" (금액이 이미 만원 단위일 때)
  static String manwon(int amountInManwon) =>
      '${_withCommas(amountInManwon)}만원';

  /// 169200 -> "+169,200원", -169200 -> "-169,200원"
  static String signedWon(int amountInWon) {
    final sign = amountInWon < 0 ? '-' : '+';
    return '$sign${won(amountInWon.abs())}';
  }
}
