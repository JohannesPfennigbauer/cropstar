import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/plant.dart';

class ApiService {
  static const String baseUrl = 'http://localhost:8000';

  // Search for plants by name
  static Future<List<String>> searchPlants(String searchTerm) async {
    try {
      if (searchTerm.trim().length < 2) {
        return [];
      }

      final response = await http.get(
        Uri.parse('$baseUrl/plants/search?search_term=${Uri.encodeComponent(searchTerm)}'),
        headers: {'Content-Type': 'application/json'},
      );

      if (response.statusCode == 200) {
        final List<dynamic> scientificNames = json.decode(response.body);
        return scientificNames.cast<String>();
      } else if (response.statusCode == 400) {
        // Search term too short
        return [];
      } else {
        throw Exception('Failed to search plants: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Error searching plants: $e');
    }
  }

  // Get detailed information for a specific plant
  static Future<Plant> getPlant(String scientificName) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/plant/${Uri.encodeComponent(scientificName)}'),
        headers: {'Content-Type': 'application/json'},
      );

      if (response.statusCode == 200) {
        final Map<String, dynamic> plantData = json.decode(response.body);
        return Plant.fromJson(plantData);
      } else if (response.statusCode == 404) {
        throw Exception('Plant not found');
      } else {
        throw Exception('Failed to get plant: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Error getting plant: $e');
    }
  }

  // Update plant information
  static Future<bool> updatePlant(String scientificName, Plant plant) async {
    try {
      // Prepare the update payload
      final updatePayload = {
        'properties': plant.properties.toJson(),
        'traits': plant.traits.map((trait) => trait.toJson()).toList(),
        'soil_claims': plant.soilClaims.map((claim) => claim.toJson()).toList(),
        'weeding_strategies': plant.weedingStrategies.map((strategy) => strategy.toJson()).toList(),
      };

      final response = await http.put(
        Uri.parse('$baseUrl/plant/${Uri.encodeComponent(scientificName)}'),
        headers: {'Content-Type': 'application/json'},
        body: json.encode(updatePayload),
      );

      if (response.statusCode == 200) {
        return true;
      } else if (response.statusCode == 404) {
        throw Exception('Plant not found');
      } else if (response.statusCode == 400) {
        throw Exception('Invalid plant data');
      } else {
        throw Exception('Failed to update plant: ${response.statusCode} - ${response.body}');
      }
    } catch (e) {
      throw Exception('Error updating plant: $e');
    }
  }

  // Health check endpoint
  static Future<bool> checkServerHealth() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/'),
        headers: {'Content-Type': 'application/json'},
      );

      return response.statusCode == 200;
    } catch (e) {
      return false;
    }
  }
}