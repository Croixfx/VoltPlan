import 'package:intl/intl.dart';

class Formatters {
  Formatters._();

  static final NumberFormat _currencyFormat = NumberFormat('#,##0', 'en_US');
  static final DateFormat _dateFormat = DateFormat('MMM dd, yyyy');
  static final DateFormat _timeFormat = DateFormat('hh:mm a');

  /// Formats amount into Rwandan Francs: "1,245,000 RWF"
  static String formatRwf(num amount) {
    return '${_currencyFormat.format(amount)} RWF';
  }

  /// Formats number with thousands separator: "1,245"
  static String formatNumber(num number) {
    return _currencyFormat.format(number);
  }

  /// Formats date: "Oct 06, 2026"
  static String formatDate(DateTime date) {
    return _dateFormat.format(date);
  }

  /// Formats relative or short date: "Today", "Yesterday", or "Oct 06, 2026"
  static String formatRelativeDate(DateTime date) {
    final now = DateTime.now();
    final difference = now.difference(date);

    if (difference.inDays == 0 && now.day == date.day) {
      return 'Today, ${_timeFormat.format(date)}';
    } else if (difference.inDays <= 1 && now.day - date.day == 1) {
      return 'Yesterday';
    } else if (difference.inDays < 7) {
      return '${difference.inDays} days ago';
    } else {
      return _dateFormat.format(date);
    }
  }
}
