import 'package:flutter/services.dart';

/// 입력 중인 숫자 필드에 3자리마다 콤마를 끼워 넣는 포매터.
/// `FilteringTextInputFormatter.digitsOnly` 뒤에 붙여서 쓴다 - 순수 숫자만
/// 남은 값을 받아 콤마를 다시 넣고, 커서가 콤마 삽입으로 엉뚱한 자리로
/// 튀지 않도록 커서 왼쪽 숫자 개수를 기준으로 위치를 다시 계산한다.
///
/// 콤마가 섞인 텍스트를 실제 값으로 쓰려면 항상 `replaceAll(',', '')` 로
/// 걷어내고 파싱해야 한다.
class ThousandsSeparatorInputFormatter extends TextInputFormatter {
  @override
  TextEditingValue formatEditUpdate(
    TextEditingValue oldValue,
    TextEditingValue newValue,
  ) {
    final digitsOnly = newValue.text.replaceAll(',', '');
    if (digitsOnly.isEmpty) {
      return newValue.copyWith(text: '');
    }

    final cursorOffset = newValue.selection.end.clamp(0, newValue.text.length);
    final digitsBeforeCursor =
        newValue.text.substring(0, cursorOffset).replaceAll(',', '').length;

    final formatted = formatDigits(digitsOnly);

    var seen = 0;
    var cursorIndex = formatted.length;
    for (var i = 0; i < formatted.length; i++) {
      if (formatted[i] != ',') seen++;
      if (seen == digitsBeforeCursor) {
        cursorIndex = i + 1;
        break;
      }
    }

    return TextEditingValue(
      text: formatted,
      selection: TextSelection.collapsed(offset: cursorIndex),
    );
  }

  /// "1234567" -> "1,234,567"
  static String formatDigits(String digits) {
    final buffer = StringBuffer();
    for (var i = 0; i < digits.length; i++) {
      if (i != 0 && (digits.length - i) % 3 == 0) buffer.write(',');
      buffer.write(digits[i]);
    }
    return buffer.toString();
  }
}
