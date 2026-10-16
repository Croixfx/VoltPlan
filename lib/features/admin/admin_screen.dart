import 'package:flutter/material.dart';
import '../../core/network/api_client.dart';
import '../../core/network/api_endpoints.dart';
import '../../core/network/api_exceptions.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';
import '../projects/project_overview_screen.dart';

/// Administrators only: every account and every project on the server.
class AdminScreen extends StatefulWidget {
  final AppState state;
  final ApiClient? client;

  const AdminScreen({super.key, required this.state, this.client});

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  late final ApiClient _client = widget.client ?? ApiClient();
  Map<String, dynamic>? _overview;
  List<Map<String, dynamic>> _users = [];
  List<Map<String, dynamic>> _projects = [];
  String _query = '';
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final overview = await _client.get(ApiEndpoints.adminOverview);
      final users = await _client.get(ApiEndpoints.adminUsers);
      final projects = await _client.get(ApiEndpoints.adminProjects(query: _query));
      if (!mounted) return;
      setState(() {
        _overview = Map<String, dynamic>.from(overview as Map);
        _users = (users as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _projects = (projects as List).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        _loading = false;
      });
    } on ApiException catch (e) {
      if (mounted) setState(() { _error = e.message; _loading = false; });
    } catch (e) {
      if (mounted) setState(() { _error = 'Could not load: $e'; _loading = false; });
    }
  }

  Future<void> _openProject(String id) async {
    try {
      final data = await _client.get(ApiEndpoints.project(id));
      final project = Project.fromJson(Map<String, dynamic>.from(data as Map));
      if (!mounted) return;
      widget.state.selectProject(project);
      await Navigator.push(
        context,
        MaterialPageRoute(builder: (_) => ProjectOverviewScreen(state: widget.state, project: project)),
      );
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  Future<void> _changeAccess(Map<String, dynamic> user, bool deactivate) async {
    String? reason;
    if (deactivate) {
      final controller = TextEditingController();
      final ok = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Deactivate this account?'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('${user['email']} will be signed out and cannot sign in until you reactivate it. '
                  'Their projects are kept.'),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                maxLength: 300,
                decoration: const InputDecoration(labelText: 'Reason (optional)'),
              ),
            ],
          ),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Deactivate')),
          ],
        ),
      );
      if (ok != true) return;
      reason = controller.text.trim();
    }
    try {
      await _client.post(
        deactivate ? ApiEndpoints.adminDeactivate(user['id']) : ApiEndpoints.adminReactivate(user['id']),
        body: deactivate ? {'reason': reason} : null,
      );
      await _load();
    } on ApiException catch (e) {
      _toast(e.message);
    }
  }

  void _toast(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Admin console'),
          actions: [IconButton(tooltip: 'Refresh', onPressed: _load, icon: const Icon(Icons.refresh))],
          bottom: const TabBar(tabs: [Tab(text: 'Overview'), Tab(text: 'Accounts'), Tab(text: 'Projects')]),
        ),
        body: _loading
            ? const Center(child: CircularProgressIndicator())
            : _error != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(mainAxisSize: MainAxisSize.min, children: [
                        Text(_error!, textAlign: TextAlign.center),
                        const SizedBox(height: 12),
                        FilledButton(onPressed: _load, child: const Text('Try again')),
                      ]),
                    ),
                  )
                : TabBarView(children: [_overviewTab(), _usersTab(), _projectsTab()]),
      ),
    );
  }

  Widget _overviewTab() {
    final o = _overview!;
    Widget stat(String label, Object? value) => Card(
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('$value', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w800)),
              const SizedBox(height: 2),
              Text(label, style: const TextStyle(fontSize: 12)),
            ]),
          ),
        );
    String breakdown(Object? map) => (map is Map && map.isNotEmpty)
        ? map.entries.map((e) => '${e.key}: ${e.value}').join('   ')
        : 'none yet';
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          childAspectRatio: 2.1,
          mainAxisSpacing: 8,
          crossAxisSpacing: 8,
          children: [
            stat('Accounts', o['users']),
            stat('New accounts (7 days)', o['new_users_7d']),
            stat('Projects', o['projects']),
            stat('New projects (7 days)', o['new_projects_7d']),
            stat('Deactivated accounts', o['deactivated_users']),
            stat('Projects with no owner', o['unowned_projects']),
          ],
        ),
        const SizedBox(height: 16),
        const Text('Projects by status', style: TextStyle(fontWeight: FontWeight.w700)),
        Text(breakdown(o['projects_by_status'])),
        const SizedBox(height: 12),
        const Text('Analyses', style: TextStyle(fontWeight: FontWeight.w700)),
        Text(breakdown(o['analyses_by_status'])),
      ],
    );
  }

  Widget _usersTab() {
    if (_users.isEmpty) return const Center(child: Text('No accounts yet.'));
    return ListView.separated(
      itemCount: _users.length,
      separatorBuilder: (_, _) => const Divider(height: 1),
      itemBuilder: (context, i) {
        final u = _users[i];
        final off = u['deactivated_at'] != null;
        final admin = u['is_admin'] == true;
        return ListTile(
          title: Text('${u['email']}${admin ? '  (admin)' : ''}'),
          subtitle: Text([
            if ((u['name'] ?? '').toString().isNotEmpty) u['name'],
            '${u['project_count']} project(s)',
            if (off) 'DEACTIVATED${u['deactivated_reason'] == null ? '' : ': ${u['deactivated_reason']}'}',
          ].join(' • ')),
          trailing: admin
              ? null
              : TextButton(
                  onPressed: () => _changeAccess(u, !off),
                  child: Text(off ? 'Reactivate' : 'Deactivate'),
                ),
        );
      },
    );
  }

  Widget _projectsTab() {
    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
          child: TextField(
            decoration: const InputDecoration(
              hintText: 'Search name, client, location or owner email',
              prefixIcon: Icon(Icons.search),
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onSubmitted: (v) {
              _query = v.trim();
              _load();
            },
          ),
        ),
        Expanded(
          child: _projects.isEmpty
              ? const Center(child: Text('No projects found.'))
              : ListView.separated(
                  itemCount: _projects.length,
                  separatorBuilder: (_, _) => const Divider(height: 1),
                  itemBuilder: (context, i) {
                    final p = _projects[i];
                    return ListTile(
                      title: Text('${p['name']}'),
                      subtitle: Text('${p['owner_email'] ?? 'no owner'} • ${p['client']} • ${p['location']}\n'
                          'status: ${p['status']}${p['analysis_status'] == null ? '' : ' • analysis: ${p['analysis_status']}'}'),
                      isThreeLine: true,
                      trailing: const Icon(Icons.chevron_right),
                      onTap: () => _openProject(p['id'] as String),
                    );
                  },
                ),
        ),
      ],
    );
  }
}
