import 'package:flutter/material.dart';

import '../network/server_waker.dart';

/// Shows a small notice at the bottom of the screen while the app is waiting for a sleeping server,
/// so the first tap of the day does not look like a freeze. Touches pass through it.
class ServerWakeBanner extends StatelessWidget {
  final Widget child;
  final ServerWaker? waker;

  const ServerWakeBanner({super.key, required this.child, this.waker});

  @override
  Widget build(BuildContext context) {
    final notifier = (waker ?? ServerWaker.shared).isWaking;
    return Stack(
      children: [
        child,
        Positioned(
          left: 16,
          right: 16,
          bottom: 16,
          child: SafeArea(
            child: IgnorePointer(
              child: ValueListenableBuilder<bool>(
                valueListenable: notifier,
                builder: (context, waking, _) {
                  if (!waking) return const SizedBox.shrink();
                  return Material(
                    key: const Key('server-wake-banner'),
                    elevation: 6,
                    color: const Color(0xFF1F2937),
                    borderRadius: BorderRadius.circular(12),
                    child: const Padding(
                      padding: EdgeInsets.symmetric(horizontal: 14, vertical: 12),
                      child: Row(
                        children: [
                          SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                          ),
                          SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              'Waking the server up… this can take up to a minute.',
                              style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w600),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ),
      ],
    );
  }
}
