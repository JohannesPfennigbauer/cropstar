import 'package:flutter/material.dart';
import '../models/plant.dart';
import '../services/api_service.dart';

class PlantDetailScreen extends StatefulWidget {
  final String scientificName;

  const PlantDetailScreen({super.key, required this.scientificName});

  @override
  State<PlantDetailScreen> createState() => _PlantDetailScreenState();
}

class _PlantDetailScreenState extends State<PlantDetailScreen> {
  Plant? _plant;
  bool _isLoading = true;
  bool _isEditing = false;
  bool _isSaving = false;
  String _errorMessage = '';

  // Controllers for editing
  final Map<String, TextEditingController> _propertyControllers = {};
  final List<TraitEditController> _traitControllers = [];
  final List<SoilClaimEditController> _soilClaimControllers = [];
  final List<WeedingStrategyEditController> _strategyControllers = [];

  @override
  void initState() {
    super.initState();
    _loadPlantData();
  }

  @override
  void dispose() {
    _disposeControllers();
    super.dispose();
  }

  void _disposeControllers() {
    for (final controller in _propertyControllers.values) {
      controller.dispose();
    }
    for (final controller in _traitControllers) {
      controller.dispose();
    }
    for (final controller in _soilClaimControllers) {
      controller.dispose();
    }
    for (final controller in _strategyControllers) {
      controller.dispose();
    }
  }

