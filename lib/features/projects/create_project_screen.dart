import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:http/http.dart' as http;
import '../../core/constants/app_colors.dart';
import '../../core/constants/app_constants.dart';
import '../../core/widgets/app_button.dart';
import '../../shared/state/app_state.dart';
import 'project_overview_screen.dart';

DateTime? _lastNominatimRequestAt;

class CreateProjectScreen extends StatefulWidget {
  final AppState state;

  const CreateProjectScreen({super.key, required this.state});

  @override
  State<CreateProjectScreen> createState() => _CreateProjectScreenState();
}

class _CreateProjectScreenState extends State<CreateProjectScreen> {
  final _formKey = GlobalKey<FormState>();

  final _nameController = TextEditingController();
  final _clientController = TextEditingController();
  final _locationController = TextEditingController();
  final _notesController = TextEditingController();

  _SelectedPlan? _selectedPlan;
  String _selectedBuildingType = AppConstants.buildingTypes.first;
  String _selectedStandard = AppConstants.electricalStandards.first;
  bool _isSubmitting = false;
  bool _isPickingPlan = false;

  @override
  void dispose() {
    _nameController.dispose();
    _clientController.dispose();
    _locationController.dispose();
    _notesController.dispose();
    super.dispose();
  }

  void _submit() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _isSubmitting = true);

    final newProject = await widget.state.createProjectAsync(
      name: _nameController.text.trim(),
      client: _clientController.text.trim(),
      buildingType: _selectedBuildingType,
      location: _locationController.text.trim(),
      standard: _selectedStandard,
      notes: _notesController.text.trim(),
      floorPlanName: _selectedPlan?.name,
      floorPlanBytes: _selectedPlan?.bytes,
    );

    if (mounted) {
      setState(() => _isSubmitting = false);
      // Replace create screen with Project Overview
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(
          builder: (_) =>
              ProjectOverviewScreen(state: widget.state, project: newProject),
        ),
      );
    }
  }

  Future<void> _pickFloorPlan() async {
    if (_isPickingPlan || _isSubmitting) return;

    setState(() => _isPickingPlan = true);
    try {
      final file = await FilePicker.pickFile(
        dialogTitle: 'Select Architectural Plan',
        type: FileType.custom,
        allowedExtensions: const ['pdf', 'png', 'jpg', 'jpeg'],
      );

      if (file == null || !mounted) {
        if (mounted) setState(() => _isPickingPlan = false);
        return;
      }

      final size = await file.length();
      if (!mounted) return;

      final bytes = await file.readAsBytes();
      if (!mounted) return;

      final effectiveSize = size ?? bytes.length;
      if (effectiveSize > 25 * 1024 * 1024) {
        _showMessage('Choose a plan smaller than 25 MB.');
        return;
      }

      setState(() {
        _selectedPlan = _SelectedPlan(
          name: file.name,
          size: effectiveSize,
          extension: file.extension,
          bytes: bytes,
        );
        _nameController.text = _projectNameFromFile(file.name);
      });
    } catch (error) {
      if (mounted) {
        _showMessage('Could not open the file picker: $error');
      }
    } finally {
      if (mounted) setState(() => _isPickingPlan = false);
    }
  }

  String _projectNameFromFile(String fileName) {
    final nameWithoutExtension = fileName.replaceFirst(RegExp(r'\.[^.]+$'), '');
    return nameWithoutExtension
        .replaceAll(RegExp(r'[_-]+'), ' ')
        .replaceAll(RegExp(r'\s+'), ' ')
        .trim();
  }

  Future<void> _searchLocation() async {
    final location = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (_) => const _LocationSearchSheet(),
    );
    if (location != null && mounted) {
      setState(() => _locationController.text = location);
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;

    return Scaffold(
      appBar: AppBar(title: const Text('Create Project')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 20),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // Plan selection stays on this form so project details and
                // architectural documents can be submitted together.
                Material(
                  color: isDark
                      ? AppColors.surfaceSecondaryDark
                      : AppColors.surfaceSecondaryLight,
                  borderRadius: BorderRadius.circular(10),
                  child: InkWell(
                    borderRadius: BorderRadius.circular(10),
                    onTap: _isPickingPlan ? null : _pickFloorPlan,
                    child: Container(
                      padding: const EdgeInsets.all(16),
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: isDark
                              ? AppColors.borderDark
                              : AppColors.borderLight,
                        ),
                      ),
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              _selectedPlan == null
                                  ? 'Upload a PDF or image plan (up to 25 MB). The filename will fill the project name.'
                                  : 'Plan selected. Its filename has been used as the project name.',
                              style: TextStyle(
                                fontSize: 14,
                                color: isDark
                                    ? AppColors.textSecondaryDark
                                    : AppColors.textSecondaryLight,
                                height: 1.3,
                              ),
                            ),
                          ),
                          const SizedBox(width: 12),
                          AppButton(
                            label: _selectedPlan == null ? 'Choose plan' : 'Change',
                            icon: Icons.upload_file_outlined,
                            height: 40,
                            isLoading: _isPickingPlan,
                            onPressed: _pickFloorPlan,
                          ),
                        ],
                      ),
                    ),
                  ),
                ),

                if (_selectedPlan != null) ...[
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 12,
                      vertical: 10,
                    ),
                    decoration: BoxDecoration(
                      color: isDark
                          ? AppColors.surfaceDark
                          : AppColors.surfaceLight,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: isDark
                            ? AppColors.borderDark
                            : AppColors.borderLight,
                      ),
                    ),
                    child: Row(
                      children: [
                        Icon(
                          _selectedPlan!.extension?.toLowerCase() == 'pdf'
                              ? Icons.picture_as_pdf_outlined
                              : Icons.image_outlined,
                          color: AppColors.primaryBlue,
                        ),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            _selectedPlan!.name,
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              fontSize: 14,
                              color: isDark
                                  ? AppColors.textPrimaryDark
                                  : AppColors.textPrimaryLight,
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        Text(
                          '${(_selectedPlan!.size / (1024 * 1024)).toStringAsFixed(1)} MB',
                          style: TextStyle(
                            fontSize: 13,
                            color: isDark
                                ? AppColors.textMutedDark
                                : AppColors.textMutedLight,
                          ),
                        ),
                        IconButton(
                          tooltip: 'Remove selected plan',
                          onPressed: () => setState(() {
                            _selectedPlan = null;
                          }),
                          icon: const Icon(Icons.close, size: 18),
                        ),
                      ],
                    ),
                  ),
                ],

                const SizedBox(height: 24),

                // Field: Project Name
                _buildFieldLabel('Project Name *', isDark),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _nameController,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(
                    hintText: 'e.g. Modern Family House',
                    prefixIcon: Icon(Icons.business_outlined, size: 20),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter a project name';
                    }
                    return null;
                  },
                ),

                const SizedBox(height: 18),

                // Field: Client Name
                _buildFieldLabel('Client Name *', isDark),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _clientController,
                  textCapitalization: TextCapitalization.words,
                  decoration: const InputDecoration(
                    hintText: 'e.g. Dr. Emmanuel R. / Inzovu Ltd',
                    prefixIcon: Icon(Icons.person_outline, size: 20),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please enter a client name';
                    }
                    return null;
                  },
                ),

                const SizedBox(height: 18),

                // Field: Building Type
                _buildFieldLabel('Building Type *', isDark),
                const SizedBox(height: 6),
                DropdownButtonFormField<String>(
                  initialValue: _selectedBuildingType,
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.apartment_outlined, size: 20),
                  ),
                  dropdownColor: isDark
                      ? AppColors.surfaceDark
                      : AppColors.surfaceLight,
                  items: AppConstants.buildingTypes.map((type) {
                    return DropdownMenuItem(value: type, child: Text(type));
                  }).toList(),
                  onChanged: (val) {
                    if (val != null) {
                      setState(() => _selectedBuildingType = val);
                    }
                  },
                ),

                const SizedBox(height: 18),

                // Field: Location
                _buildFieldLabel('Location *', isDark),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _locationController,
                  decoration: InputDecoration(
                    hintText: 'e.g. Kigali, Kicukiro Sector',
                    prefixIcon: const Icon(
                      Icons.location_on_outlined,
                      size: 20,
                    ),
                    suffixIcon: IconButton(
                      tooltip: 'Search address',
                      onPressed: _searchLocation,
                      icon: const Icon(Icons.search),
                    ),
                  ),
                  validator: (value) {
                    if (value == null || value.trim().isEmpty) {
                      return 'Please specify the project location';
                    }
                    return null;
                  },
                ),

                const SizedBox(height: 18),

                // Field: Electrical Standard
                _buildFieldLabel('Electrical Standard *', isDark),
                const SizedBox(height: 6),
                DropdownButtonFormField<String>(
                  initialValue: _selectedStandard,
                  isExpanded: true,
                  decoration: const InputDecoration(
                    prefixIcon: Icon(Icons.verified_outlined, size: 20),
                  ),
                  dropdownColor: isDark
                      ? AppColors.surfaceDark
                      : AppColors.surfaceLight,
                  items: AppConstants.electricalStandards.map((std) {
                    return DropdownMenuItem(
                      value: std,
                      child: Text(
                        std,
                        style: const TextStyle(fontSize: 14),
                        overflow: TextOverflow.ellipsis,
                      ),
                    );
                  }).toList(),
                  onChanged: (val) {
                    if (val != null) setState(() => _selectedStandard = val);
                  },
                ),

                const SizedBox(height: 18),

                // Field: Notes
                _buildFieldLabel('Engineering Notes / Scope', isDark),
                const SizedBox(height: 6),
                TextFormField(
                  controller: _notesController,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    hintText:
                        'Add special client requirements (solar backup, heavy appliances, EV charger provision)...',
                    alignLabelWithHint: true,
                  ),
                ),

                const SizedBox(height: 32),

                // Submit Button
                AppButton(
                  label: 'Create Project',
                  icon: Icons.check,
                  isFullWidth: true,
                  isLoading: _isSubmitting,
                  onPressed: _submit,
                ),

                const SizedBox(height: 24),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildFieldLabel(String label, bool isDark) {
    return Text(
      label,
      style: TextStyle(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: isDark ? AppColors.textPrimaryDark : AppColors.textPrimaryLight,
      ),
    );
  }
}

