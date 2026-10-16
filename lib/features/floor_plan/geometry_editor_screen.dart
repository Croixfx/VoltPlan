import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/network/api_exceptions.dart';
import '../../core/widgets/app_button.dart';
import '../../shared/models/geometry.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';

const List<String> kCommonRoomNames = [
  'Bedroom',
  'Master Bedroom',
  'Kitchen',
  'Bathroom',
  'Toilet',
  'Living Room',
  'Dining Room',
  'Corridor',
  'Store Room',
  'Office',
  'Veranda',
];

enum _Handle { topLeft, topRight, bottomLeft, bottomRight, move }

/// Fix what the AI got wrong at the source: room boundaries, room names and door
/// positions. Every change is validated by the backend, which also reports the
/// geometry checks that must pass before equipment can be regenerated.
class GeometryEditorScreen extends StatefulWidget {
  final AppState state;
  final Project project;

  /// When set, the plan image is not loaded and the editor works on a blank sheet of this
  /// aspect ratio. Used by tests; production always loads the real plan.
  final double? planAspectRatio;

  const GeometryEditorScreen({
    super.key,
    required this.state,
    required this.project,
    this.planAspectRatio,
  });

  @override
  State<GeometryEditorScreen> createState() => _GeometryEditorScreenState();
}

class _GeometryEditorScreenState extends State<GeometryEditorScreen> {
  final TextEditingController _nameController = TextEditingController();
  GeometryState? _geo;
  String? _loadError;
  double? _aspect;
  bool _imageFailed = false;
  bool _busy = false;
  bool _showIssues = false;

  String? _selRoomId;
  String? _selDoorId;
  Rect? _dragRect; // preview while resizing / moving the selected room
  GeoDoor?
  _dragDoor; // preview while sliding the selected door (snapped to a wall)
  Offset?
  _doorPointer; // where the finger actually is; the preview is only its projection onto a wall

  String get _pid => (widget.state.selectedProject ?? widget.project).id;
  late final String _imageUrl = ApiEndpoints.projectPlanFile(_pid);

  @override
  void initState() {
    super.initState();
    if (widget.planAspectRatio != null) {
      _aspect = widget.planAspectRatio;
    } else {
      final stream = NetworkImage(
        _imageUrl,
        headers: ApiEndpoints.authHeaders,
      ).resolve(const ImageConfiguration());
      late final ImageStreamListener listener;
      listener = ImageStreamListener(
        (info, _) {
          if (mounted)
            setState(() => _aspect = info.image.width / info.image.height);
          stream.removeListener(listener);
        },
        onError: (_, _) {
          if (mounted) setState(() => _imageFailed = true);
          stream.removeListener(listener);
        },
      );
      stream.addListener(listener);
    }
    _load();
  }

  @override
  void dispose() {
    _nameController.dispose();
    super.dispose();
  }

  // ------------------------------------------------------------------ data
  Future<void> _load() async {
    setState(() => _loadError = null);
    try {
      final geo = await widget.state.geometryRepository.getGeometry(_pid);
      if (!mounted) return;
      setState(() => _geo = geo);
      widget.state.noteGeometry(geo);
    } on ApiException catch (e) {
      if (mounted) setState(() => _loadError = e.message);
    } catch (e) {
      if (mounted) setState(() => _loadError = e.toString());
    }
  }

