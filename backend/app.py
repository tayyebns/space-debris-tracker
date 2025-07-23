from flask import Flask, jsonify
from flask_cors import CORS
import requests
import os
from dotenv import load_dotenv
import datetime
import json

load_dotenv()

app = Flask(__name__)
CORS(app)

class SpaceTrackAPI:
    def __init__(self):
        self.username = os.getenv('SPACE_TRACK_USERNAME')
        self.password = os.getenv('SPACE_TRACK_PASSWORD')
        self.base_url = "https://www.space-track.org"
        self.session = requests.Session()
        self.authenticated = False
    
    def authenticate(self):
        """Login to Space-Track.org"""
        login_url = f"{self.base_url}/ajaxauth/login"
        login_data = {
            'identity': self.username,
            'password': self.password
        }
        
        try:
            response = self.session.post(login_url, data=login_data)
            if response.status_code == 200:
                self.authenticated = True
                print("✅ Successfully authenticated with Space-Track.org")
                return True
            else:
                print(f"❌ Authentication failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Authentication error: {e}")
        
        return False
    
    def get_debris_data(self, limit=100):
        """Fetch real space debris data"""
        if not self.authenticated and not self.authenticate():
            return None
        
        # Query for space debris (objects with high eccentricity or in decaying orbits)
        query_url = f"{self.base_url}/basicspacedata/query/class/gp/EPOCH/>now-30/MEAN_MOTION/>11/orderby/NORAD_CAT_ID/limit/{limit}/format/json"
        
        try:
            response = self.session.get(query_url)
            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Data fetch failed: {response.status_code}")
        except Exception as e:
            print(f"❌ Data fetch error: {e}")
        
        return None

# Initialize API client
space_track = SpaceTrackAPI()

@app.route('/health')
def health_check():
    current_time = datetime.datetime.now().strftime("%H:%M:%S")
    return jsonify({
        "status": "healthy", 
        "message": f"Backend active at {current_time}",
        "timestamp": current_time
    })

@app.route('/api/debris')
def get_debris():
    """Get real space debris data from Space-Track.org"""
    print("🚀 Fetching real space debris data...")
    
    raw_data = space_track.get_debris_data(10000)  # Get 50 objects
    
    if not raw_data:
        return jsonify({"error": "Failed to fetch real space data"}), 500
    
    # Process the real data into our format
    processed_objects = []
    for obj in raw_data:
        try:
            processed_obj = {
            "id": obj.get('NORAD_CAT_ID'),
            "name": obj.get('OBJECT_NAME', 'Unknown Object'),
            "country": obj.get('COUNTRY_CODE', 'Unknown'),
            "altitude": calculate_altitude(obj),
            "velocity": round(float(obj.get('MEAN_MOTION', 0)) * 0.1, 2),  # Simplified
            "risk_level": calculate_risk_level(obj),
            "orbit_type": classify_orbit(obj),
            "size": obj.get('RCS_SIZE', 'Unknown'),
            "launch_date": obj.get('LAUNCH_DATE', 'Unknown'),
            "epoch": obj.get('EPOCH')
       }
            processed_objects.append(processed_obj)
        except Exception as e:
            continue  # Skip malformed objects
    
    print(f"✅ Successfully processed {len(processed_objects)} real space objects")
    
    return jsonify({
        "total_count": len(processed_objects),
        "objects": processed_objects,
        "last_updated": datetime.datetime.now().strftime("%H:%M:%S"),
        "data_source": "Space-Track.org (Official US Space Force)"
    })

def calculate_risk_level(obj):
    """Calculate risk level based on orbital parameters"""
    try:
        mean_motion = float(obj.get('MEAN_MOTION', 0))
        eccentricity = float(obj.get('ECCENTRICITY', 0))
        
        if mean_motion > 15 and eccentricity > 0.1:
            return 'HIGH'
        elif mean_motion > 12:
            return 'MEDIUM'
        else:
            return 'LOW'
    except:
        return 'LOW'

def classify_orbit(obj):
    """Classify orbit type based on mean motion"""
    try:
        mean_motion = float(obj.get('MEAN_MOTION', 0))
        
        if mean_motion > 11:
            return 'LEO'  # Low Earth Orbit
        elif mean_motion > 1:
            return 'MEO'  # Medium Earth Orbit
        else:
            return 'GEO'  # Geostationary/High orbit
    except:
        return 'LEO'
def calculate_altitude(obj):
    """Calculate altitude from orbital parameters"""
    try:
        # Try different altitude fields from Space-Track
        apogee = float(obj.get('APOGEE', 0))
        perigee = float(obj.get('PERIGEE', 0))
        mean_motion = float(obj.get('MEAN_MOTION', 0))
        
        if apogee > 0 and perigee > 0:
            # Average of apogee and perigee
            return round((apogee + perigee) / 2)
        elif mean_motion > 0:
            # Calculate from mean motion using Kepler's laws
            # Semi-major axis = (μ/n²)^(1/3) where μ = 398600.4418 km³/s²
            mu = 398600.4418
            n = mean_motion * 2 * 3.14159 / 86400  # Convert to rad/s
            semi_major_axis = (mu / (n * n)) ** (1/3)
            altitude = semi_major_axis - 6371  # Subtract Earth's radius
            return round(max(altitude, 0))  # Don't allow negative altitudes
        else:
            return 0
    except (ValueError, TypeError, ZeroDivisionError):
        return 0
if __name__ == '__main__':
    app.run(debug=True, port=5000)