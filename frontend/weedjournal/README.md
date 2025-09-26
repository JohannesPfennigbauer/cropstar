# Weed Management Flutter Web App

A Flutter web application that serves as a client for the FastAPI weed management backend. This app allows users to search for plants, view detailed plant information, and edit plant data.

### Features

🏠 Home Screen
- **Live Search**: Real-time search with debounced input
- **Navigation**: Click on any plant to view detailed information

🌱 Plant Detail Screen
- **Four Information Categories**: General Information, Plant Traits, Soil Claims, Weeding Strategies

✏️ Edit Mode
- **Toggle Edit**: Switch between view and edit modes with the edit button
- **Dynamic Forms**: Add/remove traits, soil claims, and weeding strategies
- **Save Changes**: Update plant information via PUT API endpoint

### Prerequisites
- Flutter SDK (latest stable version)
- FastAPI backend running on `http://localhost:8000`

### Installation

1. **Navigate to the frontend folder**:
   ```bash
   cd frontend/weedjournal
   ```

2. **Install dependencies**:
   ```bash
   flutter pub get
   ```

3. **Run the web application**:
   ```bash
   flutter run -d chrome
   ```