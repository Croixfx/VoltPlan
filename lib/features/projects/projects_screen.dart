import 'package:flutter/material.dart';
import '../../core/constants/app_colors.dart';
import '../../core/utils/formatters.dart';
import '../../core/widgets/empty_state.dart';
import '../../core/widgets/status_badge.dart';
import '../../shared/models/project.dart';
import '../../shared/state/app_state.dart';
import 'create_project_screen.dart';
import 'project_overview_screen.dart';

class ProjectsScreen extends StatefulWidget {
  final AppState state;

  const ProjectsScreen({super.key, required this.state});

  @override
  State<ProjectsScreen> createState() => _ProjectsScreenState();
}

class _ProjectsScreenState extends State<ProjectsScreen> {
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _searchController.text = widget.state.searchQuery;
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final projects = widget.state.filteredProjects;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Projects'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            tooltip: 'New Project',
            onPressed: () {
              Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => CreateProjectScreen(state: widget.state),
                ),
              );
            },
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () {
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) => CreateProjectScreen(state: widget.state),
            ),
          );
        },
        backgroundColor: AppColors.primaryBlue,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.add, size: 20),
        label: const Text(
          'New Project',
          style: TextStyle(fontWeight: FontWeight.w600),
        ),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Search Bar
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
              child: TextField(
                controller: _searchController,
                onChanged: (val) {
                  widget.state.setSearchQuery(val);
                },
                decoration: InputDecoration(
                  hintText: 'Search by project, client, or location...',
                  prefixIcon: Icon(
                    Icons.search,
                    color: isDark
                        ? AppColors.textMutedDark
                        : AppColors.textMutedLight,
                    size: 20,
                  ),
                  suffixIcon: _searchController.text.isNotEmpty
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 18),
                          onPressed: () {
                            _searchController.clear();
                            widget.state.setSearchQuery('');
                          },
                        )
                      : null,
                ),
              ),
            ),

            // Filter Chips Bar
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
              child: Row(
                children: [
                  _buildFilterChip('All', null, isDark),
                  const SizedBox(width: 8),
                  _buildFilterChip(
                    'In Progress',
                    ProjectStatus.inProgress,
                    isDark,
                  ),
                  const SizedBox(width: 8),
                  _buildFilterChip(
                    'Completed',
                    ProjectStatus.completed,
                    isDark,
                  ),
                  const SizedBox(width: 8),
                  _buildFilterChip(
                    'Review Required',
                    ProjectStatus.reviewRequired,
                    isDark,
                  ),
                ],
              ),
            ),

            const SizedBox(height: 8),

            // Projects List or Empty State
            Expanded(
              child: projects.isEmpty
                  ? EmptyState(
                      icon: Icons.folder_open,
                      title: 'No Projects Found',
                      message: widget.state.searchQuery.isNotEmpty
                          ? 'No projects matching "${widget.state.searchQuery}". Try modifying your search or filter.'
                          : 'You have not created any projects yet. Start planning by creating your first electrical project.',
                      actionLabel: widget.state.searchQuery.isNotEmpty
                          ? 'Clear Filter'
                          : '+ Create Project',
                      onAction: () {
                        if (widget.state.searchQuery.isNotEmpty) {
                          _searchController.clear();
                          widget.state.setSearchQuery('');
                          widget.state.setStatusFilter(null);
                        } else {
                          Navigator.push(
                            context,
                            MaterialPageRoute(
                              builder: (_) =>
                                  CreateProjectScreen(state: widget.state),
                            ),
                          );
                        }
                      },
                    )
                  : ListView.separated(
                      padding: const EdgeInsets.fromLTRB(20, 8, 20, 80),
                      itemCount: projects.length,
                      separatorBuilder: (_, _) => const SizedBox(height: 12),
                      itemBuilder: (context, index) {
                        final project = projects[index];
                        return _buildProjectCard(context, project, isDark);
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFilterChip(String label, ProjectStatus? status, bool isDark) {
    final isSelected = widget.state.statusFilter == status;

    return ChoiceChip(
      label: Text(label),
      selected: isSelected,
      onSelected: (selected) {
        widget.state.setStatusFilter(selected ? status : null);
      },
      selectedColor: AppColors.primaryBlue.withValues(
        alpha: isDark ? 0.25 : 0.12,
      ),
      backgroundColor: isDark
          ? AppColors.surfaceSecondaryDark
          : AppColors.surfaceSecondaryLight,
      side: BorderSide(
        color: isSelected
            ? AppColors.primaryBlue
            : (isDark ? AppColors.borderDark : AppColors.borderLight),
      ),
      labelStyle: TextStyle(
        fontSize: 14,
        fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
        color: isSelected
            ? AppColors.primaryBlue
            : (isDark
                  ? AppColors.textSecondaryDark
                  : AppColors.textSecondaryLight),
      ),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      visualDensity: VisualDensity.compact,
    );
  }

  Widget _buildProjectCard(BuildContext context, Project project, bool isDark) {
    return Material(
      color: isDark ? AppColors.surfaceDark : AppColors.surfaceLight,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(
          color: isDark ? AppColors.borderDark : AppColors.borderLight,
          width: 1,
        ),
      ),
      child: InkWell(
        onTap: () {
          widget.state.selectProject(project);
          Navigator.push(
            context,
            MaterialPageRoute(
              builder: (_) =>
                  ProjectOverviewScreen(state: widget.state, project: project),
            ),
          );
        },
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      project.name,
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        letterSpacing: -0.2,
                        color: isDark
                            ? AppColors.textPrimaryDark
                            : AppColors.textPrimaryLight,
                      ),
                    ),
                  ),
                  StatusBadge(status: project.status.label, isSmall: true),
                ],
              ),
              const SizedBox(height: 6),
              Row(
                children: [
                  Icon(
                    Icons.person_outline,
                    size: 14,
                    color: isDark
                        ? AppColors.textMutedDark
                        : AppColors.textMutedLight,
                  ),
                  const SizedBox(width: 4),
                  Text(
                    project.client,
                    style: TextStyle(
                      fontSize: 14,
                      color: isDark
                          ? AppColors.textSecondaryDark
                          : AppColors.textSecondaryLight,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Icon(
                    Icons.location_on_outlined,
                    size: 14,
                    color: isDark
                        ? AppColors.textMutedDark
                        : AppColors.textMutedLight,
                  ),
                  const SizedBox(width: 4),
                  Expanded(
                    child: Text(
                      project.location,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 14,
                        color: isDark
                            ? AppColors.textSecondaryDark
                            : AppColors.textSecondaryLight,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Divider(
                color: isDark ? AppColors.borderDark : AppColors.borderLight,
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Updated ${Formatters.formatRelativeDate(project.updatedAt)}',
                    style: TextStyle(
                      fontSize: 14,
                      color: isDark
                          ? AppColors.textMutedDark
                          : AppColors.textMutedLight,
                    ),
                  ),
                  Row(
                    children: [
                      Text(
                        project.currentStage.title,
                        style: const TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppColors.primaryBlue,
                        ),
                      ),
                      const SizedBox(width: 4),
                      const Icon(
                        Icons.arrow_forward_ios,
                        size: 11,
                        color: AppColors.primaryBlue,
                      ),
                    ],
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}