  void _toast(String message, {bool error = false}) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(
          content: Text(message),
          backgroundColor: error ? Colors.red.shade700 : null,
          duration: Duration(seconds: error ? 5 : 2),
        ),
      );
  }

  /// Runs one backend edit and replaces the local state with the authoritative result.
  Future<bool> _apply(Future<GeometryState> Function() call) async {
    if (_busy) return false;
    setState(() => _busy = true);
    try {
      final geo = await call();
      if (!mounted) return true;
      setState(() {
        _geo = geo;
        _dragRect = null;
        _dragDoor = null;
        _doorPointer = null;
        // drop a selection that no longer exists
        if (_selRoomId != null && !geo.rooms.any((r) => r.id == _selRoomId))
          _selRoomId = null;
        if (_selDoorId != null && !geo.doors.any((d) => d.id == _selDoorId))
          _selDoorId = null;
      });
      widget.state.noteGeometry(geo);
      return true;
    } on ApiException catch (e) {
      _toast(e.message, error: true);
    } catch (e) {
      _toast(e.toString(), error: true);
    } finally {
      if (mounted) {
        setState(() {
          _busy = false;
          _dragRect = null; // a rejected edit snaps back to the stored geometry
          _dragDoor = null;
          _doorPointer = null;
        });
      }
    }
    return false;
  }

  GeoRoom? get _selectedRoom {
    for (final r in _geo?.rooms ?? const <GeoRoom>[]) {
      if (r.id == _selRoomId) return r;
    }
    return null;
  }

  GeoDoor? get _selectedDoor {
    for (final d in _geo?.doors ?? const <GeoDoor>[]) {
      if (d.id == _selDoorId) return d;
    }
    return null;
  }

  void _selectRoom(GeoRoom? room) {
    setState(() {
      _selRoomId = room?.id;
      _selDoorId = null;
      _dragRect = null;
      _dragDoor = null;
      _doorPointer = null;
      _nameController.text = room?.name ?? '';
    });
  }

  void _selectDoor(GeoDoor? door) {
    setState(() {
      _selDoorId = door?.id;
      _selRoomId = null;
      _dragRect = null;
      _dragDoor = null;
    });
  }

  // ---------------------------------------------------------------- actions
  Future<void> _rename(String name) async {
    final room = _selectedRoom;
    final trimmed = name.trim();
    if (room == null || trimmed.isEmpty || trimmed == room.name) return;
    await _apply(
      () => widget.state.geometryRepository.updateRoom(
        _pid,
        room.id,
        name: trimmed,
      ),
    );
    final updated = _selectedRoom;
    if (updated != null) _nameController.text = updated.name;
  }

  Future<void> _commitRoomRect(GeoRoom room, Rect rect) => _apply(
    () => widget.state.geometryRepository.updateRoom(
      _pid,
      room.id,
      bounds: [rect.left, rect.top, rect.right, rect.bottom],
    ),
  );

  Future<void> _addRoom() async {
    const rect = [0.40, 0.40, 0.60, 0.55];
    final before = _geo?.rooms.map((r) => r.id).toSet() ?? {};
    final ok = await _apply(
      () => widget.state.geometryRepository.addRoom(_pid, 'New Room', rect),
    );
    if (ok && mounted) {
      final created = _geo?.rooms
          .where((r) => !before.contains(r.id))
          .firstOrNull;
      if (created != null) _selectRoom(created);
    }
  }

  Future<void> _deleteRoom() async {
    final room = _selectedRoom;
    if (room == null) return;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete room?'),
        content: Text(
          'Delete "${room.name}" together with its doors and fixtures?',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed != true) return;
    await _apply(
      () => widget.state.geometryRepository.deleteRoom(_pid, room.id),
    );
  }

  Future<void> _addDoor(String wall) async {
    final room = _selectedRoom;
    if (room == null) return;
    final before = _geo?.doors.map((d) => d.id).toSet() ?? {};
    final ok = await _apply(
      () => widget.state.geometryRepository.addDoor(_pid, room.id, wall),
    );
    if (ok && mounted) {
      final created = _geo?.doors
          .where((d) => !before.contains(d.id))
          .firstOrNull;
      if (created != null) _selectDoor(created);
    }
  }

  Future<void> _commitDoorDrag(GeoDoor door) async {
    final dragged = _dragDoor;
    final room = _geo?.rooms.where((r) => r.id == door.roomId).firstOrNull;
    if (dragged == null || room == null) return;
    final snap = snapToWall(room.rect, dragged.position);
    await _apply(
      () => widget.state.geometryRepository.updateDoor(
        _pid,
        door.id,
        wall: snap.wall,
        position: snap.t,
      ),
    );
  }

  double _doorWallPosition(GeoDoor door, GeoRoom room) {
    final rect = room.rect;
    final position = door.wall == 'north' || door.wall == 'south'
        ? (door.position.dx - rect.left) / rect.width
        : (door.position.dy - rect.top) / rect.height;
    return position.clamp(0.0, 1.0).toDouble();
  }

  Offset _pointOnWall(GeoRoom room, String wall, double position) {
    final rect = room.rect;
    return switch (wall) {
      'north' => Offset(rect.left + rect.width * position, rect.top),
      'south' => Offset(rect.left + rect.width * position, rect.bottom),
      'west' => Offset(rect.left, rect.top + rect.height * position),
      _ => Offset(rect.right, rect.top + rect.height * position),
    };
  }

  void _previewDoorPosition(GeoDoor door, GeoRoom room, double position) {
    setState(() {
      _dragDoor = door.copyWith(
        position: _pointOnWall(room, door.wall, position),
      );
    });
  }

  Future<void> _regenerate() async {
    if (_busy) return;
    setState(() => _busy = true);
    final error = await widget.state.regenerateDesign(_pid);
    if (!mounted) return;
    setState(() => _busy = false);
    if (error != null) {
      _toast(error, error: true);
      await _load(); // show the up-to-date list of problems
      return;
    }
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        const SnackBar(
          content: Text('Equipment regenerated from your corrections.'),
        ),
      );
    Navigator.pop(context, true);
  }

  // ------------------------------------------------------------ interaction
  void _onTap(Offset local, Size size) {
    final geo = _geo;
    if (geo == null || _busy) return;
    final p = Offset(local.dx / size.width, local.dy / size.height);

    GeoDoor? hitDoor;
    double best = 22.0 / size.shortestSide;
    for (final d in geo.doors) {
      final dist = (d.position - p).distance;
      if (dist < best) {
        best = dist;
        hitDoor = d;
      }
    }
    if (hitDoor != null) {
      _selectDoor(hitDoor);
      return;
    }
    final room = roomAt(geo.rooms, p);
    if (room != null) {
      _selectRoom(room);
    } else {
      setState(() {
        _selRoomId = null;
        _selDoorId = null;
      });
    }
  }

  Rect _adjust(Rect base, _Handle h, Offset d) {
    return switch (h) {
      _Handle.topLeft => Rect.fromLTRB(
        base.left + d.dx,
        base.top + d.dy,
        base.right,
        base.bottom,
      ),
      _Handle.topRight => Rect.fromLTRB(
        base.left,
        base.top + d.dy,
        base.right + d.dx,
        base.bottom,
      ),
      _Handle.bottomLeft => Rect.fromLTRB(
        base.left + d.dx,
        base.top,
        base.right,
        base.bottom + d.dy,
      ),
      _Handle.bottomRight => Rect.fromLTRB(
        base.left,
        base.top,
        base.right + d.dx,
        base.bottom + d.dy,
      ),
      _Handle.move => base.shift(d),
    };
  }

  void _dragHandle(GeoRoom room, _Handle h, Offset deltaPx, Size size) {
    if (_busy) return;
    final d = Offset(deltaPx.dx / size.width, deltaPx.dy / size.height);
    final base = _dragRect ?? room.rect;
    var next = _adjust(base, h, d);
    if (h == _Handle.move) {
      // keep the whole room inside the plan instead of squashing it against the edge
      final dx = next.left < 0
          ? -next.left
          : (next.right > 1 ? 1 - next.right : 0.0);
      final dy = next.top < 0
          ? -next.top
          : (next.bottom > 1 ? 1 - next.bottom : 0.0);
      next = next.shift(Offset(dx, dy));
    } else {
      next = clampRect(next);
    }
    setState(() => _dragRect = next);
  }

  void _dragDoorHandle(GeoDoor door, Offset deltaPx, Size size) {
    if (_busy) return;
    final room = _geo?.rooms.where((r) => r.id == door.roomId).firstOrNull;
    if (room == null) return;
    // Accumulate the raw pointer movement; snapping every step would pin the door to its current wall.
    final pointer =
        (_doorPointer ?? door.position) +
        Offset(deltaPx.dx / size.width, deltaPx.dy / size.height);
    final snap = snapToWall(room.rect, pointer);
    setState(() {
      _doorPointer = pointer;
      _dragDoor = door.copyWith(wall: snap.wall, position: snap.point);
    });
  }

  // ------------------------------------------------------------------- build
  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Rooms & Doors'),
        actions: [
          IconButton(
            tooltip: 'Reload',
            icon: const Icon(Icons.refresh),
            onPressed: _busy ? null : _load,
          ),
        ],
      ),
      body: SafeArea(
        child: _geo == null
            ? _buildLoading()
            : Column(
                children: [
                  if (_busy) const LinearProgressIndicator(minHeight: 2),
                  Expanded(child: _buildPlan(isDark)),
                  ConstrainedBox(
                    constraints: BoxConstraints(
                      maxHeight: MediaQuery.of(context).size.height * 0.46,
                    ),
                    child: SingleChildScrollView(child: _buildPanel(isDark)),
                  ),
                ],
              ),
      ),
    );
  }

  Widget _buildLoading() {
    if (_loadError != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(_loadError!, textAlign: TextAlign.center),
              const SizedBox(height: 12),
              AppButton(label: 'Try again', onPressed: _load, height: 38),
            ],
          ),
        ),
      );
    }
    return const Center(child: CircularProgressIndicator());
  }

  Widget _buildPlan(bool isDark) {
    if (_imageFailed) {
      return const Center(child: Text('The plan image could not be loaded.'));
    }
    final aspect = _aspect;
    if (aspect == null) return const Center(child: CircularProgressIndicator());
    final geo = _geo!;

    return Container(
      color: isDark ? AppColors.surfaceDark : AppColors.surfaceSecondaryLight,
      child: Center(
        child: AspectRatio(
          aspectRatio: aspect,
          child: LayoutBuilder(
            builder: (context, constraints) {
              final size = constraints.biggest;
              Offset px(Offset r) =>
                  Offset(r.dx * size.width, r.dy * size.height);

              final room = _selectedRoom;
              final door = _selectedDoor;
              final shownDoor =
                  (_dragDoor != null &&
                      door != null &&
                      _dragDoor!.id == door.id)
                  ? _dragDoor!
                  : door;
              final rooms = [
                for (final r in geo.rooms)
                  if (r.id == _selRoomId && _dragRect != null)
                    r.copyWith(rect: _dragRect)
                  else
                    r,
              ];
              final doors = [
                for (final d in geo.doors)
                  if (shownDoor != null && d.id == shownDoor.id)
                    shownDoor
                  else
                    d,
              ];

              final handles = <Widget>[];
              if (room != null && !_busy) {
                final rect = _dragRect ?? room.rect;
                Widget handle(_Handle h, Offset at, {IconData? icon}) =>
                    Positioned(
                      key: Key('room-handle-${h.name}'),
                      left: at.dx - 16,
                      top: at.dy - 16,
                      width: 32,
                      height: 32,
                      child: GestureDetector(
                        behavior: HitTestBehavior.opaque,
                        onPanUpdate: (d) => _dragHandle(room, h, d.delta, size),
                        onPanEnd: (_) {
                          final r = _dragRect;
                          if (r != null) _commitRoomRect(room, r);
                        },
                        child: Container(
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: AppColors.primaryBlue,
                            border: Border.all(color: Colors.white, width: 2),
                          ),
                          child: icon == null
                              ? null
                              : Icon(icon, size: 16, color: Colors.white),
                        ),
                      ),
                    );
                handles
                  ..add(handle(_Handle.topLeft, px(rect.topLeft)))
                  ..add(handle(_Handle.topRight, px(rect.topRight)))
                  ..add(handle(_Handle.bottomLeft, px(rect.bottomLeft)))
                  ..add(handle(_Handle.bottomRight, px(rect.bottomRight)))
                  ..add(
                    handle(
                      _Handle.move,
                      px(rect.center),
                      icon: Icons.open_with_rounded,
                    ),
                  );
              }
              if (door != null && shownDoor != null && !_busy) {
                final at = px(shownDoor.position);
                handles.add(
                  Positioned(
                    key: const Key('door-handle'),
                    left: at.dx - 24,
                    top: at.dy - 24,
                    width: 48,
                    height: 48,
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onPanUpdate: (d) => _dragDoorHandle(door, d.delta, size),
                      onPanEnd: (_) => _commitDoorDrag(door),
                      child: Container(
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          color: Colors.orange.shade700.withValues(alpha: 0.9),
                          border: Border.all(color: Colors.white, width: 2),
                        ),
                        child: const Icon(
                          Icons.door_front_door_outlined,
                          size: 22,
                          color: Colors.white,
                        ),
                      ),
                    ),
                  ),
                );
              }

              return Stack(
                clipBehavior: Clip.none,
                children: [
                  Positioned.fill(
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onTapUp: (d) => _onTap(d.localPosition, size),
                      child: Stack(
                        fit: StackFit.expand,
                        children: [
                          if (widget.planAspectRatio == null)
                            Image.network(
                              _imageUrl,
                              headers: ApiEndpoints.authHeaders,
                              fit: BoxFit.fill,
                            )
                          else
                            const ColoredBox(color: Colors.white),
                          CustomPaint(
                            painter: _GeometryPainter(
                              rooms: rooms,
                              doors: doors,
                              issues: geo.issues,
                              selectedRoomId: _selRoomId,
                              selectedDoorId: _selDoorId,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  ...handles,
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  Widget _buildPanel(bool isDark) {
    final geo = _geo!;
    final room = _selectedRoom;
    final door = _selectedDoor;
    final muted = isDark
        ? AppColors.textSecondaryDark
        : AppColors.textSecondaryLight;
    final errors = geo.errorCount;
    final warnings = geo.issues.length - errors;

    return Container(
      padding: const EdgeInsets.fromLTRB(16, 10, 16, 14),
      decoration: BoxDecoration(
        color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
        border: Border(
          top: BorderSide(
            color: isDark ? AppColors.borderDark : AppColors.borderLight,
          ),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          if (room != null) ..._roomControls(room, muted),
          if (door != null) ..._doorControls(door, muted),
          if (room == null && door == null) ...[
            Text(
              'Tap a room to rename or reshape it, or a door marker to move it. '
              'Drag the blue handles; doors slide along walls.',
              style: TextStyle(fontSize: 12.5, color: muted),
            ),
            const SizedBox(height: 8),
            Align(
              alignment: Alignment.centerLeft,
              child: OutlinedButton.icon(
                key: const Key('add-room'),
                onPressed: _busy ? null : _addRoom,
                icon: const Icon(Icons.add_box_outlined, size: 18),
                label: const Text('Add room'),
              ),
            ),
          ],
          const Divider(height: 20),
          InkWell(
            key: const Key('issues-toggle'),
            onTap: geo.issues.isEmpty
                ? null
                : () => setState(() => _showIssues = !_showIssues),
            child: Row(
              children: [
                Icon(
                  errors > 0
                      ? Icons.error_outline
                      : (warnings > 0
                            ? Icons.warning_amber_rounded
                            : Icons.check_circle_outline),
                  size: 18,
                  color: errors > 0
                      ? Colors.red
                      : (warnings > 0 ? Colors.orange : Colors.green),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    geo.issues.isEmpty
                        ? 'Geometry checks passed'
                        : '$errors error${errors == 1 ? '' : 's'} • $warnings warning${warnings == 1 ? '' : 's'}',
                    style: const TextStyle(
                      fontSize: 13,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                ),
                if (geo.issues.isNotEmpty)
                  Icon(_showIssues ? Icons.expand_less : Icons.expand_more),
              ],
            ),
          ),
          if (_showIssues || errors > 0)
            for (final issue in geo.issues)
              Padding(
                padding: const EdgeInsets.only(top: 6),
                child: InkWell(
                  onTap: () => _focusIssue(issue),
                  child: Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Icon(
                        issue.isError
                            ? Icons.cancel_outlined
                            : Icons.info_outline,
                        size: 15,
                        color: issue.isError ? Colors.red : Colors.orange,
                      ),
                      const SizedBox(width: 6),
                      Expanded(
                        child: Text(
                          issue.message,
                          style: const TextStyle(fontSize: 12.5),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          const SizedBox(height: 12),
          AppButton(
            key: const Key('regenerate-button'),
            label: 'Regenerate equipment',
            icon: Icons.auto_fix_high,
            isLoading: _busy,
            onPressed: (!geo.canGenerate || _busy) ? null : _regenerate,
          ),
          const SizedBox(height: 4),
          Text(
            geo.canGenerate
                ? (geo.needsRegeneration
                      ? 'Your corrections are saved. Regenerate to rebuild sockets, lights, circuits, BOQ and cost.'
                      : 'Equipment matches the current rooms and doors.')
                : 'Fix the errors above before equipment can be generated. Nothing is guessed.',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 11.5, color: muted),
          ),
        ],
      ),
    );
  }

  void _focusIssue(GeoIssue issue) {
    final geo = _geo!;
    for (final id in issue.entityIds) {
      final r = geo.rooms.where((x) => x.id == id).firstOrNull;
      if (r != null) {
        _selectRoom(r);
        return;
      }
      final d = geo.doors.where((x) => x.id == id).firstOrNull;
      if (d != null) {
        _selectDoor(d);
        return;
      }
    }
  }

  List<Widget> _roomControls(GeoRoom room, Color muted) {
    final doorsHere = _geo!.doors.where((d) => d.roomId == room.id).length;
    return [
      Text(
        '${room.name}${room.areaM2 != null ? ' • ${room.areaM2!.toStringAsFixed(1)} m²' : ''} • $doorsHere door${doorsHere == 1 ? '' : 's'}',
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 8),
      Row(
        children: [
          Expanded(
            child: TextField(
              key: const Key('room-name-field'),
              controller: _nameController,
              enabled: !_busy,
              textInputAction: TextInputAction.done,
              onSubmitted: _rename,
              decoration: const InputDecoration(
                labelText: 'Room name',
                isDense: true,
                border: OutlineInputBorder(),
              ),
            ),
          ),
          const SizedBox(width: 8),
          IconButton.filled(
            key: const Key('save-room-name'),
            tooltip: 'Save name',
            onPressed: _busy ? null : () => _rename(_nameController.text),
            icon: const Icon(Icons.check),
          ),
        ],
      ),
      const SizedBox(height: 8),
      SizedBox(
        height: 34,
        child: ListView.separated(
          scrollDirection: Axis.horizontal,
          itemCount: kCommonRoomNames.length,
          separatorBuilder: (_, _) => const SizedBox(width: 6),
          itemBuilder: (context, i) => ActionChip(
            key: Key('name-chip-${kCommonRoomNames[i]}'),
            label: Text(
              kCommonRoomNames[i],
              style: const TextStyle(fontSize: 12),
            ),
            onPressed: _busy ? null : () => _rename(kCommonRoomNames[i]),
          ),
        ),
      ),
      const SizedBox(height: 8),
      Wrap(
        spacing: 6,
        runSpacing: 4,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          Text('Add door on:', style: TextStyle(fontSize: 12, color: muted)),
          for (final w in kWalls)
            OutlinedButton(
              key: Key('add-door-$w'),
              style: OutlinedButton.styleFrom(
                visualDensity: VisualDensity.compact,
              ),
              onPressed: _busy ? null : () => _addDoor(w),
              child: Text(w[0].toUpperCase() + w.substring(1)),
            ),
          TextButton.icon(
            key: const Key('delete-room'),
            onPressed: _busy ? null : _deleteRoom,
            icon: const Icon(Icons.delete_outline, size: 18, color: Colors.red),
            label: const Text(
              'Delete room',
              style: TextStyle(color: Colors.red),
            ),
          ),
        ],
      ),
    ];
  }

  List<Widget> _doorControls(GeoDoor door, Color muted) {
    final room = _geo!.rooms.where((r) => r.id == door.roomId).firstOrNull;
    final horizontal = door.wall == 'north' || door.wall == 'south';
    final sides = horizontal
        ? const ['west', 'east']
        : const ['north', 'south'];
    return [
      Text(
        'Door in ${room?.name ?? 'room'} • ${door.wall} wall',
        style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 4),
      Text(
        'Drag the orange handle along the walls. Switches are placed on the handle side.',
        style: TextStyle(fontSize: 12, color: muted),
      ),
      if (room != null) ...[
        const SizedBox(height: 8),
        Row(
          children: [
            const Text('Wall position', style: TextStyle(fontSize: 12)),
            Expanded(
              child: Slider(
                key: const Key('door-position-slider'),
                min: 0,
                max: 1,
                value: _doorWallPosition(_dragDoor ?? door, room),
                onChanged: _busy
                    ? null
                    : (value) => _previewDoorPosition(door, room, value),
                onChangeEnd: _busy
                    ? null
                    : (value) => _apply(
                        () => widget.state.geometryRepository.updateDoor(
                          _pid,
                          door.id,
                          position: value,
                        ),
                      ),
              ),
            ),
          ],
        ),
        Wrap(
          spacing: 6,
          children: [
            for (final wall in kWalls)
              OutlinedButton(
                key: Key('door-wall-$wall'),
                style: OutlinedButton.styleFrom(
                  visualDensity: VisualDensity.compact,
                  backgroundColor: door.wall == wall
                      ? AppColors.primaryBlue.withValues(alpha: 0.12)
                      : null,
                ),
                onPressed: _busy || door.wall == wall
                    ? null
                    : () => _apply(
                        () => widget.state.geometryRepository.updateDoor(
                          _pid,
                          door.id,
                          wall: wall,
                          position: _doorWallPosition(door, room),
                        ),
                      ),
                child: Text(wall[0].toUpperCase() + wall.substring(1)),
              ),
          ],
        ),
      ],
      const SizedBox(height: 8),
      Wrap(
        spacing: 12,
        runSpacing: 8,
        crossAxisAlignment: WrapCrossAlignment.center,
        children: [
          SegmentedButton<String>(
            key: const Key('door-swing'),
            showSelectedIcon: false,
            segments: const [
              ButtonSegment(value: 'into_room', label: Text('Opens in')),
              ButtonSegment(value: 'out_of_room', label: Text('Opens out')),
            ],
            selected: {door.swingDirection},
            onSelectionChanged: _busy
                ? null
                : (s) => _apply(
                    () => widget.state.geometryRepository.updateDoor(
                      _pid,
                      door.id,
                      swingDirection: s.first,
                    ),
                  ),
          ),
          SegmentedButton<String>(
            key: const Key('door-strike'),
            showSelectedIcon: false,
            segments: [
              for (final s in sides)
                ButtonSegment(
                  value: s,
                  label: Text('Handle ${s[0].toUpperCase()}${s.substring(1)}'),
                ),
            ],
            selected: {
              sides.contains(door.strikeSide) ? door.strikeSide! : sides.last,
            },
            onSelectionChanged: _busy
                ? null
                : (s) => _apply(
                    () => widget.state.geometryRepository.updateDoor(
                      _pid,
                      door.id,
                      strikeSide: s.first,
                    ),
                  ),
          ),
          TextButton.icon(
            key: const Key('delete-door'),
            onPressed: _busy
                ? null
                : () => _apply(
                    () => widget.state.geometryRepository.deleteDoor(
                      _pid,
                      door.id,
                    ),
                  ),
            icon: const Icon(Icons.delete_outline, size: 18, color: Colors.red),
            label: const Text(
              'Delete door',
              style: TextStyle(color: Colors.red),
            ),
          ),
        ],
      ),
    ];
  }
}

class _GeometryPainter extends CustomPainter {
  final List<GeoRoom> rooms;
  final List<GeoDoor> doors;
  final List<GeoIssue> issues;
  final String? selectedRoomId;
  final String? selectedDoorId;

  _GeometryPainter({
    required this.rooms,
    required this.doors,
    required this.issues,
    required this.selectedRoomId,
    required this.selectedDoorId,
  });

  static const Color manualColor = Color(0xFFF59E0B);

  /// error > warning for each entity id
  Map<String, String> get _severity {
    final map = <String, String>{};
    for (final i in issues) {
      for (final id in i.entityIds) {
        if (map[id] != 'error') map[id] = i.severity;
      }
    }
    return map;
  }

  @override
  void paint(Canvas canvas, Size size) {
    final severity = _severity;
    Rect px(Rect r) => Rect.fromLTRB(
      r.left * size.width,
      r.top * size.height,
      r.right * size.width,
      r.bottom * size.height,
    );

    for (final r in rooms) {
      final rect = px(r.rect);
      final selected = r.id == selectedRoomId;
      final sev = severity[r.id];
      final base = sev == 'error'
          ? Colors.red
          : (sev == 'warning' ? Colors.orange : AppColors.primaryBlue);
      canvas.drawRect(
        rect,
        Paint()..color = base.withValues(alpha: selected ? 0.22 : 0.10),
      );
      canvas.drawRect(
        rect,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = selected ? 3 : 1.6
          ..color = sev != null
              ? base
              : (r.isManual ? manualColor : AppColors.primaryBlue),
      );
      final tp = TextPainter(
        text: TextSpan(
          text: r.name,
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w700,
            color: Colors.black87,
            backgroundColor: Colors.white.withValues(alpha: 0.75),
          ),
        ),
        textDirection: TextDirection.ltr,
        maxLines: 1,
        ellipsis: '…',
      )..layout(maxWidth: rect.width - 6);
      tp.paint(canvas, Offset(rect.left + 4, rect.top + 3));
    }

    for (final d in doors) {
      final c = Offset(d.position.dx * size.width, d.position.dy * size.height);
      final horizontal = d.wall == 'north' || d.wall == 'south';
      final bar = horizontal
          ? Rect.fromCenter(center: c, width: 22, height: 6)
          : Rect.fromCenter(center: c, width: 6, height: 22);
      final sev = severity[d.id];
      final color = d.id == selectedDoorId
          ? Colors.orange.shade800
          : (sev == 'error'
                ? Colors.red
                : (sev == 'warning' ? Colors.orange : Colors.brown.shade600));
      canvas.drawRRect(
        RRect.fromRectAndRadius(bar, const Radius.circular(2)),
        Paint()..color = color,
      );
      canvas.drawCircle(
        c,
        9,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 1.5
          ..color = color,
      );
    }
  }

  @override
  bool shouldRepaint(_GeometryPainter old) => true;
}
