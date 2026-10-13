/// Reason code the backend attaches when re-reading a plan with AI would throw away the user's
/// corrected rooms and doors.
const String geometryCorrectedCode = 'geometry_corrected';

const String _geometryCorrectedMessage =
    'You have corrected rooms or doors in this project. Rebuild the design from your corrections, '
    'or read the plan again with AI (this discards your corrections).';

/// Backend messages are written for people, but this is the last line of defence: nothing that reaches
/// the screen may contain API terms such as parameter names or URL paths.
String friendlyApiMessage(String message) {
  if (message.contains('reset_geometry')) return _geometryCorrectedMessage;
  return message.replaceAll(RegExp(r'\s*Check /api/[\w/\-]+\.?'), '').trim();
}
