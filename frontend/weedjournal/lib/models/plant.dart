// import 'dart:ffi';

class Trait {
  final String plantTraitName;
  final String? plantTraitValue;

  Trait({
    required this.plantTraitName,
    this.plantTraitValue,
  });

  factory Trait.fromJson(Map<String, dynamic> json) {
    return Trait(
      plantTraitName: json['plant_trait_name'] ?? '',
      plantTraitValue: json['plant_trait_value'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'plant_trait_name': plantTraitName,
      'plant_trait_value': plantTraitValue,
    };
  }

  Trait copyWith({
    String? plantTraitName,
    String? plantTraitValue,
  }) {
    return Trait(
      plantTraitName: plantTraitName ?? this.plantTraitName,
      plantTraitValue: plantTraitValue ?? this.plantTraitValue,
    );
  }
}

class SoilClaim {
  final String soilProperty;
  final String? soilCondition;

  SoilClaim({
    required this.soilProperty,
    this.soilCondition,
  });

  factory SoilClaim.fromJson(Map<String, dynamic> json) {
    return SoilClaim(
      soilProperty: json['soil_property'] ?? '',
      soilCondition: json['soil_condition'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'soil_property': soilProperty,
      'soil_condition': soilCondition,
    };
  }

  SoilClaim copyWith({
    String? soilProperty,
    String? soilCondition,
  }) {
    return SoilClaim(
      soilProperty: soilProperty ?? this.soilProperty,
      soilCondition: soilCondition ?? this.soilCondition,
    );
  }
}

class WeedingStrategy {
  final String strategyName;
  final String? type;
  final String? germanName;
  final double? confidence;
  final String? relationshipType;

  WeedingStrategy({
    required this.strategyName,
    this.type,
    this.germanName,
    this.confidence,
    this.relationshipType,
  });

  factory WeedingStrategy.fromJson(Map<String, dynamic> json) {
    return WeedingStrategy(
      strategyName: json['strategy_name'] ?? '',
      type: json['type'],
      germanName: json['german_name'],
      confidence: json['confidence']?.toDouble(),
      relationshipType: json['relationshipType'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'strategy_name': strategyName,
      'type': type,
      'german_name': germanName,
      'confidence': confidence,
      'relationshipType': relationshipType,
    };
  }

  WeedingStrategy copyWith({
    String? strategyName,
    String? type,
    String? germanName,
    double? confidence,
    String? relationshipType,
  }) {
    return WeedingStrategy(
      strategyName: strategyName ?? this.strategyName,
      type: type ?? this.type,
      germanName: germanName ?? this.germanName,
      confidence: confidence ?? this.confidence,
      relationshipType: relationshipType ?? this.relationshipType,
    );
  }
}

class PlantProperties {
  final String? commonName;
  final String? germanName;
  final String? family;
  final String? genus;

  PlantProperties({
    this.commonName,
    this.germanName,
    this.family,
    this.genus,
  });

  factory PlantProperties.fromJson(Map<String, dynamic> json) {
    return PlantProperties(
      commonName: json['common_name'],
      germanName: json['german_name'],
      family: json['family'],
      genus: json['genus'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'common_name': commonName,
      'german_name': germanName,
      'family': family,
      'genus': genus,
    };
  }

  PlantProperties copyWith({
    String? commonName,
    String? germanName,
    String? family,
    String? genus,
  }) {
    return PlantProperties(
      commonName: commonName ?? this.commonName,
      germanName: germanName ?? this.germanName,
      family: family ?? this.family,
      genus: genus ?? this.genus,
    );
  }
}

class Plant {
  final String scientificName;
  final PlantProperties properties;
  final List<Trait> traits;
  final List<SoilClaim> soilClaims;
  final List<WeedingStrategy> weedingStrategies;

  Plant({
    required this.scientificName,
    required this.properties,
    required this.traits,
    required this.soilClaims,
    required this.weedingStrategies,
  });

  factory Plant.fromJson(Map<String, dynamic> json) {
    return Plant(
      scientificName: json['scientific_name'] ?? '',
      properties: PlantProperties.fromJson(json['properties'] ?? {}),
      traits: (json['traits'] as List<dynamic>? ?? [])
          .map((trait) => Trait.fromJson(trait))
          .toList(),
      soilClaims: (json['soil_claims'] as List<dynamic>? ?? [])
          .map((claim) => SoilClaim.fromJson(claim))
          .toList(),
      weedingStrategies: (json['weeding_strategies'] as List<dynamic>? ?? [])
          .map((strategy) => WeedingStrategy.fromJson(strategy))
          .toList(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'scientific_name': scientificName,
      'properties': properties.toJson(),
      'traits': traits.map((trait) => trait.toJson()).toList(),
      'soil_claims': soilClaims.map((claim) => claim.toJson()).toList(),
      'weeding_strategies':
          weedingStrategies.map((strategy) => strategy.toJson()).toList(),
    };
  }

  Plant copyWith({
    String? scientificName,
    PlantProperties? properties,
    List<Trait>? traits,
    List<SoilClaim>? soilClaims,
    List<WeedingStrategy>? weedingStrategies,
  }) {
    return Plant(
      scientificName: scientificName ?? this.scientificName,
      properties: properties ?? this.properties,
      traits: traits ?? this.traits,
      soilClaims: soilClaims ?? this.soilClaims,
      weedingStrategies: weedingStrategies ?? this.weedingStrategies,
    );
  }
}