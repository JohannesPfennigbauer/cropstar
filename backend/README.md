# Weed Management Knowledge Graph: Backend

A FastAPI backend for interacting with a Neo4j knowledge graph containing plant/weed management information.

### Database Setup
Currently no example data is provided. I am working on this.

### API Features
- **GET /plant/{plant_name}**: Retrieve comprehensive plant information including properties, traits, soil requirements, and weeding strategies
- **PUT /plant/{plant_name}**: Update plant information with transaction support
- **GET /plants/search**: Search for plants by name for autocomplete functionality

### Prerequisites
- Python 3.8+
- Neo4j Database (local or remote)

### Installation
1. Clone the repository and navigate to the backend folder
   
2. Create a virtual environment:
   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Environment configuration:
   Create a `.env` file with your Neo4j connection details.

5. KG Creation:
   Run all cells in kg_creation.ipynb (adjust according to your data structure)

6. KG Evolution:
   Run all cells in kg_evolution.ipynb

7. Setup CORS
   Add the port of the Flutter frontend as an allowed_origin in Line 46 of main.py

8. Start the application:
   ```bash
   python main.py
   ```

The API will be available at `http://localhost:8000`