class _SelectedPlan {
  final String name;
  final int size;
  final String? extension;
  final Uint8List bytes;

  const _SelectedPlan({
    required this.name,
    required this.size,
    required this.extension,
    required this.bytes,
  });
}

class _LocationSearchSheet extends StatefulWidget {
  const _LocationSearchSheet();

  @override
  State<_LocationSearchSheet> createState() => _LocationSearchSheetState();
}

class _LocationSearchSheetState extends State<_LocationSearchSheet> {
  final _queryController = TextEditingController();
  List<String> _results = [];
  String? _error;
  bool _isSearching = false;

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _search() async {
    final query = _queryController.text.trim();
    if (query.length < 3) {
      setState(() {
        _error = 'Enter at least 3 characters to search.';
        _results = [];
      });
      return;
    }

    if (_isSearching) return;
    setState(() {
      _isSearching = true;
      _error = null;
      _results = [];
    });

    try {
      final previousRequest = _lastNominatimRequestAt;
      if (previousRequest != null) {
        final elapsed = DateTime.now().difference(previousRequest);
        if (elapsed < const Duration(seconds: 1)) {
          await Future<void>.delayed(const Duration(seconds: 1) - elapsed);
        }
      }
      if (!mounted) return;
      _lastNominatimRequestAt = DateTime.now();

      final uri = Uri.https('nominatim.openstreetmap.org', '/search', {
        'q': query,
        'format': 'jsonv2',
        'addressdetails': '1',
        'limit': '5',
        'accept-language': 'en',
      });
      final response = await http
          .get(
            uri,
            headers: kIsWeb
                ? const {}
                : const {
                    'User-Agent': 'VoltPlan/1.0 (project location search)',
                  },
          )
          .timeout(const Duration(seconds: 12));

      if (!mounted) return;
      if (response.statusCode != 200) {
        setState(() {
          _error =
              'Address search failed (HTTP ${response.statusCode}). Please try again.';
        });
        return;
      }

      final decoded = jsonDecode(response.body);
      if (decoded is! List) {
        throw const FormatException('Unexpected address search response.');
      }
      final results = decoded
          .whereType<Map<String, dynamic>>()
          .map((entry) => entry['display_name'])
          .whereType<String>()
          .map((name) => name.trim())
          .where((name) => name.isNotEmpty)
          .toList();

      setState(() {
        _results = results;
        if (results.isEmpty) {
          _error = 'No matching addresses found. Try a more specific search.';
        }
      });
    } on http.ClientException {
      if (mounted) {
        setState(() {
          _error = 'Could not connect to OpenStreetMap. Check your connection.';
        });
      }
    } on TimeoutException {
      if (mounted) {
        setState(() {
          _error = 'Address search timed out. Please try again.';
        });
      }
    } on FormatException {
      if (mounted) {
        setState(() {
          _error =
              'OpenStreetMap returned an invalid response. Please try again.';
        });
      }
    } finally {
      if (mounted) setState(() => _isSearching = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final isDark = Theme.of(context).brightness == Brightness.dark;
    final screenHeight = MediaQuery.sizeOf(context).height;
    final keyboardHeight = MediaQuery.viewInsetsOf(context).bottom;
    final availableHeight = (screenHeight - keyboardHeight)
        .clamp(320.0, screenHeight)
        .toDouble();
    return Padding(
      padding: EdgeInsets.only(
        left: 20,
        top: 20,
        right: 20,
        bottom: MediaQuery.viewInsetsOf(context).bottom + 20,
      ),
      child: SizedBox(
        height: availableHeight * 0.72,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Find project address',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            const SizedBox(height: 6),
            Text(
              'Search for a place, then select the matching address.',
              style: TextStyle(
                fontSize: 14,
                color: isDark
                    ? AppColors.textSecondaryDark
                    : AppColors.textSecondaryLight,
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _queryController,
                    autofocus: true,
                    textInputAction: TextInputAction.search,
                    onSubmitted: (_) => _search(),
                    decoration: const InputDecoration(
                      hintText: 'Address, neighborhood, or city',
                      prefixIcon: Icon(Icons.search),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                AppButton(
                  label: 'Search',
                  isLoading: _isSearching,
                  onPressed: _search,
                ),
              ],
            ),
            const SizedBox(height: 8),
            Text(
              'Search queries are sent to OpenStreetMap Nominatim.',
              style: TextStyle(
                fontSize: 12,
                color: isDark
                    ? AppColors.textMutedDark
                    : AppColors.textMutedLight,
              ),
            ),
            const SizedBox(height: 12),
            Expanded(
              child: _isSearching
                  ? const Center(child: CircularProgressIndicator())
                  : _error != null
                  ? Center(
                      child: Text(
                        _error!,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontSize: 14,
                          color: isDark
                              ? AppColors.textSecondaryDark
                              : AppColors.textSecondaryLight,
                        ),
                      ),
                    )
                  : ListView.separated(
                      itemCount: _results.length,
                      separatorBuilder: (_, _) => Divider(
                        color: isDark
                            ? AppColors.borderDark
                            : AppColors.borderLight,
                      ),
                      itemBuilder: (context, index) {
                        final address = _results[index];
                        return ListTile(
                          contentPadding: EdgeInsets.zero,
                          leading: const Icon(
                            Icons.location_on_outlined,
                            color: AppColors.primaryBlue,
                          ),
                          title: Text(
                            address,
                            maxLines: 3,
                            overflow: TextOverflow.ellipsis,
                          ),
                          onTap: () => Navigator.pop(context, address),
                        );
                      },
                    ),
            ),
            Center(
              child: Text(
                '© OpenStreetMap contributors',
                style: TextStyle(
                  fontSize: 12,
                  color: isDark
                      ? AppColors.textMutedDark
                      : AppColors.textMutedLight,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
