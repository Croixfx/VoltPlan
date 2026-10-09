import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/material.dart';

import '../../core/network/api_exceptions.dart';
import '../../features/analysis/data/analysis_repository.dart';
import '../../features/boq/data/boq_repository.dart';
import '../../features/projects/data/project_repository.dart';
import '../mock_data/mock_data.dart';
import '../models/analysis_result.dart';
import '../models/architectural_feature.dart';
import '../models/boq_item.dart';
import '../models/circuit.dart';
import '../models/cost_estimate.dart';
import '../models/electrical_point.dart';
import '../models/project.dart';
import '../models/room.dart';
import '../models/wiring_arc.dart';

class AppState extends ChangeNotifier {
  AppState() {
    _init();
  }

  // Repositories
  final ProjectRepository _projectRepo = ProjectRepository();
  final AnalysisRepository _analysisRepo = AnalysisRepository();
  final BoqRepository _boqRepo = BoqRepository();

  ThemeMode _themeMode = ThemeMode.light;
  ThemeMode get themeMode => _themeMode;

  List<Project> _projects = [];
  List<Project> get projects => _projects;

  Project? _selectedProject;
  Project? get selectedProject =>
      _selectedProject ?? (_projects.isNotEmpty ? _projects.first : null);

  String _searchQuery = '';
  String get searchQuery => _searchQuery;

  ProjectStatus? _statusFilter;
  ProjectStatus? get statusFilter => _statusFilter;

  List<Room> _rooms = [];
  List<Room> get rooms => _rooms;

  List<ElectricalPoint> _electricalPoints = [];
  List<ElectricalPoint> get electricalPoints => _electricalPoints;

  List<Circuit> _circuits = [];
  List<Circuit> get circuits => _circuits;

  List<BoqItem> _boqItems = [];
  List<BoqItem> get boqItems => _boqItems;

  ElectricalPoint? _inspectedPoint;
  ElectricalPoint? get inspectedPoint => _inspectedPoint;

  // Analysis State
  bool _isAnalyzing = false;
  bool get isAnalyzing => _isAnalyzing;

  int _analysisStage = 0; // 0 to 5
  int get analysisStage => _analysisStage;

  bool _isAnalysisFinished = false;
  bool get isAnalysisFinished => _isAnalysisFinished;

  String _analysisStatusMessage = '';
  String get analysisStatusMessage => _analysisStatusMessage;

  String? _analysisErrorMessage;
  String? get analysisErrorMessage => _analysisErrorMessage;

  // Real Backend Analysis Results
  AnalysisResult? _currentAnalysisResult;
  AnalysisResult? get currentAnalysisResult => _currentAnalysisResult;
  List<WiringArc> get wiringArcs => _currentAnalysisResult?.wiringArcs ?? [];

  List<ArchitecturalFeature> _architecturalFeatures = [];
  List<ArchitecturalFeature> get architecturalFeatures => _architecturalFeatures;

  List<String> _analysisObservations = [];
  List<String> get analysisObservations => _analysisObservations;

  List<String> _analysisWarnings = [];
  List<String> get analysisWarnings => _analysisWarnings;

  CostEstimate? _backendCostEstimate;
  CostEstimate? get backendCostEstimate => _backendCostEstimate;

  String _engineeringDisclaimer = '';
  String get engineeringDisclaimer => _engineeringDisclaimer;

  bool _isBackendConnected = false;
  bool get isBackendConnected => _isBackendConnected;

  // Profile / Settings
  String _userName = 'Eng. Patrick Mugabo';
  String get userName => _userName;

  String _companyName = 'VoltPlan Engineering Ltd';
  String get companyName => _companyName;

  String _currentStandard = 'RS IEC 60364';
  String get currentStandard => _currentStandard;

  String _unitSystem = 'Metric (mm / m / m²)';
  String get unitSystem => _unitSystem;

  bool _notificationsEnabled = true;
  bool get notificationsEnabled => _notificationsEnabled;

  void _init() {
    _projects = MockData.getProjects();
    _selectedProject = _projects.first;
    _rooms = MockData.getRooms();
    _electricalPoints = MockData.getElectricalPoints();
    _circuits = MockData.getCircuits();
    _boqItems = MockData.getBoqItems();

    // Check backend in background
    checkBackendConnection();
  }