  Future<void> _loadPlantData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = '';
    });

    try {
      final plant = await ApiService.getPlant(widget.scientificName);
      setState(() {
        _plant = plant;
        _isLoading = false;
      });
      _initializeControllers();
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  void _initializeControllers() {
    if (_plant == null) return;

    // Property controllers
    _propertyControllers.clear();
    _propertyControllers['common_name'] = TextEditingController(text: _plant!.properties.commonName ?? '');
    _propertyControllers['german_name'] = TextEditingController(text: _plant!.properties.germanName ?? '');
    _propertyControllers['family'] = TextEditingController(text: _plant!.properties.family ?? '');
    _propertyControllers['genus'] = TextEditingController(text: _plant!.properties.genus ?? '');

    // Trait controllers
    _traitControllers.clear();
    for (final trait in _plant!.traits) {
      _traitControllers.add(TraitEditController(
        nameController: TextEditingController(text: trait.plantTraitName),
        valueController: TextEditingController(text: trait.plantTraitValue ?? ''),
      ));
    }

    // Soil claim controllers
    _soilClaimControllers.clear();
    for (final claim in _plant!.soilClaims) {
      _soilClaimControllers.add(SoilClaimEditController(
        propertyController: TextEditingController(text: claim.soilProperty),
        conditionController: TextEditingController(text: claim.soilCondition ?? ''),
      ));
    }

    // Strategy controllers
    _strategyControllers.clear();
    for (final strategy in _plant!.weedingStrategies) {
      _strategyControllers.add(WeedingStrategyEditController(
        typeController: TextEditingController(text: strategy.type),
        nameController: TextEditingController(text: strategy.strategyName),
        germanNameController: TextEditingController(text: strategy.germanName ?? ''),
        confidenceController: TextEditingController(text: strategy.confidence?.toString() ?? ''),
        relationshipTypeController: TextEditingController(text: strategy.relationshipType ?? ''),
      ));
    }
  }

  void _toggleEditMode() {
    setState(() {
      _isEditing = !_isEditing;
      if (_isEditing) {
        _initializeControllers();
      }
    });
  }

  Future<void> _saveChanges() async {
    if (_plant == null) return;

    setState(() {
      _isSaving = true;
      _errorMessage = '';
    });

    try {
      // Create updated plant object
      final updatedProperties = PlantProperties(
        commonName: _propertyControllers['common_name']?.text,
        germanName: _propertyControllers['german_name']?.text,
        family: _propertyControllers['family']?.text,
        genus: _propertyControllers['genus']?.text,
      );

      final updatedTraits = _traitControllers.map((controller) => Trait(
        plantTraitName: controller.nameController.text,
        plantTraitValue: controller.valueController.text.isEmpty ? null : controller.valueController.text,
      )).toList();

      final updatedSoilClaims = _soilClaimControllers.map((controller) => SoilClaim(
        soilProperty: controller.propertyController.text,
        soilCondition: controller.conditionController.text.isEmpty ? null : controller.conditionController.text,
      )).toList();

      final updatedStrategies = _strategyControllers.map((controller) => WeedingStrategy(
        type: controller.typeController.text,
        strategyName: controller.nameController.text,
        germanName: controller.germanNameController.text.isEmpty ? null : controller.germanNameController.text,
        confidence: controller.confidenceController.text.isEmpty ? null : double.tryParse(controller.confidenceController.text),
        relationshipType: controller.relationshipTypeController.text.isEmpty ? null : controller.relationshipTypeController.text,
      )).toList();

      final updatedPlant = _plant!.copyWith(
        properties: updatedProperties,
        traits: updatedTraits,
        soilClaims: updatedSoilClaims,
        weedingStrategies: updatedStrategies,
      );

      final success = await ApiService.updatePlant(widget.scientificName, updatedPlant);

      if (success) {
        setState(() {
          _plant = updatedPlant;
          _isEditing = false;
          _isSaving = false;
        });
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text('Plant updated successfully!'),
              backgroundColor: Colors.green,
            ),
          );
        }
      }
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isSaving = false;
      });
    }
  }

  void _addTrait() {
    setState(() {
      _traitControllers.add(TraitEditController(
        nameController: TextEditingController(),
        valueController: TextEditingController(),
      ));
    });
  }

  void _removeTrait(int index) {
    setState(() {
      _traitControllers[index].dispose();
      _traitControllers.removeAt(index);
    });
  }

  void _addSoilClaim() {
    setState(() {
      _soilClaimControllers.add(SoilClaimEditController(
        propertyController: TextEditingController(),
        conditionController: TextEditingController(),
      ));
    });
  }

  void _removeSoilClaim(int index) {
    setState(() {
      _soilClaimControllers[index].dispose();
      _soilClaimControllers.removeAt(index);
    });
  }

  void _addStrategy() {
    setState(() {
      _strategyControllers.add(WeedingStrategyEditController(
        typeController: TextEditingController(),
        nameController: TextEditingController(),
        germanNameController: TextEditingController(),
        confidenceController: TextEditingController(),
        relationshipTypeController: TextEditingController(),
      ));
    });
  }

  void _removeStrategy(int index) {
    setState(() {
      _strategyControllers[index].dispose();
      _strategyControllers.removeAt(index);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text(_plant?.scientificName ?? widget.scientificName),
        backgroundColor: Colors.green.shade700,
        foregroundColor: Colors.white,
        actions: [
          if (_plant != null && !_isSaving)
            IconButton(
              icon: Icon(_isEditing ? Icons.close : Icons.edit),
              onPressed: _toggleEditMode,
            ),
          if (_isEditing && !_isSaving)
            IconButton(
              icon: const Icon(Icons.save),
              onPressed: _saveChanges,
            ),
          if (_isSaving)
            const Padding(
              padding: EdgeInsets.all(16.0),
              child: SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(
                  strokeWidth: 2,
                  valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
                ),
              ),
            ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : _errorMessage.isNotEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        Icons.error_outline,
                        size: 64,
                        color: Colors.red.shade400,
                      ),
                      const SizedBox(height: 16),
                      Text(
                        'Error',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.red.shade600,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 32),
                        child: Text(
                          _errorMessage,
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.red.shade500,
                          ),
                          textAlign: TextAlign.center,
                        ),
                      ),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _loadPlantData,
                        child: const Text('Try Again'),
                      ),
                    ],
                  ),
                )
              : _plant == null
                  ? const Center(child: Text('No plant data available'))
                  : Padding(
                      padding: const EdgeInsets.all(40.0),
                      child: Stack(
                        children: [
                          Column(
                            children: [
                              // Upper row: General Information and Plant Traits
                              Expanded(
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: _buildGeneralInformationSection(),
                                    ),
                                    const SizedBox(width: 20),
                                    Expanded(
                                      child: _buildTraitsSection(),
                                    ),
                                  ],
                                ),
                              ),
                              const SizedBox(height: 20),
                              // Lower row: Soil Claims and Weeding Strategies
                              Expanded(
                                child: Row(
                                  children: [
                                    Expanded(
                                      child: _buildWeedingStrategiesSection(),
                                    ),
                                    const SizedBox(width: 20),
                                    Expanded(
                                      child: _buildSoilClaimsSection(),
                                    ),
                                  ],
                                ),
                              ),
                            ],
                          ),
                          // Centered circular plant image
                          Center(
                            child: Container(
                              width: 500,
                              height: 500,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: Colors.white,
                                border: Border.all(color: Colors.green.shade300, width: 4),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.black.withValues(alpha: 0.2),
                                    blurRadius: 8,
                                    offset: const Offset(0, 2),
                                  ),
                                ],
                              ),
                              child: ClipOval(
                                child: _buildPlantImage(),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
    );
  }

  Widget _buildSection(String title, IconData icon, Color color, List<Widget> children, CutoutPosition cutoutPosition) {
    return Expanded(
      child: ClipPath(
        clipper: CardCutoutClipper(cutoutPosition),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(16.0),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.center,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Icon(icon, color: color),
                    const SizedBox(width: 8),
                    Text(
                      title,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.center,
                      children: children,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildGeneralInformationSection() {
    return _buildSection(
      'General Information',
      Icons.info_outline,
      Colors.blue,
      [
        _buildInfoItem('Scientific Name', _plant?.scientificName ?? widget.scientificName, 'scientific_name'),
        _buildInfoItem('Common Name', _plant!.properties.commonName, 'common_name'),
        _buildInfoItem('German Name', _plant!.properties.germanName, 'german_name'),
        _buildInfoItem('Family', _plant!.properties.family, 'family'),
        _buildInfoItem('Genus', _plant!.properties.genus, 'genus'),
      ],
      CutoutPosition.bottomRight,
    );
  }

  Widget _buildTraitsSection() {
    return _buildSection(
      'Plant Traits',
      Icons.eco,
      Colors.green,
      [
        if (_plant!.traits.isEmpty && !_isEditing)
          const Text('No traits available', style: TextStyle(color: Colors.grey)),
        ..._isEditing
            ? _traitControllers.asMap().entries.map((entry) {
                final index = entry.key;
                final controller = entry.value;
                return _buildEditableTraitItem(controller, index);
              }).toList()
            : _plant!.traits.map((trait) => _buildTraitItem(trait)).toList(),
        if (_isEditing)
          ElevatedButton.icon(
            onPressed: _addTrait,
            icon: const Icon(Icons.add),
            label: const Text('Add Trait'),
          ),
      ],
      CutoutPosition.bottomLeft,
    );
  }

  Widget _buildSoilClaimsSection() {
    return _buildSection(
      'Soil Claims',
      Icons.terrain,
      Colors.brown,
      [
        if (_plant!.soilClaims.isEmpty && !_isEditing)
          const Text('No soil claims available', style: TextStyle(color: Colors.grey)),
        ..._isEditing
            ? _soilClaimControllers.asMap().entries.map((entry) {
                final index = entry.key;
                final controller = entry.value;
                return _buildEditableSoilClaimItem(controller, index);
              }).toList()
            : _plant!.soilClaims.map((claim) => _buildSoilClaimItem(claim)).toList(),
        if (_isEditing)
          ElevatedButton.icon(
            onPressed: _addSoilClaim,
            icon: const Icon(Icons.add),
            label: const Text('Add Soil Claim'),
          ),
      ],
      CutoutPosition.topLeft,
    );
  }

  Widget _buildWeedingStrategiesSection() {
    return _buildSection(
      'Effective Weeding Strategies',
      Icons.grass,
      Colors.orange,
      [
        if (_plant!.weedingStrategies.isEmpty && !_isEditing)
          const Text('No weeding strategies available', style: TextStyle(color: Colors.grey)),
        ..._isEditing
            ? _strategyControllers.asMap().entries.map((entry) {
                final index = entry.key;
                final controller = entry.value;
                return _buildEditableStrategyItem(controller, index);
              }).toList()
            : _plant!.weedingStrategies.map((strategy) => _buildStrategyItem(strategy)).toList(),
        if (_isEditing)
          ElevatedButton.icon(
            onPressed: _addStrategy,
            icon: const Icon(Icons.add),
            label: const Text('Add Strategy'),
          ),
      ],
      CutoutPosition.topRight,
    );
  }

  
  Widget _buildInfoItem(String label, String? value, String controllerKey) {
    // Scientific name should always be displayed as read-only
    if (controllerKey == 'scientific_name') {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 180,
              child: Text(
                '$label:',
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
            SizedBox(
              width: 200,
              child: Text(
                value != null && value.isNotEmpty 
                    ? value 
                    : widget.scientificName.isNotEmpty 
                        ? widget.scientificName 
                        : 'Not specified'
              ),
            ),
          ],
        ),
      );
    }
    
    if (_isEditing) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 8.0),
        child: TextField(
          controller: _propertyControllers[controllerKey],
          decoration: InputDecoration(
            labelText: label,
            border: const OutlineInputBorder(),
          ),
        ),
      );
    } else {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 4.0),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            SizedBox(
              width: 180,
              child: Text(
                '$label:',
                style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ),
            SizedBox(
              width: 200,
              child: Text(value ?? 'Not specified'),
            ),
          ],
        ),
      );
    }
  }

  Widget _buildTraitItem(Trait trait) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        textDirection: TextDirection.rtl,
        children: [
          SizedBox(
            width: 200,
            child: Text(
              trait.plantTraitValue ?? 'Not specified',
            ),
          ),
          SizedBox(
            width: 200,
            child: Text(
              '${trait.plantTraitName}:',
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
          SizedBox(
            width: 140,
            ),
        ],
      ),
    );
  }

  Widget _buildEditableTraitItem(TraitEditController controller, int index) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        textDirection: TextDirection.rtl,
        children: [
          IconButton(
            icon: const Icon(Icons.remove_circle, color: Colors.red),
            onPressed: () => _removeTrait(index),
          ),
          Expanded(
            child: TextField(
              controller: controller.valueController,
              textAlign: TextAlign.right,
              decoration: const InputDecoration(
                labelText: 'Plant Trait Value',
                border: OutlineInputBorder(),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: controller.nameController,
              textAlign: TextAlign.right,
              decoration: const InputDecoration(
                labelText: 'Plant Trait Name',
                border: OutlineInputBorder(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSoilClaimItem(SoilClaim claim) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4.0),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        textDirection: TextDirection.rtl,
        children: [
          SizedBox(
            width: 200,
            child: Text(
              claim.soilCondition ?? 'Not specified',
            ),
          ),
          SizedBox(
            width: 200,
            child: Text(
              '${claim.soilProperty}:',
              style: const TextStyle(fontWeight: FontWeight.w500),
            ),
          ),
          SizedBox(
            width: 140,
          )
        ],
      ),
    );
  }

  Widget _buildEditableSoilClaimItem(SoilClaimEditController controller, int index) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Row(
        textDirection: TextDirection.rtl,
        children: [
          IconButton(
            icon: const Icon(Icons.remove_circle, color: Colors.red),
            onPressed: () => _removeSoilClaim(index),
          ),
          Expanded(
            child: TextField(
              controller: controller.conditionController,
              textAlign: TextAlign.right,
              decoration: const InputDecoration(
                labelText: 'Condition',
                border: OutlineInputBorder(),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: TextField(
              controller: controller.propertyController,
              textAlign: TextAlign.right,
              decoration: const InputDecoration(
                labelText: 'Soil Property',
                border: OutlineInputBorder(),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStrategyItem(WeedingStrategy strategy) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: (strategy.type ?? 'unknown') == 'mechanical' 
                      ? Colors.blue.shade100
                      : (strategy.type ?? 'unknown') == 'chemical'
                          ? Colors.red.shade100
                          : Colors.green.shade100,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  (strategy.type ?? 'UNKNOWN').toUpperCase(),
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.bold,
                    color: (strategy.type ?? 'unknown') == 'mechanical' 
                        ? Colors.blue.shade700
                        : (strategy.type ?? 'unknown') == 'chemical'
                            ? Colors.red.shade700
                            : Colors.green.shade700,
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                  strategy.strategyName,
                  style: const TextStyle(fontWeight: FontWeight.w500),
              ),
            ],
          ),
          if (strategy.germanName != null && strategy.germanName!.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'German: ${strategy.germanName}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade600,
                    ),
                  ),
                ],
              ),
            ),
          if (strategy.confidence != null)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'Confidence: ${strategy.confidence!.toStringAsFixed(2)}',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey.shade600,
                    ),
                  ),
                  const SizedBox(width: 8),
                  if (strategy.relationshipType != null)
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: strategy.relationshipType == 'predictedEffectiveAgainst'
                            ? Colors.orange.shade100
                            : Colors.green.shade100,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        strategy.relationshipType == 'predictedEffectiveAgainst' ? 'PREDICTED' : 'CONFIRMED',
                        style: TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: strategy.relationshipType == 'predictedEffectiveAgainst'
                              ? Colors.orange.shade700
                              : Colors.green.shade700,
                        ),
                      ),
                    ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildEditableStrategyItem(WeedingStrategyEditController controller, int index) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8.0),
      child: Column(
        children: [
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller.typeController,
                  decoration: const InputDecoration(
                    labelText: 'Strategy Type',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                flex: 2,
                child: TextField(
                  controller: controller.nameController,
                  decoration: const InputDecoration(
                    labelText: 'Strategy Name',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              IconButton(
                icon: const Icon(Icons.remove_circle, color: Colors.red),
                onPressed: () => _removeStrategy(index),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              Expanded(
                child: TextField(
                  controller: controller.germanNameController,
                  decoration: const InputDecoration(
                    labelText: 'German Name (optional)',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextField(
                  controller: controller.confidenceController,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(
                    labelText: 'Confidence (0-1)',
                    border: OutlineInputBorder(),
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          TextField(
            controller: controller.relationshipTypeController,
            decoration: const InputDecoration(
              labelText: 'Relationship Type (optional)',
              border: OutlineInputBorder(),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildPlantImage() {
    String imageFileName = widget.scientificName.toLowerCase().replaceAll(' ', '_').replaceAll('-', '_');
    String imageUrl = 'http://localhost:8000/static/images/plants/$imageFileName.jpg';
    
    return Image.network(
      imageUrl,
      fit: BoxFit.cover,
      loadingBuilder: (context, child, loadingProgress) {
        if (loadingProgress == null) return child;
        return Container(
          color: Colors.green.shade50,
          child: Center(
            child: CircularProgressIndicator(
              value: loadingProgress.expectedTotalBytes != null
                  ? loadingProgress.cumulativeBytesLoaded / loadingProgress.expectedTotalBytes!
                  : null,
              valueColor: AlwaysStoppedAnimation<Color>(Colors.green.shade400),
            ),
          ),
        );
      },
      errorBuilder: (context, error, stackTrace) {
        return Container(
          color: Colors.green.shade50,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.local_florist,
                size: 60,
                color: Colors.green.shade400,
              ),
              const SizedBox(height: 8),
              Text(
                'No image\navailable',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 12,
                  color: Colors.green.shade600,
                  fontWeight: FontWeight.w500,
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// Helper classes for edit controllers
class TraitEditController {
  final TextEditingController nameController;
  final TextEditingController valueController;

  TraitEditController({
    required this.nameController,
    required this.valueController,
  });

  void dispose() {
    nameController.dispose();
    valueController.dispose();
  }
}

class SoilClaimEditController {
  final TextEditingController propertyController;
  final TextEditingController conditionController;

  SoilClaimEditController({
    required this.propertyController,
    required this.conditionController,
  });

  void dispose() {
    propertyController.dispose();
    conditionController.dispose();
  }
}

class WeedingStrategyEditController {
  final TextEditingController typeController;
  final TextEditingController nameController;
  final TextEditingController germanNameController;
  final TextEditingController confidenceController;
  final TextEditingController relationshipTypeController;

  WeedingStrategyEditController({
    required this.typeController,
    required this.nameController,
    required this.germanNameController,
    required this.confidenceController,
    required this.relationshipTypeController,
  });

  void dispose() {
    typeController.dispose();
    nameController.dispose();
    germanNameController.dispose();
    confidenceController.dispose();
    relationshipTypeController.dispose();
  }
}


enum CutoutPosition {
  topLeft,
  topRight,
  bottomLeft,
  bottomRight,
}

class CardCutoutClipper extends CustomClipper<Path> {
  final CutoutPosition cutoutPosition;
  static const double cutoutRadius = 255.0; // Half of the circle diameter

  CardCutoutClipper(this.cutoutPosition);

  @override
  Path getClip(Size size) {
    final path = Path();
    
    switch (cutoutPosition) {
      case CutoutPosition.topLeft:
        path.moveTo(cutoutRadius, 0);
        path.lineTo(size.width, 0);
        path.lineTo(size.width, size.height);
        path.lineTo(0, size.height);
        path.lineTo(0, cutoutRadius);
        path.arcToPoint(
          Offset(cutoutRadius, 0),
          radius: const Radius.circular(cutoutRadius),
          clockwise: false,
        );
        break;
        
      case CutoutPosition.topRight:
        path.moveTo(0, 0);
        path.lineTo(size.width - cutoutRadius, 0);
        path.arcToPoint(
          Offset(size.width, cutoutRadius),
          radius: const Radius.circular(cutoutRadius),
          clockwise: false,
        );
        path.lineTo(size.width, size.height);
        path.lineTo(0, size.height);
        path.close();
        break;
        
      case CutoutPosition.bottomLeft:
        path.moveTo(0, 0);
        path.lineTo(size.width, 0);
        path.lineTo(size.width, size.height);
        path.lineTo(cutoutRadius, size.height);
        path.arcToPoint(
          Offset(0, size.height - cutoutRadius),
          radius: const Radius.circular(cutoutRadius),
          clockwise: false,
        );
        path.close();
        break;
        
      case CutoutPosition.bottomRight:
        path.moveTo(0, 0);
        path.lineTo(size.width, 0);
        path.lineTo(size.width, size.height - cutoutRadius);
        path.arcToPoint(
          Offset(size.width - cutoutRadius, size.height),
          radius: const Radius.circular(cutoutRadius),
          clockwise: false,
        );
        path.lineTo(0, size.height);
        path.close();
        break;
    }
    
    return path;
  }

  @override
  bool shouldReclip(CustomClipper<Path> oldClipper) => false;
}