  Future<bool> checkBackendConnection() async {
    try {
      final healthy = await _projectRepo.checkHealth();
      _isBackendConnected = healthy;
      notifyListeners();
      if (healthy) {
        await fetchBackendProjects();
      }
      return healthy;
    } catch (_) {
      _isBackendConnected = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> fetchBackendProjects() async {
    try {
      final backendProjects = await _projectRepo.getProjects();
      if (backendProjects.isNotEmpty) {
        // Merge backend projects, preserving local mock projects if not yet on backend
        final existingIds = backendProjects.map((p) => p.id).toSet();
        final localOnly = _projects.where((p) => !existingIds.contains(p.id)).toList();
        _projects = [...backendProjects, ...localOnly];
        if (_selectedProject != null) {
          final updated = _projects.firstWhere(
            (p) => p.id == _selectedProject!.id,
            orElse: () => _projects.first,
          );
          _selectedProject = updated;
        }
        notifyListeners();
      }
    } catch (_) {
      // Keep existing
    }
  }

  void setThemeMode(ThemeMode mode) {
    _themeMode = mode;
    notifyListeners();
  }

  void toggleTheme() {
    _themeMode = _themeMode == ThemeMode.dark ? ThemeMode.light : ThemeMode.dark;
    notifyListeners();
  }

  void selectProject(Project project) {
    _selectedProject = project;
    // If selecting a project that has floor plan bytes or backend ID, reset or reload
    notifyListeners();
  }

  void setSearchQuery(String query) {
    _searchQuery = query;
    notifyListeners();
  }

  void setStatusFilter(ProjectStatus? status) {
    _statusFilter = status;
    notifyListeners();
  }

  List<Project> get filteredProjects {
    return _projects.where((p) {
      final matchesQuery = _searchQuery.isEmpty ||
          p.name.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          p.client.toLowerCase().contains(_searchQuery.toLowerCase()) ||
          p.location.toLowerCase().contains(_searchQuery.toLowerCase());
      final matchesStatus = _statusFilter == null || p.status == _statusFilter;
      return matchesQuery && matchesStatus;
    }).toList();
  }

  /// Synchronous create method (retained for backward compatibility)
  Project createProject({
    required String name,
    required String client,
    required String buildingType,
    required String location,
    required String standard,
    String notes = '',
    String? floorPlanName,
    Uint8List? floorPlanBytes,
  }) {
    final newProject = Project(
      id: 'proj-${DateTime.now().millisecondsSinceEpoch}',
      name: name,
      client: client,
      buildingType: buildingType,
      location: location,
      standard: standard,
      notes: notes,
      status: ProjectStatus.inProgress,
      currentStage: floorPlanName == null
          ? ProjectStage.floorPlan
          : ProjectStage.aiAnalysis,
      updatedAt: DateTime.now(),
      createdAt: DateTime.now(),
      roomsCount: 0,
      electricalPointsCount: 0,
      circuitsCount: 0,
      estimatedCostRwf: 0,
      floorPlanName: floorPlanName,
      floorPlanBytes: floorPlanBytes,
    );

    _projects.insert(0, newProject);
    _selectedProject = newProject;
    notifyListeners();

    // Fire off async backend sync in background
    _syncNewProjectToBackend(newProject, floorPlanBytes);

    return newProject;
  }

  Future<Project> createProjectAsync({
    required String name,
    required String client,
    required String buildingType,
    required String location,
    required String standard,
    String notes = '',
    String? floorPlanName,
    Uint8List? floorPlanBytes,
  }) async {
    Project project;
    try {
      project = await _projectRepo.createProject(
        name: name,
        client: client,
        buildingType: buildingType,
        location: location,
        standard: standard,
        notes: notes,
      );

      if (floorPlanBytes != null && floorPlanBytes.isNotEmpty && floorPlanName != null) {
        project = await _projectRepo.uploadPlan(
          projectId: project.id,
          fileBytes: floorPlanBytes,
          filename: floorPlanName,
        );
        project = project.copyWith(floorPlanBytes: floorPlanBytes);
      }
    } catch (_) {
      // Local fallback
      project = Project(
        id: 'proj-${DateTime.now().millisecondsSinceEpoch}',
        name: name,
        client: client,
        buildingType: buildingType,
        location: location,
        standard: standard,
        notes: notes,
        status: ProjectStatus.inProgress,
        currentStage: floorPlanName == null
            ? ProjectStage.floorPlan
            : ProjectStage.aiAnalysis,
        updatedAt: DateTime.now(),
        createdAt: DateTime.now(),
        floorPlanName: floorPlanName,
        floorPlanBytes: floorPlanBytes,
      );
    }

    _projects.insert(0, project);
    _selectedProject = project;
    notifyListeners();
    return project;
  }

  Future<void> _syncNewProjectToBackend(Project localProject, Uint8List? bytes) async {
    try {
      final backendProj = await _projectRepo.createProject(
        name: localProject.name,
        client: localProject.client,
        buildingType: localProject.buildingType,
        location: localProject.location,
        standard: localProject.standard,
        notes: localProject.notes,
      );

      Project finalProj = backendProj;
      if (bytes != null && bytes.isNotEmpty && localProject.floorPlanName != null) {
        finalProj = await _projectRepo.uploadPlan(
          projectId: backendProj.id,
          fileBytes: bytes,
          filename: localProject.floorPlanName!,
        );
      }
      finalProj = finalProj.copyWith(floorPlanBytes: bytes);

      final idx = _projects.indexWhere((p) => p.id == localProject.id);
      if (idx != -1) {
        _projects[idx] = finalProj;
        if (_selectedProject?.id == localProject.id) {
          _selectedProject = finalProj;
        }
        notifyListeners();
      }
    } catch (_) {
      // Retain local project
    }
  }

  Future<bool> uploadProjectPlan(
    String projectId,
    String floorPlanName,
    Uint8List floorPlanBytes,
  ) async {
    try {
      final updated = await _projectRepo.uploadPlan(
        projectId: projectId,
        fileBytes: floorPlanBytes,
        filename: floorPlanName,
      );

      final finalProject = updated.copyWith(floorPlanBytes: floorPlanBytes);

      final index = _projects.indexWhere((p) => p.id == projectId);
      if (index != -1) {
        _projects[index] = finalProject;
      } else {
        _projects.insert(0, finalProject);
      }

      if (_selectedProject?.id == projectId) {
        _selectedProject = finalProject;
      }
      notifyListeners();
      return true;
    } catch (e) {
      // Fallback local update
      setProjectFloorPlan(projectId, floorPlanName, floorPlanBytes: floorPlanBytes);
      return false;
    }
  }

  void setProjectFloorPlan(
    String projectId,
    String floorPlanName, {
    Uint8List? floorPlanBytes,
  }) {
    final index = _projects.indexWhere((p) => p.id == projectId);
    if (index != -1) {
      _projects[index] = _projects[index].copyWith(
        floorPlanName: floorPlanName,
        floorPlanBytes: floorPlanBytes,
        currentStage: ProjectStage.aiAnalysis,
        updatedAt: DateTime.now(),
      );
      if (_selectedProject?.id == projectId) {
        _selectedProject = _projects[index];
      }
      notifyListeners();
    }
  }

  void advanceProjectStage(String projectId, ProjectStage nextStage) {
    final index = _projects.indexWhere((p) => p.id == projectId);
    if (index != -1) {
      _projects[index] = _projects[index].copyWith(
        currentStage: nextStage,
        updatedAt: DateTime.now(),
      );
      if (_selectedProject?.id == projectId) {
        _selectedProject = _projects[index];
      }
      notifyListeners();
    }
  }

  void inspectPoint(ElectricalPoint? point) {
    _inspectedPoint = point;
    notifyListeners();
  }

  // Real AI Analysis Execution against FastAPI Backend
  Future<void> runRealAnalysis(String projectId) async {
    _isAnalyzing = true;
    _analysisStage = 1;
    _analysisStatusMessage = 'Step 1/5: Preparing and rendering architectural floor plan...';
    _analysisErrorMessage = null;
    _isAnalysisFinished = false;
    notifyListeners();

    try {
      // If project has no backend ID (i.e. starts with 'proj-'), attempt to register it on backend first
      String effectiveProjectId = projectId;
      if (projectId.startsWith('proj-') && _selectedProject != null) {
        final currentProj = _selectedProject!;
        try {
          final created = await _projectRepo.createProject(
            name: currentProj.name,
            client: currentProj.client,
            buildingType: currentProj.buildingType,
            location: currentProj.location,
            standard: currentProj.standard,
            notes: currentProj.notes,
          );
          effectiveProjectId = created.id;

          if (currentProj.floorPlanBytes != null && currentProj.floorPlanBytes!.isNotEmpty) {
            await _projectRepo.uploadPlan(
              projectId: effectiveProjectId,
              fileBytes: currentProj.floorPlanBytes!,
              filename: currentProj.floorPlanName ?? 'floor_plan.png',
            );
          }

          final idx = _projects.indexWhere((p) => p.id == projectId);
          if (idx != -1) {
            _projects[idx] = created.copyWith(
              id: effectiveProjectId,
              floorPlanBytes: currentProj.floorPlanBytes,
              floorPlanName: currentProj.floorPlanName,
            );
            _selectedProject = _projects[idx];
          }
        } catch (e) {
          // If backend registration fails, fall back to simulation
          await runAnalysisSimulation(projectId);
          return;
        }
      }

      _analysisStage = 2;
      _analysisStatusMessage = 'Step 2/5: AI Vision model extracting rooms and architectural boundaries...';
      notifyListeners();

      // Trigger analysis pipeline
      await _analysisRepo.triggerAnalysis(effectiveProjectId);

      _analysisStage = 3;
      _analysisStatusMessage = 'Step 3/5: Applying Rwandan RS IEC 60364 electrical engineering rules...';
      notifyListeners();

      await Future.delayed(const Duration(milliseconds: 300));
      _analysisStage = 4;
      _analysisStatusMessage = 'Step 4/5: Sizing conductors, circuit breakers, and balancing phases (L1, L2, L3)...';
      notifyListeners();

      await Future.delayed(const Duration(milliseconds: 300));
      _analysisStage = 5;
      _analysisStatusMessage = 'Step 5/5: Generating Bill of Quantities & Rwandan Franc preliminary cost estimate...';
      notifyListeners();

      // Fetch structured analysis results
      final result = await _analysisRepo.getAnalysisResult(effectiveProjectId);

      _currentAnalysisResult = result;
      _rooms = result.rooms;
      _electricalPoints = result.electricalPoints;
      _circuits = result.circuits;
      _boqItems = result.boqItems;
      _backendCostEstimate = result.costEstimate;
      _architecturalFeatures = result.architecturalFeatures;
      _analysisObservations = result.observations;
      _analysisWarnings = result.warnings;
      _engineeringDisclaimer = result.engineeringDisclaimer;

      _analysisStatusMessage = 'Analysis and electrical engineering calculations completed successfully.';
      _isAnalyzing = false;
      _isAnalysisFinished = true;

      // Update project record
      final idx = _projects.indexWhere((p) => p.id == effectiveProjectId || p.id == projectId);
      if (idx != -1) {
        final estCost = result.costEstimate?.grandTotalRwf ?? grandTotalCost;
        _projects[idx] = _projects[idx].copyWith(
          id: effectiveProjectId,
          currentStage: ProjectStage.electricalDesign,
          status: ProjectStatus.completed,
          roomsCount: result.rooms.length,
          electricalPointsCount: result.electricalPoints.length,
          circuitsCount: result.circuits.length,
          estimatedCostRwf: estCost,
          updatedAt: DateTime.now(),
        );
        _selectedProject = _projects[idx];
      }
      notifyListeners();
    } catch (e) {
      // If error occurred, check if we should fall back to simulation or display real error
      if (e is ApiException) {
        _analysisErrorMessage = e.message;
      } else {
        _analysisErrorMessage = e.toString();
      }

      // If network unreachable, run simulation as graceful fallback
      if (_analysisErrorMessage!.contains('Network connection') ||
          _analysisErrorMessage!.contains('Failed to connect') ||
          _analysisErrorMessage!.contains('SocketException')) {
        await runAnalysisSimulation(projectId);
      } else {
        _isAnalyzing = false;
        notifyListeners();
      }
    }
  }

  // AI Analysis simulation (graceful offline fallback)
  Future<void> runAnalysisSimulation(String projectId) async {
    _isAnalyzing = true;
    _analysisStage = 1;
    _analysisStatusMessage = 'Step 1/5: Preparing floor plan document...';
    _isAnalysisFinished = false;
    _analysisErrorMessage = null;
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 600));
    _analysisStage = 2;
    _analysisStatusMessage = 'Step 2/5: AI Vision model extracting rooms and architectural boundaries...';
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 700));
    _analysisStage = 3;
    _analysisStatusMessage = 'Step 3/5: Applying RS IEC 60364 electrical rules...';
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 700));
    _analysisStage = 4;
    _analysisStatusMessage = 'Step 4/5: Sizing conductors and balancing circuit phases...';
    notifyListeners();

    await Future.delayed(const Duration(milliseconds: 600));
    _analysisStage = 5;
    _analysisStatusMessage = 'Step 5/5: Generating Bill of Quantities & Rwandan Franc cost estimate...';
    _isAnalyzing = false;
    _isAnalysisFinished = true;

    final index = _projects.indexWhere((p) => p.id == projectId);
    if (index != -1) {
      _projects[index] = _projects[index].copyWith(
        currentStage: ProjectStage.electricalDesign,
        roomsCount: _rooms.isNotEmpty ? _rooms.length : 8,
        electricalPointsCount: _electricalPoints.isNotEmpty ? _electricalPoints.length : 24,
        circuitsCount: _circuits.isNotEmpty ? _circuits.length : 5,
        estimatedCostRwf: grandTotalCost,
        updatedAt: DateTime.now(),
      );
      if (_selectedProject?.id == projectId) {
        _selectedProject = _projects[index];
      }
    }
    notifyListeners();
  }

  void resetAnalysis() {
    _isAnalyzing = false;
    _analysisStage = 0;
    _isAnalysisFinished = false;
    _analysisErrorMessage = null;
    notifyListeners();
  }

  Future<void> reloadBoqAndCost(String projectId) async {
    try {
      final items = await _boqRepo.getBoqItems(projectId);
      final cost = await _boqRepo.getCostEstimate(projectId);
      if (items.isNotEmpty) {
        _boqItems = items;
      }
      _backendCostEstimate = cost;
      notifyListeners();
    } catch (_) {
      // Keep existing items if offline
    }
  }

  void setInspectedPoint(ElectricalPoint? point) {
    _inspectedPoint = point;
    notifyListeners();
  }

  void updatePointPosition(String pointId, double newX, double newY) {
    final clampedX = newX.clamp(0.015, 0.985);
    final clampedY = newY.clamp(0.015, 0.985);

    final idx = _electricalPoints.indexWhere((p) => p.id == pointId);
    if (idx == -1) return;

    final oldPoint = _electricalPoints[idx];
    final updatedPoint = oldPoint.copyWith(
      xRatio: double.parse(clampedX.toStringAsFixed(3)),
      yRatio: double.parse(clampedY.toStringAsFixed(3)),
    );

    _electricalPoints[idx] = updatedPoint;

    if (_inspectedPoint?.id == pointId) {
      _inspectedPoint = updatedPoint;
    }

    _recomputeWiringArcs();
    notifyListeners();
  }

  void nudgePoint(String pointId, double dxRatio, double dyRatio) {
    final idx = _electricalPoints.indexWhere((p) => p.id == pointId);
    if (idx == -1) return;
    final p = _electricalPoints[idx];
    updatePointPosition(pointId, p.xRatio + dxRatio, p.yRatio + dyRatio);
  }

  void _recomputeWiringArcs() {
    if (_currentAnalysisResult == null) return;

    final roomSwitches = <String, List<ElectricalPoint>>{};
    final roomLights = <String, List<ElectricalPoint>>{};

    for (final p in _electricalPoints) {
      if (p.type == ElectricalPointType.switchPoint) {
        roomSwitches.putIfAbsent(p.roomId, () => []).add(p);
      } else if (p.type == ElectricalPointType.light || p.type == ElectricalPointType.downlight) {
        roomLights.putIfAbsent(p.roomId, () => []).add(p);
      }
    }

    final newArcs = <WiringArc>[];
    int arcIdx = 1;

    for (final entry in roomLights.entries) {
      final roomId = entry.key;
      final lights = entry.value;
      final switches = roomSwitches[roomId] ?? [];
      if (switches.isEmpty) continue;

      for (final lt in lights) {
        ElectricalPoint nearestSw = switches.first;
        double minDist = double.infinity;
        for (final sw in switches) {
          final dX = sw.xRatio - lt.xRatio;
          final dY = sw.yRatio - lt.yRatio;
          final dist = math.sqrt(dX * dX + dY * dY);
          if (dist < minDist) {
            minDist = dist;
            nearestSw = sw;
          }
        }

        final midX = (nearestSw.xRatio + lt.xRatio) / 2.0;
        final midY = (nearestSw.yRatio + lt.yRatio) / 2.0;
        final dx = lt.xRatio - nearestSw.xRatio;
        final dy = lt.yRatio - nearestSw.yRatio;
        final chord = math.sqrt(dx * dx + dy * dy);

        const sag = 0.22;
        final nx = chord > 1e-4 ? -dy / chord : 0.0;
        final ny = chord > 1e-4 ? dx / chord : 0.0;

        final cpX = midX + nx * (chord * sag);
        final cpY = midY + ny * (chord * sag);

        newArcs.add(
          WiringArc(
            id: 'arc_${arcIdx.toString().padLeft(3, '0')}',
            circuitId: nearestSw.circuitId,
            roomId: roomId,
            switchId: nearestSw.id,
            luminaireId: lt.id,
            startPoint: [nearestSw.xRatio, nearestSw.yRatio],
            controlPoint: [double.parse(cpX.toStringAsFixed(3)), double.parse(cpY.toStringAsFixed(3))],
            endPoint: [lt.xRatio, lt.yRatio],
            lengthNorm: chord * (1.0 + (8.0 * sag * sag) / 3.0),
          ),
        );
        arcIdx++;
      }
    }

    _currentAnalysisResult = _currentAnalysisResult!.copyWith(
      wiringArcs: newArcs,
      electricalPoints: List.from(_electricalPoints),
    );
  }

  // BOQ Updates
  void updateBoqQuantity(String itemId, double newQuantity) {
    final index = _boqItems.indexWhere((item) => item.id == itemId);
    if (index != -1) {
      _boqItems[index] = _boqItems[index].copyWith(
        quantity: newQuantity < 0 ? 0 : newQuantity,
      );
      _updateProjectTotalFromBoq();
      notifyListeners();
    }
  }

  num get totalBoqCost {
    return _boqItems.fold<num>(0, (sum, item) => sum + item.totalRwf);
  }

  num get materialsCost {
    if (_backendCostEstimate != null) {
      return _backendCostEstimate!.materialsCostRwf;
    }
    return totalBoqCost;
  }

  num get laborCost {
    if (_backendCostEstimate != null) {
      return _backendCostEstimate!.laborCostRwf;
    }
    return (totalBoqCost * 0.28).round();
  }

  num get contingencyCost {
    if (_backendCostEstimate != null) {
      return _backendCostEstimate!.contingencyCostRwf;
    }
    return (totalBoqCost * 0.12).round();
  }

  num get grandTotalCost {
    if (_backendCostEstimate != null) {
      return _backendCostEstimate!.grandTotalRwf;
    }
    return materialsCost + laborCost + contingencyCost;
  }

  void _updateProjectTotalFromBoq() {
    if (_selectedProject != null) {
      final idx = _projects.indexWhere((p) => p.id == _selectedProject!.id);
      if (idx != -1) {
        _projects[idx] = _projects[idx].copyWith(
          estimatedCostRwf: grandTotalCost,
        );
        _selectedProject = _projects[idx];
      }
    }
  }

  // Profile updates
  void updateProfile({
    String? name,
    String? company,
    String? standard,
    String? unitSystem,
    bool? notifications,
  }) {
    if (name != null) _userName = name;
    if (company != null) _companyName = company;
    if (standard != null) _currentStandard = standard;
    if (unitSystem != null) _unitSystem = unitSystem;
    if (notifications != null) _notificationsEnabled = notifications;
    notifyListeners();
  }
}
