import json
import time
import requests
import random
import math
import pyautogui
import pygetwindow as gw
import re
import os
import signal
import logging
from functools import wraps
from geopy.geocoders import Nominatim
from datetime import datetime, timezone, timedelta
import pytz
import sys
from warning_data_to_html import create_html

# ========================================================================================
# --- LOGGING SETUP ---
# ========================================================================================
def setup_logging():
    """Configure logging to both console and file"""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    log_file = os.path.join(log_dir, f"weatherwise_{datetime.now().strftime('%Y%m%d')}.log")
    
    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Clear existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Console handler with UTF-8 encoding
    console = logging.StreamHandler(sys.stdout)  # Use stdout instead of stderr
    console.setLevel(logging.INFO)
    console_format = logging.Formatter('%(levelname)s: %(message)s')
    console.setFormatter(console_format)
    
    # File handler with UTF-8 encoding
    file_handler = logging.FileHandler(log_file, encoding='utf-8')  # Specify UTF-8 encoding
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_format)
    
    # Add handlers
    logger.addHandler(console)
    logger.addHandler(file_handler)
    
    return logger

logger = setup_logging()

# ========================================================================================
# --- CONFIGURATION MANAGEMENT ---
# ========================================================================================
DEFAULT_CONFIG = {
    "WEATHER_WISE_WINDOW_TITLE": "WeatherWise",
    "HOTKEY_SHOW_GRAPHIC": ['ctrl', 'alt', 'shift', 'f11'],
    "HOTKEY_HIDE_GRAPHIC": ['ctrl', 'alt', 'shift', 'f12'],
    "HOTKEY_COMPOSITE_RADAR": ['shift', '2'],
    "HOTKEY_NORMAL_RADAR": ['shift', '1'],
    "HOTKEY_PLAYBACK_TOGGLE": 'space',
    "POLLING_INTERVAL_SECONDS": 10,
    "IDLE_CYCLE_SECONDS": 100,  # Total time for a city in pure idle mode
    "WARNING_INTERLEAVE_CYCLE_SECONDS": 30,  # Time per warning in warnings mode
    "POST_SEARCH_DELAY_SECONDS": 3,
    "POST_NAVIGATION_ZOOM_OUTS": 2,
    "IDLE_CITY_TOUR_ZOOM_OUTS": 4,
    "IDLE_RADAR_TOUR_ZOOM_OUTS": 2,
    "LOCAL_TIMEZONE": "America/Chicago",
    "NWS_USER_AGENT": "WeatherWiseStreamBot/1.0 (YourName, yourcontact@example.com)",
    "GEOLOCATION_USER_AGENT": "WeatherWiseStreamBot/1.0 (YourStreamName, yourcontact@example.com)",
    "WEATHER_API_KEY": "09846f8f8afa4a2bb19194147250907",  # Replace with your actual WeatherAPI key
    "WEATHER_API_ENABLED": True,
    "CITY_DISPLAY_DURATION": 100,  # Total time for a city in any city mode (idle or break)
    "WARNINGS_PER_CYCLE": 10,     # Number of warnings to show before starting city break
    "CITIES_PER_CYCLE": 5,        # Number of cities to show before switching back to warnings
    "DISPLAY_SEQUENCE": ["current", "forecast", "three_day", "astronomy", "air_quality"],  # Order of displays
    "DISPLAY_DURATION": 15,        # Seconds to show each display type (current, forecast, etc.)
    "CACHE_DURATION": 900         # Cache weather data for 15 minutes (900 seconds)
}

def load_config():
    """Load configuration from file or create default"""
    config_path = os.path.join(os.path.dirname(__file__) or '.', 'config.json')
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                # Update with any new default keys that might not be in saved config
                for key, value in DEFAULT_CONFIG.items():
                    if key not in config:
                        config[key] = value
                logger.info(f"Configuration loaded from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Error loading config: {e}. Using defaults.")
            return DEFAULT_CONFIG
    else:
        # Create default config file
        with open(config_path, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        logger.info(f"Default configuration created at {config_path}")
        return DEFAULT_CONFIG

CONFIG = load_config()

# ========================================================================================
# --- RATE LIMITING ---
# ========================================================================================
def rate_limit(min_interval=1.0):
    """Decorator to enforce minimum time between API calls"""
    last_called = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = func.__name__
            current_time = time.time()
            if key in last_called:
                elapsed = current_time - last_called[key]
                if elapsed < min_interval:
                    sleep_time = min_interval - elapsed
                    logger.debug(f"Rate limiting {key}: sleeping {sleep_time:.2f}s")
                    time.sleep(sleep_time)
            result = func(*args, **kwargs)
            last_called[key] = time.time()
            return result
        return wrapper
    return decorator

# ========================================================================================
# --- STATE MANAGEMENT ---
# ========================================================================================
def save_state():
    """Save current state to allow resuming after restart"""
    try:
        state_data = {
            "active_warnings": [w.get('id', '') for w in active_warnings_cache],
            "warning_display_index": warning_display_index,
            "cities_shown_in_break": cities_shown_in_break,
            "last_action_timestamp": last_action_timestamp,
            "current_mode": current_mode,
            "warnings_shown_in_cycle": warnings_shown_in_cycle,
            "current_display": current_display,
            "display_start_time": display_start_time,
            "current_city": current_city,  # Save current city to resume display cycle
            "city_start_time": city_start_time  # Save city overall timer
        }
        
        # Use a temporary file for atomic write
        temp_file_path = 'weatherwise_state.json.tmp'
        final_file_path = 'weatherwise_state.json'
        
        with open(temp_file_path, 'w', encoding='utf-8') as f:
            json.dump(state_data, f, indent=4)
        
        # Replace the old file with the new one (atomic operation)
        os.replace(temp_file_path, final_file_path)
        
        logger.debug("State saved successfully")
    except Exception as e:
        logger.error(f"Failed to save state: {e}")

def load_state():
    """Load previous state if available"""
    state_file = 'weatherwise_state.json'
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                
                # Reset active warnings to empty list to force refresh
                if 'active_warnings' in state:
                    state['active_warnings'] = []
                
                logger.info("Previous state loaded")
                return state
        except Exception as e:
            logger.error(f"Failed to load state: {e}")
            # If the state file is corrupted, remove it
            if os.path.exists(state_file):
                os.remove(state_file)
    
    logger.info("No previous state found, starting fresh")
    return None

# ========================================================================================
# --- DATA CONSTANTS ---
# ========================================================================================
# --- City Tour List (abbreviated) ---
IDLE_CITY_TOUR_LIST = [
    # Alabama
    "Birmingham, AL", "Montgomery, AL", "Huntsville, AL", "Mobile, AL", "Tuscaloosa, AL",
    "Hoover, AL", "Dothan, AL", "Auburn, AL", "Decatur, AL", "Madison, AL",
    "Oxford, AL", "Gadsden, AL", "Vestavia Hills, AL", "Prattville, AL", "Phenix City, AL",
    
    # Arizona
    "Phoenix, AZ", "Tucson, AZ", "Mesa, AZ", "Chandler, AZ", "Scottsdale, AZ",
    "Glendale, AZ", "Gilbert, AZ", "Tempe, AZ", "Peoria, AZ", "Surprise, AZ",
    "Yuma, AZ", "Avondale, AZ", "Goodyear, AZ", "Flagstaff, AZ", "Buckeye, AZ",
    
    # Arkansas
    "Little Rock, AR", "Fort Smith, AR", "Fayetteville, AR", "Springdale, AR", "Jonesboro, AR",
    "North Little Rock, AR", "Conway, AR", "Rogers, AR", "Pine Bluff, AR", "Bentonville, AR",
    "Hot Springs, AR", "Benton, AR", "Texarkana, AR", "Sherwood, AR", "Jacksonville, AR",
    
    # California
    "Los Angeles, CA", "San Diego, CA", "San Jose, CA", "San Francisco, CA", "Fresno, CA",
    "Sacramento, CA", "Long Beach, CA", "Oakland, CA", "Bakersfield, CA", "Anaheim, CA",
    "Santa Ana, CA", "Riverside, CA", "Stockton, CA", "Irvine, CA", "Chula Vista, CA",
    
    # Colorado
    "Denver, CO", "Colorado Springs, CO", "Aurora, CO", "Fort Collins, CO", "Lakewood, CO",
    "Thornton, CO", "Arvada, CO", "Westminster, CO", "Pueblo, CO", "Centennial, CO",
    "Boulder, CO", "Greeley, CO", "Longmont, CO", "Loveland, CO", "Grand Junction, CO",
    
    # Connecticut
    "Bridgeport, CT", "New Haven, CT", "Stamford, CT", "Hartford, CT", "Waterbury, CT",
    "Norwalk, CT", "Danbury, CT", "New Britain, CT", "West Hartford, CT", "Greenwich, CT",
    "Hamden, CT", "Meriden, CT", "Bristol, CT", "Fairfield, CT", "Manchester, CT",
    
    # Delaware
    "Wilmington, DE", "Dover, DE", "Newark, DE", "Middletown, DE", "Smyrna, DE",
    "Milford, DE", "Seaford, DE", "Georgetown, DE", "Elsmere, DE", "New Castle, DE",
    "Millsboro, DE", "Laurel, DE", "Harrington, DE", "Camden, DE", "Clayton, DE",
    
    # Florida
    "Jacksonville, FL", "Miami, FL", "Tampa, FL", "Orlando, FL", "St. Petersburg, FL",
    "Davenport, FL", "Tallahassee, FL", "Fort Lauderdale, FL", "Port St. Lucie, FL", "Cape Coral, FL",
    "Pembroke Pines, FL", "Hollywood, FL", "Miramar, FL", "Gainesville, FL", "Coral Springs, FL",
    
    # Georgia
    "Atlanta, GA", "Augusta, GA", "Columbus, GA", "Savannah, GA", "Athens, GA",
    "Sandy Springs, GA", "Macon, GA", "Roswell, GA", "Albany, GA", "Johns Creek, GA",
    "Warner Robins, GA", "Alpharetta, GA", "Marietta, GA", "Smyrna, GA", "Valdosta, GA",
    
    # Idaho
    "Boise, ID", "Meridian, ID", "Nampa, ID", "Idaho Falls, ID", "Pocatello, ID",
    "Caldwell, ID", "Coeur d'Alene, ID", "Twin Falls, ID", "Post Falls, ID", "Lewiston, ID",
    "Rexburg, ID", "Eagle, ID", "Moscow, ID", "Mountain Home, ID", "Kuna, ID",
    
    # Illinois
    "Chicago, IL", "Aurora, IL", "Naperville, IL", "Joliet, IL", "Rockford, IL",
    "Elgin, IL", "Springfield, IL", "Peoria, IL", "Champaign, IL", "Waukegan, IL",
    "Bloomington, IL", "Decatur, IL", "Evanston, IL", "Schaumburg, IL", "Bolingbrook, IL",
    
    # Indiana
    "Indianapolis, IN", "Fort Wayne, IN", "Evansville, IN", "South Bend, IN", "Carmel, IN",
    "Fishers, IN", "Bloomington, IN", "Hammond, IN", "Gary, IN", "Lafayette, IN",
    "Muncie, IN", "Terre Haute, IN", "Kokomo, IN", "Anderson, IN", "Noblesville, IN",
    
    # Iowa
    "Des Moines, IA", "Cedar Rapids, IA", "Davenport, IA", "Sioux City, IA", "Iowa City, IA",
    "Waterloo, IA", "Council Bluffs, IA", "Ames, IA", "West Des Moines, IA", "Ankeny, IA",
    "Urbandale, IA", "Cedar Falls, IA", "Marion, IA", "Bettendorf, IA", "Mason City, IA",
    
    # Kansas
    "Wichita, KS", "Overland Park, KS", "Kansas City, KS", "Olathe, KS", "Topeka, KS",
    "Lawrence, KS", "Shawnee, KS", "Manhattan, KS", "Lenexa, KS", "Salina, KS",
    "Hutchinson, KS", "Leavenworth, KS", "Leawood, KS", "Dodge City, KS", "Garden City, KS",
    
    # Kentucky
    "Louisville, KY", "Lexington, KY", "Bowling Green, KY", "Owensboro, KY", "Covington, KY",
    "Richmond, KY", "Georgetown, KY", "Florence, KY", "Hopkinsville, KY", "Nicholasville, KY",
    "Frankfort, KY", "Henderson, KY", "Jeffersontown, KY", "Paducah, KY", "Elizabethtown, KY",
    
    # Louisiana
    "New Orleans, LA", "Baton Rouge, LA", "Shreveport, LA", "Lafayette, LA", "Lake Charles, LA",
    "Kenner, LA", "Bossier City, LA", "Monroe, LA", "Alexandria, LA", "Houma, LA",
    "New Iberia, LA", "Slidell, LA", "Hammond, LA", "Ruston, LA", "Natchitoches, LA",
    
    # Maine
    "Portland, ME", "Lewiston, ME", "Bangor, ME", "South Portland, ME", "Auburn, ME",
    "Biddeford, ME", "Sanford, ME", "Saco, ME", "Augusta, ME", "Westbrook, ME",
    "Waterville, ME", "Presque Isle, ME", "Brewer, ME", "Bath, ME", "Caribou, ME",
    
    # Maryland
    "Baltimore, MD", "Frederick, MD", "Rockville, MD", "Gaithersburg, MD", "Bowie, MD",
    "Hagerstown, MD", "Annapolis, MD", "College Park, MD", "Salisbury, MD", "Laurel, MD",
    "Greenbelt, MD", "Cumberland, MD", "Westminster, MD", "Hyattsville, MD", "Takoma Park, MD",
    
    # Massachusetts
    "Boston, MA", "Worcester, MA", "Springfield, MA", "Cambridge, MA", "Lowell, MA",
    "Brockton, MA", "Quincy, MA", "Lynn, MA", "New Bedford, MA", "Fall River, MA",
    "Newton, MA", "Lawrence, MA", "Somerville, MA", "Framingham, MA", "Haverhill, MA",
    
    # Michigan
    "Detroit, MI", "Grand Rapids, MI", "Warren, MI", "Sterling Heights, MI", "Ann Arbor, MI",
    "Lansing, MI", "Flint, MI", "Dearborn, MI", "Livonia, MI", "Troy, MI",
    "Westland, MI", "Farmington Hills, MI", "Kalamazoo, MI", "Wyoming, MI", "Southfield, MI",
    
    # Minnesota
    "Minneapolis, MN", "St. Paul, MN", "Rochester, MN", "Duluth, MN", "Bloomington, MN",
    "Brooklyn Park, MN", "Plymouth, MN", "St. Cloud, MN", "Eagan, MN", "Woodbury, MN",
    "Maple Grove, MN", "Eden Prairie, MN", "Coon Rapids, MN", "Burnsville, MN", "Blaine, MN",
    
    # Mississippi
    "Jackson, MS", "Gulfport, MS", "Southaven, MS", "Hattiesburg, MS", "Biloxi, MS",
    "Meridian, MS", "Tupelo, MS", "Greenville, MS", "Olive Branch, MS", "Horn Lake, MS",
    "Clinton, MS", "Pearl, MS", "Madison, MS", "Starkville, MS", "Ridgeland, MS",
    
    # Missouri
    "Kansas City, MO", "St. Louis, MO", "Springfield, MO", "Columbia, MO", "Independence, MO",
    "Lee's Summit, MO", "O'Fallon, MO", "St. Joseph, MO", "St. Charles, MO", "Blue Springs, MO",
    "Joplin, MO", "Florissant, MO", "Jefferson City, MO", "Chesterfield, MO", "Cape Girardeau, MO",
    
    # Montana
    "Billings, MT", "Missoula, MT", "Great Falls, MT", "Bozeman, MT", "Butte, MT",
    "Helena, MT", "Kalispell, MT", "Havre, MT", "Anaconda, MT", "Miles City, MT",
    "Belgrade, MT", "Livingston, MT", "Laurel, MT", "Whitefish, MT", "Lewistown, MT",
    
    # Nebraska
    "Omaha, NE", "Lincoln, NE", "Bellevue, NE", "Grand Island, NE", "Kearney, NE",
    "Fremont, NE", "Hastings, NE", "Norfolk, NE", "Columbus, NE", "North Platte, NE",
    "Papillion, NE", "La Vista, NE", "Scottsbluff, NE", "South Sioux City, NE", "Beatrice, NE",
    
    # Nevada
    "Las Vegas, NV", "Henderson, NV", "Reno, NV", "North Las Vegas, NV", "Sparks, NV",
    "Carson City, NV", "Fernley, NV", "Elko, NV", "Mesquite, NV", "Boulder City, NV",
    "Fallon, NV", "Winnemucca, NV", "West Wendover, NV", "Ely, NV", "Yerington, NV",
    
    # New Hampshire
    "Manchester, NH", "Nashua, NH", "Concord, NH", "Dover, NH", "Rochester, NH",
    "Keene, NH", "Portsmouth, NH", "Laconia, NH", "Lebanon, NH", "Claremont, NH",
    "Somersworth, NH", "Berlin, NH", "Franklin, NH", "Derry, NH", "Londonderry, NH",
    
    # New Jersey
    "Newark, NJ", "Jersey City, NJ", "Paterson, NJ", "Elizabeth, NJ", "Trenton, NJ",
    "Clifton, NJ", "Camden, NJ", "Passaic, NJ", "Union City, NJ", "East Orange, NJ",
    "Vineland, NJ", "Bayonne, NJ", "New Brunswick, NJ", "Perth Amboy, NJ", "Hoboken, NJ",
    
    # New Mexico
    "Albuquerque, NM", "Las Cruces, NM", "Rio Rancho, NM", "Santa Fe, NM", "Roswell, NM",
    "Farmington, NM", "Alamogordo, NM", "Clovis, NM", "Hobbs, NM", "Carlsbad, NM",
    "Gallup, NM", "Deming, NM", "Los Lunas, NM", "Chaparral, NM", "Sunland Park, NM",
    
    # New York
    "New York, NY", "Buffalo, NY", "Rochester, NY", "Yonkers, NY", "Syracuse, NY",
    "Albany, NY", "New Rochelle, NY", "Mount Vernon, NY", "Schenectady, NY", "Utica, NY",
    "White Plains, NY", "Hempstead, NY", "Troy, NY", "Niagara Falls, NY", "Binghamton, NY",
    
    # North Carolina
    "Charlotte, NC", "Raleigh, NC", "Greensboro, NC", "Durham, NC", "Winston-Salem, NC",
    "Fayetteville, NC", "Cary, NC", "Wilmington, NC", "High Point, NC", "Concord, NC",
    "Greenville, NC", "Asheville, NC", "Gastonia, NC", "Jacksonville, NC", "Chapel Hill, NC",
    
    # North Dakota
    "Fargo, ND", "Bismarck, ND", "Grand Forks, ND", "Minot, ND", "West Fargo, ND",
    "Williston, ND", "Dickinson, ND", "Mandan, ND", "Jamestown, ND", "Wahpeton, ND",
    "Devils Lake, ND", "Valley City, ND", "Grafton, ND", "Watford City, ND", "Rugby, ND",
    
    # Ohio
    "Columbus, OH", "Cleveland, OH", "Cincinnati, OH", "Toledo, OH", "Akron, OH",
    "Dayton, OH", "Parma, OH", "Canton, OH", "Youngstown, OH", "Lorain, OH",
    "Hamilton, OH", "Springfield, OH", "Kettering, OH", "Elyria, OH", "Lakewood, OH",
    
    # Oklahoma
    "Oklahoma City, OK", "Tulsa, OK", "Norman, OK", "Broken Arrow, OK", "Edmond, OK",
    "Lawton, OK", "Moore, OK", "Midwest City, OK", "Enid, OK", "Stillwater, OK",
    "Muskogee, OK", "Bartlesville, OK", "Owasso, OK", "Ponca City, OK", "Shawnee, OK",
    
    # Oregon
    "Portland, OR", "Salem, OR", "Eugene, OR", "Gresham, OR", "Hillsboro, OR",
    "Beaverton, OR", "Bend, OR", "Medford, OR", "Springfield, OR", "Corvallis, OR",
    "Albany, OR", "Tigard, OR", "Lake Oswego, OR", "Keizer, OR", "Grants Pass, OR",
    
    # Pennsylvania
    "Philadelphia, PA", "Pittsburgh, PA", "Allentown, PA", "Erie, PA", "Reading, PA",
    "Scranton, PA", "Bethlehem, PA", "Lancaster, PA", "Harrisburg, PA", "Altoona, PA",
    "York, PA", "State College, PA", "Wilkes-Barre, PA", "Chester, PA", "Williamsport, PA",
    
    # Rhode Island
    "Providence, RI", "Warwick, RI", "Cranston, RI", "Pawtucket, RI", "East Providence, RI",
    "Woonsocket, RI", "Coventry, RI", "Cumberland, RI", "North Providence, RI", "South Kingstown, RI",
    "West Warwick, RI", "Johnston, RI", "North Kingstown, RI", "Newport, RI", "Bristol, RI",
    
    # South Carolina
    "Columbia, SC", "Charleston, SC", "North Charleston, SC", "Mount Pleasant, SC", "Rock Hill, SC",
    "Greenville, SC", "Summerville, SC", "Sumter, SC", "Goose Creek, SC", "Hilton Head Island, SC",
    "Florence, SC", "Spartanburg, SC", "Myrtle Beach, SC", "Aiken, SC", "Anderson, SC",
    
    # South Dakota
    "Sioux Falls, SD", "Rapid City, SD", "Aberdeen, SD", "Brookings, SD", "Watertown, SD",
    "Mitchell, SD", "Yankton, SD", "Pierre, SD", "Huron, SD", "Vermillion, SD",
    "Spearfish, SD", "Brandon, SD", "Box Elder, SD", "Sturgis, SD", "Madison, SD",
    
    # Tennessee
    "Nashville, TN", "Memphis, TN", "Knoxville, TN", "Chattanooga, TN", "Clarksville, TN",
    "Murfreesboro, TN", "Franklin, TN", "Jackson, TN", "Johnson City, TN", "Bartlett, TN",
    "Hendersonville, TN", "Kingsport, TN", "Collierville, TN", "Cleveland, TN", "Smyrna, TN",
    
    # Texas
    "Houston, TX", "San Antonio, TX", "Dallas, TX", "Austin, TX", "Fort Worth, TX",
    "El Paso, TX", "Arlington, TX", "Corpus Christi, TX", "Plano, TX", "Laredo, TX",
    "Lubbock, TX", "Garland, TX", "Irving, TX", "Amarillo, TX", "Grand Prairie, TX",
    
    # Utah
    "Salt Lake City, UT", "West Valley City, UT", "Provo, UT", "West Jordan, UT", "Orem, UT",
    "Sandy, UT", "Ogden, UT", "St. George, UT", "Layton, UT", "South Jordan, UT",
    "Lehi, UT", "Millcreek, UT", "Taylorsville, UT", "Logan, UT", "Murray, UT",
    
    # Vermont
    "Burlington, VT", "South Burlington, VT", "Rutland, VT", "Essex, VT", "Colchester, VT",
    "Bennington, VT", "Brattleboro, VT", "Milton, VT", "Hartford, VT", "Springfield, VT",
    "Barre, VT", "Williston, VT", "Montpelier, VT", "Middlebury, VT", "St. Albans, VT",
    
    # Virginia
    "Virginia Beach, VA", "Norfolk, VA", "Chesapeake, VA", "Richmond, VA", "Newport News, VA",
    "Alexandria, VA", "Hampton, VA", "Roanoke, VA", "Portsmouth, VA", "Suffolk, VA",
    "Lynchburg, VA", "Harrisonburg, VA", "Leesburg, VA", "Charlottesville, VA", "Danville, VA",
    
    # Washington
    "Seattle, WA", "Spokane, WA", "Tacoma, WA", "Vancouver, WA", "Bellevue, WA",
    "Kent, WA", "Everett, WA", "Renton, WA", "Yakima, WA", "Federal Way, WA",
    "Spokane Valley, WA", "Bellingham, WA", "Kennewick, WA", "Auburn, WA", "Pasco, WA",
    
    # West Virginia
    "Charleston, WV", "Huntington, WV", "Morgantown, WV", "Parkersburg, WV", "Wheeling, WV",
    "Weirton, WV", "Fairmont, WV", "Beckley, WV", "Clarksburg, WV", "Martinsburg, WV",
    "South Charleston, WV", "St. Albans, WV", "Vienna, WV", "Bluefield, WV", "Moundsville, WV",
    
    # Wisconsin
    "Milwaukee, WI", "Madison, WI", "Green Bay, WI", "Kenosha, WI", "Racine, WI",
    "Appleton, WI", "Waukesha, WI", "Eau Claire, WI", "Oshkosh, WI", "Janesville, WI",
    "West Allis, WI", "La Crosse, WI", "Sheboygan, WI", "Wauwatosa, WI", "Fond du Lac, WI",
    
    # Wyoming
    "Cheyenne, WY", "Casper, WY", "Laramie, WY", "Gillette, WY", "Rock Springs, WY",
    "Sheridan, WY", "Green River, WY", "Evanston, WY", "Riverton, WY", "Jackson, WY",
    "Cody, WY", "Rawlins, WY", "Lander, WY", "Torrington, WY", "Powell, WY"
]

# --- NWS API Configuration ---
NWS_API_URL = "https://api.weather.gov/alerts/active"
NWS_API_HEADERS = {
    "User-Agent": CONFIG["NWS_USER_AGENT"], 
    "Accept": "application/geo+json"
}

# --- Radar Sites (abbreviated) ---
RADAR_SITES = [
    {"id": "KABR", "lat": 45.45, "lon": -98.41, "desc": "Aberdeen, SD"},
    {"id": "KABX", "lat": 35.15, "lon": -106.82, "desc": "Albuquerque, NM"},
    {"id": "KAKQ", "lat": 36.98, "lon": -77.01, "desc": "Norfolk/Richmond, VA"},
    {"id": "KAMA", "lat": 35.23, "lon": -101.71, "desc": "Amarillo, TX"},
    {"id": "KAMX", "lat": 25.61, "lon": -80.41, "desc": "Miami, FL"},
    {"id": "KAPX", "lat": 44.90, "lon": -84.72, "desc": "Gaylord, MI"},
    {"id": "KARX", "lat": 43.82, "lon": -91.19, "desc": "La Crosse, WI"},
    {"id": "KATX", "lat": 48.19, "lon": -122.49, "desc": "Seattle/Tacoma, WA"},
    {"id": "KBBX", "lat": 39.49, "lon": -121.63, "desc": "Beale AFB, CA"},
    {"id": "KBGM", "lat": 42.19, "lon": -75.98, "desc": "Binghamton, NY"},
    {"id": "KBHX", "lat": 40.49, "lon": -124.29, "desc": "Eureka, CA"},
    {"id": "KBIS", "lat": 46.77, "lon": -100.76, "desc": "Bismarck, ND"},
    {"id": "KBLX", "lat": 45.85, "lon": -108.60, "desc": "Billings, MT"},
    {"id": "KBMX", "lat": 33.17, "lon": -86.77, "desc": "Birmingham, AL"},
    {"id": "KBOI", "lat": 43.56, "lon": -116.24, "desc": "Boise, ID"},
    {"id": "KBOX", "lat": 41.95, "lon": -71.13, "desc": "Boston, MA"},
    {"id": "KBRO", "lat": 25.91, "lon": -97.42, "desc": "Brownsville, TX"},
    {"id": "KBUF", "lat": 42.94, "lon": -78.73, "desc": "Buffalo, NY"},
    {"id": "KBYX", "lat": 24.59, "lon": -81.70, "desc": "Key West, FL"},
    {"id": "KCAE", "lat": 33.94, "lon": -81.12, "desc": "Columbia, SC"},
    {"id": "KCBW", "lat": 46.04, "lon": -67.80, "desc": "Caribou, ME"},
    {"id": "KCCX", "lat": 40.92, "lon": -77.92, "desc": "State College, PA"},
    {"id": "KCLE", "lat": 41.41, "lon": -81.86, "desc": "Cleveland, OH"},
    {"id": "KCLX", "lat": 32.65, "lon": -81.04, "desc": "Charleston, SC"},
    {"id": "KCRP", "lat": 27.78, "lon": -97.51, "desc": "Corpus Christi, TX"},
    {"id": "KCXX", "lat": 44.51, "lon": -73.16, "desc": "Burlington, VT"},
    {"id": "KCYS", "lat": 41.15, "lon": -104.81, "desc": "Cheyenne, WY"},
    {"id": "KDAX", "lat": 38.50, "lon": -121.67, "desc": "Sacramento, CA"},
    {"id": "KDDC", "lat": 37.76, "lon": -99.97, "desc": "Dodge City, KS"},
    {"id": "KDFX", "lat": 29.27, "lon": -100.28, "desc": "Laughlin AFB, TX"},
    {"id": "KDGX", "lat": 32.32, "lon": -89.98, "desc": "Jackson, MS"},
    {"id": "KDIX", "lat": 39.94, "lon": -74.41, "desc": "Philadelphia, PA"},
    {"id": "KDLH", "lat": 46.83, "lon": -92.21, "desc": "Duluth, MN"},
    {"id": "KDMX", "lat": 41.73, "lon": -93.72, "desc": "Des Moines, IA"},
    {"id": "KDOX", "lat": 38.82, "lon": -75.44, "desc": "Dover AFB, DE"},
    {"id": "KDTX", "lat": 42.70, "lon": -83.47, "desc": "Detroit, MI"},
    {"id": "KDVN", "lat": 41.61, "lon": -90.58, "desc": "Davenport, IA"},
    {"id": "KDYX", "lat": 32.54, "lon": -99.25, "desc": "Dyess AFB, TX"},
    {"id": "KEAX", "lat": 38.81, "lon": -94.26, "desc": "Kansas City, MO"},
    {"id": "KEMX", "lat": 31.89, "lon": -110.63, "desc": "Tucson, AZ"},
    {"id": "KENX", "lat": 42.58, "lon": -74.06, "desc": "Albany, NY"},
    {"id": "KEOX", "lat": 31.46, "lon": -85.46, "desc": "Fort Rucker, AL"},
    {"id": "KEPZ", "lat": 31.87, "lon": -106.69, "desc": "El Paso, TX"},
    {"id": "KESX", "lat": 35.70, "lon": -114.89, "desc": "Las Vegas, NV"},
    {"id": "KEVX", "lat": 30.56, "lon": -85.92, "desc": "Eglin AFB, FL"},
    {"id": "KEWX", "lat": 29.70, "lon": -98.02, "desc": "Austin/San Antonio, TX"},
    {"id": "KEYX", "lat": 35.09, "lon": -117.56, "desc": "Edwards AFB, CA"},
    {"id": "KFCX", "lat": 37.02, "lon": -80.27, "desc": "Roanoke, VA"},
    {"id": "KFDR", "lat": 34.36, "lon": -98.97, "desc": "Frederick, OK"},
    {"id": "KFDX", "lat": 34.63, "lon": -103.63, "desc": "Cannon AFB, NM"},
    {"id": "KFFC", "lat": 33.36, "lon": -84.57, "desc": "Atlanta, GA"},
    {"id": "KFSD", "lat": 43.58, "lon": -96.73, "desc": "Sioux Falls, SD"},
    {"id": "KFSX", "lat": 34.57, "lon": -111.19, "desc": "Flagstaff, AZ"},
    {"id": "KFTG", "lat": 39.79, "lon": -104.54, "desc": "Denver, CO"},
    {"id": "KFWS", "lat": 32.57, "lon": -97.30, "desc": "Dallas/Fort Worth, TX"},
    {"id": "KGGW", "lat": 48.20, "lon": -106.62, "desc": "Glasgow, MT"},
    {"id": "KGJX", "lat": 39.06, "lon": -108.21, "desc": "Grand Junction, CO"},
    {"id": "KGLD", "lat": 39.37, "lon": -101.70, "desc": "Goodland, KS"},
    {"id": "KGRB", "lat": 44.49, "lon": -88.11, "desc": "Green Bay, WI"},
    {"id": "KGRK", "lat": 30.72, "lon": -97.38, "desc": "Fort Hood, TX"},
    {"id": "KGRR", "lat": 42.89, "lon": -85.54, "desc": "Grand Rapids, MI"},
    {"id": "KGSP", "lat": 34.88, "lon": -82.22, "desc": "Greenville/Spartanburg, SC"},
    {"id": "KGWX", "lat": 33.89, "lon": -88.33, "desc": "Columbus AFB, MS"},
    {"id": "KGYX", "lat": 43.89, "lon": -70.25, "desc": "Portland, ME"},
    {"id": "KHDX", "lat": 33.07, "lon": -106.12, "desc": "Holloman AFB, NM"},
    {"id": "KHGX", "lat": 29.47, "lon": -95.08, "desc": "Houston, TX"},
    {"id": "KHNX", "lat": 36.31, "lon": -119.63, "desc": "San Joaquin Valley, CA"},
    {"id": "KHPX", "lat": 36.73, "lon": -87.28, "desc": "Fort Campbell, KY"},
    {"id": "KHTX", "lat": 34.93, "lon": -86.08, "desc": "Huntsville, AL"},
    {"id": "KICT", "lat": 37.65, "lon": -97.44, "desc": "Wichita, KS"},
    {"id": "KICX", "lat": 37.59, "lon": -112.86, "desc": "Cedar City, UT"},
    {"id": "KILN", "lat": 39.42, "lon": -83.82, "desc": "Cincinnati, OH"},
    {"id": "KILX", "lat": 40.15, "lon": -89.33, "desc": "Lincoln, IL"},
    {"id": "KIND", "lat": 39.70, "lon": -86.29, "desc": "Indianapolis, IN"},
    {"id": "KINX", "lat": 36.17, "lon": -95.56, "desc": "Tulsa, OK"},
    {"id": "KIWA", "lat": 33.29, "lon": -111.67, "desc": "Phoenix, AZ"},
    {"id": "KIWX", "lat": 41.35, "lon": -85.70, "desc": "Northern Indiana"},
    {"id": "KJAX", "lat": 30.48, "lon": -81.70, "desc": "Jacksonville, FL"},
    {"id": "KJGX", "lat": 32.67, "lon": -83.35, "desc": "Robins AFB, GA"},
    {"id": "KJKL", "lat": 37.59, "lon": -83.31, "desc": "Jackson, KY"},
    {"id": "KLBB", "lat": 33.65, "lon": -101.81, "desc": "Lubbock, TX"},
    {"id": "KLCH", "lat": 30.12, "lon": -93.21, "desc": "Lake Charles, LA"},
    {"id": "KHDC", "lat": 30.33, "lon": -89.82, "desc": "New Orleans, LA"},
    {"id": "KLNX", "lat": 41.95, "lon": -100.57, "desc": "North Platte, NE"},
    {"id": "KLOT", "lat": 41.60, "lon": -88.08, "desc": "Chicago, IL"},
    {"id": "KLRX", "lat": 40.73, "lon": -116.80, "desc": "Elko, NV"},
    {"id": "KLSX", "lat": 38.69, "lon": -90.68, "desc": "St. Louis, MO"},
    {"id": "KLTX", "lat": 33.99, "lon": -78.42, "desc": "Wilmington, NC"},
    {"id": "KLVX", "lat": 37.97, "lon": -85.94, "desc": "Louisville, KY"},
    {"id": "KLWX", "lat": 38.97, "lon": -77.48, "desc": "Sterling, VA"},
    {"id": "KLZK", "lat": 34.83, "lon": -92.25, "desc": "Little Rock, AR"},
    {"id": "KMAF", "lat": 31.94, "lon": -102.19, "desc": "Midland/Odessa, TX"},
    {"id": "KMAX", "lat": 42.08, "lon": -122.72, "desc": "Medford, OR"},
    {"id": "KMBX", "lat": 48.39, "lon": -100.86, "desc": "Minot AFB, ND"},
    {"id": "KMHX", "lat": 34.77, "lon": -76.87, "desc": "Morehead City, NC"},
    {"id": "KMKX", "lat": 42.96, "lon": -88.55, "desc": "Milwaukee, WI"},
    {"id": "KMLB", "lat": 28.11, "lon": -80.65, "desc": "Melbourne, FL"},
    {"id": "KMOB", "lat": 30.68, "lon": -88.24, "desc": "Mobile, AL"},
    {"id": "KMPX", "lat": 44.85, "lon": -93.56, "desc": "Minneapolis/St. Paul, MN"},
    {"id": "KMQT", "lat": 46.53, "lon": -87.55, "desc": "Marquette, MI"},
    {"id": "KMRX", "lat": 36.17, "lon": -83.40, "desc": "Knoxville/Tri-Cities, TN"},
    {"id": "KMSX", "lat": 47.04, "lon": -113.98, "desc": "Missoula, MT"},
    {"id": "KMTX", "lat": 41.26, "lon": -112.45, "desc": "Salt Lake City, UT"},
    {"id": "KMUX", "lat": 37.15, "lon": -121.89, "desc": "San Francisco, CA"},
    {"id": "KMVX", "lat": 47.52, "lon": -97.32, "desc": "Grand Forks, ND"},
    {"id": "KMXX", "lat": 32.53, "lon": -85.78, "desc": "Maxwell AFB, AL"},
    {"id": "KNKX", "lat": 32.92, "lon": -117.04, "desc": "San Diego, CA"},
    {"id": "KNQA", "lat": 35.34, "lon": -89.87, "desc": "Memphis, TN"},
    {"id": "KOAX", "lat": 41.32, "lon": -96.36, "desc": "Omaha, NE"},
    {"id": "KOHX", "lat": 36.25, "lon": -86.56, "desc": "Nashville, TN"},
    {"id": "KOKX", "lat": 40.86, "lon": -72.86, "desc": "New York City, NY"},
    {"id": "KOTX", "lat": 47.68, "lon": -117.63, "desc": "Spokane, WA"},
    {"id": "KPAH", "lat": 37.07, "lon": -88.77, "desc": "Paducah, KY"},
    {"id": "KPBZ", "lat": 40.53, "lon": -80.22, "desc": "Pittsburgh, PA"},
    {"id": "KPDT", "lat": 45.69, "lon": -118.85, "desc": "Pendleton, OR"},
    {"id": "KPOE", "lat": 31.15, "lon": -92.97, "desc": "Fort Polk, LA"},
    {"id": "KPUX", "lat": 38.46, "lon": -104.18, "desc": "Pueblo, CO"},
    {"id": "KRAX", "lat": 35.66, "lon": -78.49, "desc": "Raleigh/Durham, NC"},
    {"id": "KRGX", "lat": 39.75, "lon": -119.46, "desc": "Reno, NV"},
    {"id": "KRIW", "lat": 43.06, "lon": -108.47, "desc": "Riverton, WY"},
    {"id": "KRLX", "lat": 38.30, "lon": -81.72, "desc": "Charleston, WV"},
    {"id": "KRTX", "lat": 45.71, "lon": -122.96, "desc": "Portland, OR"},
    {"id": "KSFX", "lat": 43.10, "lon": -112.68, "desc": "Pocatello/Idaho Falls, ID"},
    {"id": "KSGF", "lat": 37.23, "lon": -93.40, "desc": "Springfield, MO"},
    {"id": "KSHV", "lat": 32.45, "lon": -93.84, "desc": "Shreveport, LA"},
    {"id": "KSJT", "lat": 31.37, "lon": -100.49, "desc": "San Angelo, TX"},
    {"id": "KSOX", "lat": 33.82, "lon": -117.64, "desc": "Santa Ana Mountains, CA"},
    {"id": "KSRX", "lat": 35.29, "lon": -94.36, "desc": "Fort Smith, AR"},
    {"id": "KTBW", "lat": 27.70, "lon": -82.40, "desc": "Tampa, FL"},
    {"id": "KTFX", "lat": 47.45, "lon": -111.38, "desc": "Great Falls, MT"},
    {"id": "KTLH", "lat": 30.39, "lon": -84.33, "desc": "Tallahassee, FL"},
    {"id": "KTLX", "lat": 35.33, "lon": -97.27, "desc": "Oklahoma City, OK"},
    {"id": "KTWX", "lat": 38.99, "lon": -96.23, "desc": "Topeka, KS"},
    {"id": "KTYX", "lat": 43.75, "lon": -75.68, "desc": "Fort Drum, NY"},
    {"id": "KUDX", "lat": 44.12, "lon": -102.83, "desc": "Rapid City, SD"},
    {"id": "KUEX", "lat": 40.32, "lon": -98.44, "desc": "Hastings, NE"},
    {"id": "KVAX", "lat": 30.89, "lon": -83.00, "desc": "Moody AFB, GA"},
    {"id": "KVBX", "lat": 34.84, "lon": -120.40, "desc": "Vandenberg AFB, CA"},
    {"id": "KVNX", "lat": 36.74, "lon": -98.12, "desc": "Vance AFB, OK"},
    {"id": "KVTX", "lat": 34.41, "lon": -119.18, "desc": "Los Angeles, CA"},
    {"id": "KVWX", "lat": 38.26, "lon": -87.72, "desc": "Evansville, IN"},
    {"id": "KYUX", "lat": 32.49, "lon": -114.65, "desc": "Yuma, AZ"}
]

# ========================================================================================
# --- GLOBAL STATE ---
# ========================================================================================
active_warnings_cache = []
last_action_timestamp = 0
warning_display_index = 0
cities_shown_in_break = 0
warnings_shown_in_cycle = 0  # Track how many warnings we've shown in the current cycle
current_mode = "idle"  # "idle", "warnings", "cities"
current_display = "current"  # "current", "forecast", "three_day", "astronomy", "air_quality"
display_start_time = 0  # Timer for individual display box (e.g., current, forecast)
city_start_time = 0     # Timer for overall city display (e.g., 60 seconds per city)
weather_cache = {}      # Cache for weather data
geolocator = Nominatim(user_agent=CONFIG["GEOLOCATION_USER_AGENT"])
current_city = None     # Track the current city being displayed

WARNING_DURATIONS = {
    "PDS": 90,  # 90 seconds for PDS warnings
    "Tornado Warning": 60,  # 60 seconds for regular tornado warnings
    "Severe Thunderstorm Warning": 30  # 30 seconds for severe t-storm warnings
}

# ========================================================================================
# --- SYSTEM & NAVIGATION FUNCTIONS ---
# ========================================================================================
def initialize_pyautogui():
    """Initialize PyAutoGUI settings"""
    # Disable failsafe to prevent errors when moving to corners
    pyautogui.FAILSAFE = False
    logger.info("PyAutoGUI failsafe disabled")
    
    # Set a reasonable pause between PyAutoGUI commands
    pyautogui.PAUSE = 0.5

def force_focus_on_app():
    """Finds, activates, and clicks an offset point to focus the map pane."""
    try:
        windows = gw.getWindowsWithTitle(CONFIG["WEATHER_WISE_WINDOW_TITLE"])
        if not windows:
            logger.error(f"WINDOW NOT FOUND: '{CONFIG['WEATHER_WISE_WINDOW_TITLE']}'")
            return False
        app_window = windows[0]
        logger.debug(f"Found window: {app_window.title} at {app_window.box}")
        
        if not app_window.isActive:
            logger.debug(f"Window is not active. Activating: {app_window.title}")
            app_window.restore() # Ensure it's not minimized
            app_window.activate()
            time.sleep(2.0) # Increased sleep for activation robustness
            logger.debug(f"Window activated. Is active now: {app_window.isActive}")
            
        window_rect = app_window.box
        offset_x = window_rect.left + (window_rect.width * 0.08)
        offset_y = window_rect.top + (window_rect.height * 0.08)
        
        logger.debug(f"Clicking at relative coordinates: ({offset_x:.2f}, {offset_y:.2f}) within window {app_window.box}")
        pyautogui.click(offset_x, offset_y)
        time.sleep(0.5)
        logger.info("SUCCESS: Window focused by clicking offset point.")
        return True
    except Exception as e:
        logger.error(f"ERROR: Could not focus window: {e}")
        return False

def navigate_by_name(search_term: str, zoom_out_steps: int):
    """Navigates Weather Wise and zooms out a specified number of times."""
    logger.info(f"\n>>> ACTION: Navigating to '{search_term}'")
    
    logger.debug("Pressing HOTKEY_SHOW_GRAPHIC")
    pyautogui.hotkey(*CONFIG["HOTKEY_SHOW_GRAPHIC"])
    time.sleep(1.0) # Increased delay
    
    try:
        if not force_focus_on_app():
            logger.debug("Failed to focus app, pressing HOTKEY_HIDE_GRAPHIC and returning.")
            pyautogui.hotkey(*CONFIG["HOTKEY_HIDE_GRAPHIC"])
            return
        
        logger.debug("Pressing ESCAPE (x2)")
        pyautogui.press('escape', presses=2, interval=0.5) # Increased interval
        time.sleep(1.0) # Increased delay
        
        logger.debug("Pressing 's' for search")
        pyautogui.press('s')
        time.sleep(1.5) # Increased delay for search bar to appear
        
        logger.debug(f"Typing search term: '{search_term}'")
        pyautogui.write(search_term, interval=0.05)
        time.sleep(1.0) # Increased delay
        
        logger.debug("Pressing TAB")
        pyautogui.press('tab')
        time.sleep(1.0) # Increased delay
        
        logger.debug("Pressing ENTER")
        pyautogui.press('enter')
        time.sleep(CONFIG["POST_SEARCH_DELAY_SECONDS"]) # This is already a longer delay
        
        logger.debug("Pressing ESCAPE")
        pyautogui.press('escape')
        time.sleep(1.0) # Increased delay
        
        logger.info("SUCCESS: Search executed.")
        
        if zoom_out_steps > 0:
            logger.debug(f"Attempting to focus app for zoom out.")
            if force_focus_on_app(): # Re-focus before zooming
                logger.info(f"...Zooming out {zoom_out_steps} step(s)")
                for i in range(zoom_out_steps):
                    logger.debug(f"Pressing '-' (zoom out) {i+1}/{zoom_out_steps}")
                    pyautogui.press('-')
                    time.sleep(0.5) # Increased delay
                logger.info("SUCCESS: Zoom applied.")
            else:
                logger.warning("Could not focus app to apply zoom. Skipping zoom.")
        
        logger.info("...Toggling radar playback.")
        pyautogui.press(CONFIG["HOTKEY_PLAYBACK_TOGGLE"])
        time.sleep(0.5)
    except Exception as e:
        logger.error(f"ERROR: UI automation failed during navigation: {e}")
    finally:
        logger.debug("Pressing HOTKEY_HIDE_GRAPHIC")
        pyautogui.hotkey(*CONFIG["HOTKEY_HIDE_GRAPHIC"])
        screen_width, _ = pyautogui.size()
        logger.debug(f"Parking cursor at screen corner: ({screen_width - 1}, 1)")
        pyautogui.moveTo(screen_width - 1, 1, duration=0.25)
        logger.info("...Cursor parked.")

# ========================================================================================
# --- DATA WRITING FUNCTIONS ---
# ========================================================================================
def write_infobox_data(warning_feature):
    """Write warning data to JSON file for display"""
    try:
        props = warning_feature.get('properties') if warning_feature else None
        if not props:
            data_to_write = {"visible": False}
        else:
            params = props.get('parameters') or {}
            threats = extract_threats_from_description(props.get('description', ''))
            
            # Check for PDS status in headline or description
            is_pds = False
            headline = props.get('headline', '').upper()
            description = props.get('description', '').upper()
            
            if "PARTICULARLY DANGEROUS SITUATION" in headline or "PARTICULARLY DANGEROUS SITUATION" in description:
                is_pds = True
            
            data_to_write = {
                "visible": True,
                "type": "TORNADO WARNING" if props.get('event') == "Tornado Warning" else "SEVERE T-STORM WARNING",
                "area": props.get('areaDesc', 'N/A'),
                "population": f"{params.get('population', [0])[0]:,}" if params.get('population', [0])[0] > 0 else "N/A",
                "severity": props.get('severity', 'N/A'),
                "certainty": props.get('certainty', 'N/A'),
                "wind": f"{params.get('windGust', [None])[0]} MPH" if params.get('windGust', [None])[0] else threats.get('wind', "N/A"),
                "hail": f'{params.get("hailSize", [None])[0]}"' if params.get("hailSize", [None])[0] else threats.get('hail', "N/A"),
                "expires": get_formatted_expiration(props.get('expires'), CONFIG["LOCAL_TIMEZONE"]),
                "isPDS": is_pds  # Add PDS status to JSON data
            }
        with open('warning_data.json', 'w', encoding='utf-8') as f:
            json.dump(data_to_write, f, indent=4)
            create_html(data_to_write, 'warning_data.html')

        # Jenny voice TTS
        try:
            from yallbot_jenny_tts import generate_tts_for_alert
            import asyncio
            if data_to_write.get("visible", False):
                alert_text = f"{data_to_write['type']} issued for the counties of {data_to_write['area']}. " \
                             f"Severity: {data_to_write['severity']}. Please take immediate precautions."
                asyncio.run(generate_tts_for_alert(alert_text, f"{data_to_write['type']}_{int(time.time())}"))
        except Exception as e:
            logger.error(f"Jenny TTS failed: {e}")
    except Exception as e:
        logger.error(f"ERROR writing warning data: {e}", exc_info=True)

def hide_all_weather_displays():
    """Hide all weather display boxes"""
    for filename in ['current_conditions.json', 'daily_forecast.json', 'three_day_forecast.json', 'astronomy.json', 'air_quality.json', 'warning_data.json']:
        try:
            with open(filename, 'w') as f:
                json.dump({"visible": False}, f)
        except Exception as e:
            logger.error(f"ERROR hiding display {filename}: {e}")

# ========================================================================================
# --- WEATHERAPI FUNCTIONS ---
# ========================================================================================
@rate_limit(min_interval=1.0)
def get_weatherapi_data(city_name):
    """Fetch weather data from WeatherAPI.com"""
    global weather_cache
    
    if not CONFIG["WEATHER_API_ENABLED"] or CONFIG["WEATHER_API_KEY"] == "09846f8f8afa4a2bb19194147250907 ":
        return None
    
    # Check cache first
    cache_key = city_name.lower()
    if cache_key in weather_cache and time.time() - weather_cache[cache_key]['timestamp'] < CONFIG["CACHE_DURATION"]:
        return weather_cache[cache_key]['data']
    
    try:
        params = {
            'key': CONFIG["WEATHER_API_KEY"],
            'q': city_name,
            'aqi': 'yes',
            'alerts': 'yes',
            'days': 3  # Get 3 days of forecast data
        }
        
        response = requests.get('https://api.weatherapi.com/v1/forecast.json', params=params, timeout=15)
        response.raise_for_status()
        
        astro_response = requests.get('https://api.weatherapi.com/v1/astronomy.json', params=params, timeout=15)
        astro_response.raise_for_status()
        
        combined_data = {
            'weather': response.json(),
            'astronomy': astro_response.json()
        }
        
        weather_cache[city_name.lower()] = {
            'timestamp': time.time(),
            'data': combined_data
        }
        
        return combined_data
    except Exception as e:
        logger.error(f"ERROR: Failed to get WeatherAPI data for {city_name}: {e}")
        return None

def write_current_conditions(city_name, api_data):
    """Write current conditions data to JSON file"""
    if not api_data or 'weather' not in api_data:
        with open('current_conditions.json', 'w') as f:
            json.dump({"visible": False}, f)
        return
    
    try:
        current = api_data['weather'].get('current', {})
        location = api_data['weather'].get('location', {})
        
        # Calculate dewpoint if not provided
        dewpoint_f = current.get('dewpoint_f')
        if not dewpoint_f and (temp_c := current.get('temp_c')) is not None and (hum := current.get('humidity')) is not None:
            gamma = math.log(hum / 100.0) + (18.678 * temp_c) / (257.14 + temp_c)
            dewpoint_f = ((257.14 * gamma) / (18.678 - gamma) * 9/5) + 32
        
        # Determine UV index description
        uv_index = current.get('uv', 0)
        if uv_index > 10:
            uv_desc = "Extreme"
        elif uv_index > 7:
            uv_desc = "Very High"
        elif uv_index > 5:
            uv_desc = "High"
        elif uv_index > 2:
            uv_desc = "Moderate"
        else:
            uv_desc = "Low"
        
        data = {
            "visible": True,
            "location": f"{location.get('name')}, {location.get('region')}",
            "temperature": current.get('temp_f'),
            "feelsLike": current.get('feelslike_f'),
            "description": current.get('condition', {}).get('text'),
            "wind": f"{current.get('wind_dir')} {current.get('wind_mph', 0)} MPH" if current.get('wind_mph', 0) > 0 else "Calm",
            "windGust": f"{current.get('gust_mph')} MPH" if current.get('gust_mph') else "N/A",
            "humidity": f"{current.get('humidity')}%",
            "dewpoint": dewpoint_f,
            "pressure": f"{current.get('pressure_in')} in",
            "visibility": f"{current.get('vis_miles')} miles",
            "uvIndex": f"{uv_index} ({uv_desc})",
            "dataSource": "WeatherAPI.com"
        }
        
        with open('current_conditions.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"ERROR: Failed to write current conditions: {e}", exc_info=True)

def write_daily_forecast(city_name, api_data):
    """Write daily forecast data to JSON file"""
    if not api_data or not api_data.get('weather', {}).get('forecast', {}).get('forecastday'):
        with open('daily_forecast.json', 'w') as f:
            json.dump({"visible": False}, f)
        return
    
    try:
        day = api_data['weather']['forecast']['forecastday'][0]['day']
        location = api_data['weather']['location']
        
        data = {
            "visible": True,
            "location": f"{location.get('name')}, {location.get('region')}",
            "maxTemp": day.get('maxtemp_f'),
            "minTemp": day.get('mintemp_f'),
            "icon": map_weatherapi_icon(day.get('condition', {}).get('code')),
            "condition": day.get('condition', {}).get('text'),
            "chanceOfRain": day.get('daily_chance_of_rain'),
            "chanceOfSnow": day.get('daily_chance_of_snow'),
            "maxWind": f"{day.get('maxwind_mph')} MPH",
            "totalPrecip": f"{day.get('totalprecip_in')} in",
            "avgHumidity": day.get('avghumidity'),
            "uvIndex": day.get('uv'),
            "dataSource": "WeatherAPI.com"
        }
        
        with open('daily_forecast.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"ERROR: Failed to write daily forecast: {e}", exc_info=True)

def write_three_day_forecast(city_name, api_data):
    """Write 3-day forecast data to JSON file"""
    if not api_data or not api_data.get('weather', {}).get('forecast', {}).get('forecastday'):
        with open('three_day_forecast.json', 'w') as f:
            json.dump({"visible": False}, f)
        return
    
    try:
        forecast = api_data['weather']['forecast']['forecastday']
        location = api_data['weather']['location']
        
        days = []
        for day_data in forecast:
            day = day_data.get('day', {})
            days.append({
                "date": day_data.get('date'),
                "maxTemp": day.get('maxtemp_f'),
                "minTemp": day.get('mintemp_f'),
                "icon": map_weatherapi_icon(day.get('condition', {}).get('code')),
                "condition": day.get('condition', {}).get('text'),
                "chanceOfRain": day.get('daily_chance_of_rain'),
                "maxWind": f"{day.get('maxwind_mph')} MPH",
                "avgHumidity": day.get('avghumidity'),
                "uvIndex": day.get('uv')
            })
        
        data = {
            "visible": True,
            "location": f"{location.get('name')}, {location.get('region')}",
            "days": days,
            "dataSource": "WeatherAPI.com"
        }
        
        with open('three_day_forecast.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"ERROR: Failed to write 3-day forecast: {e}", exc_info=True)

def write_astronomy_data(city_name, api_data):
    """Write astronomy data to JSON file"""
    if not api_data or not api_data.get('astronomy', {}).get('astronomy', {}).get('astro'):
        with open('astronomy.json', 'w') as f:
            json.dump({"visible": False}, f)
        return
    
    try:
        astro = api_data['astronomy']['astronomy']['astro']
        location = api_data['astronomy']['location']
        
        daylight_str = "N/A"
        try:
            sunrise_time = datetime.strptime(astro.get('sunrise'), "%I:%M %p")
            sunset_time = datetime.strptime(astro.get('sunset'), "%I:%M %p")
            daylight_delta = sunset_time - sunrise_time
            daylight_hours = daylight_delta.seconds // 3600
            daylight_minutes = (daylight_delta.seconds % 3600) // 60
            daylight_str = f"{daylight_hours} hrs {daylight_minutes} min"
        except:
            pass
        
        data = {
            "visible": True,
            "location": f"{location.get('name')}, {location.get('region')}",
            "moonPhase": astro.get('moon_phase'),
            "sunrise": astro.get('sunrise'),
            "sunset": astro.get('sunset'),
            "daylightHours": daylight_str,
            "moonrise": astro.get('moonrise'),
            "moonset": astro.get('moonset'),
            "moonIllumination": astro.get('moon_illumination'),
            "dataSource": "WeatherAPI.com"
        }
        
        with open('astronomy.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"ERROR: Failed to write astronomy data: {e}", exc_info=True)

def write_air_quality_data(city_name, api_data):
    """Write air quality data to JSON file"""
    if not api_data or not api_data.get('weather', {}).get('current', {}).get('air_quality'):
        with open('air_quality.json', 'w') as f:
            json.dump({"visible": False}, f)
        return
    
    try:
        aq = api_data['weather']['current']['air_quality']
        location = api_data['weather']['location']
        
        data = {
            "visible": True,
            "location": f"{location.get('name')}, {location.get('region')}",
            "aqiIndex": aq.get('us-epa-index'),
            "co": f"{aq.get('co', 0):.1f} μg/m³",
            "o3": f"{aq.get('o3', 0):.1f} μg/m³",
            "no2": f"{aq.get('no2', 0):.1f} μg/m³",
            "so2": f"{aq.get('so2', 0):.1f} μg/m³",
            "pm2_5": f"{aq.get('pm2_5', 0):.1f} μg/m³",
            "pm10": f"{aq.get('pm10', 0):.1f} μg/m³",
            "dataSource": "WeatherAPI.com"
        }
        
        with open('air_quality.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"ERROR: Failed to write air quality data: {e}", exc_info=True)

def map_weatherapi_icon(code):
    """Map WeatherAPI condition codes to appropriate icons"""
    if code == 1000:
        return "sunny"
    if code == 1003:
        return "partly-cloudy"
    if code in [1006, 1009]:
        return "cloudy"
    if code in [1063, 1180, 1183, 1186, 1189, 1192, 1195]:
        return "rain"
    if code in [1087, 1273, 1276, 1279, 1282]:
        return "thunderstorm"
    if code in [1066, 1114, 1117, 1210, 1213, 1216, 1219, 1222, 1225]:
        return "snow"
    if code in [1030, 1135, 1147]:
        return "fog"
    return "unknown"

def calculate_weather_activity_score(warnings):
    """Calculate a weather activity score based on active warnings"""
    score = 0
    severity_counts = {"Extreme": 0, "Severe": 0, "Moderate": 0, "Minor": 0, "Unknown": 0}
    type_counts = {}
    pds_count = 0
    
    # Process each warning
    for warning in warnings:
        props = warning.get('properties', {})
        event_type = props.get('event', 'Unknown')
        severity = props.get('severity', 'Unknown')
        
        # Count by type
        if event_type not in type_counts:
            type_counts[event_type] = 0
        type_counts[event_type] += 1
        
        # Count by severity
        severity_counts[severity] += 1
        
        # Base score by event type
        if event_type == "Tornado Warning":
            base_score = 10
        elif event_type == "Severe Thunderstorm Warning":
            base_score = 5
        else:
            base_score = 2
        
        # Adjust by severity
        if severity == "Extreme":
            base_score *= 2.0
        elif severity == "Severe":
            base_score *= 1.5
        elif severity == "Moderate":
            base_score *= 1.0
        elif severity == "Minor":
            base_score *= 0.5
        
        # Check for PDS
        is_pds = False
        headline = props.get('headline', '').upper()
        description = props.get('description', '').upper()
        if "PARTICULARLY DANGEROUS SITUATION" in headline or "PARTICULARLY DANGEROUS SITUATION" in description:
            is_pds = True
            base_score *= 1.5  # 50% increase for PDS warnings
            
            # Count PDS tornado warnings separately
            if event_type == "Tornado Warning":
                pds_count += 1
        
        # Add to total score
        score += base_score
    
    # Create score data object
    score_data = {
        "total_score": round(score, 1),
        "severity_counts": severity_counts,
        "type_counts": type_counts,
        "pds_count": pds_count,
        "timestamp": datetime.now().isoformat()
    }
    
    return score_data

def write_weather_activity_score(warnings):
    """Calculate and write weather activity score to JSON file"""
    try:
        score_data = calculate_weather_activity_score(warnings)
        
        with open('weather_score.json', 'w', encoding='utf-8') as f:
            json.dump(score_data, f, indent=4)
        
        logger.info(f"Weather Activity Score: {score_data['total_score']} (based on {len(warnings)} warnings)")
        
        # Log PDS tornado warnings if any
        if score_data['pds_count'] > 0:
            logger.warning(f"ALERT: {score_data['pds_count']} PDS Tornado Warning(s) active!")
        
        return score_data
    except Exception as e:
        logger.error(f"ERROR: Failed to write weather activity score: {e}", exc_info=True)
        
        # Write a default score in case of error
        try:
            with open('weather_score.json', 'w', encoding='utf-8') as f:
                json.dump({
                    "total_score": 0,
                    "severity_counts": {"Extreme": 0, "Severe": 0, "Moderate": 0, "Minor": 0, "Unknown": 0},
                    "type_counts": {},
                    "pds_count": 0,
                    "timestamp": datetime.now().isoformat()
                }, f, indent=4)
        except:
            pass
        
        return None

# ========================================================================================
# --- DATA FETCHING AND PARSING FUNCTIONS FOR NWS WARNINGS ---
# ========================================================================================
def is_warning_expired(warning_feature):
    """Check if a warning has expired"""
    try:
        return datetime.fromisoformat(warning_feature['properties']['expires']) <= datetime.now(pytz.utc)
    except:
        return True

def cleanup_old_warnings():
    """Remove expired warnings from cache"""
    global active_warnings_cache
    active_warnings_cache = [w for w in active_warnings_cache if not is_warning_expired(w)]

def merge_new_warnings(current_warnings, existing_warnings):
    """Merge new warnings with existing ones, prioritizing PDS Tornado, then Tornado, then Severe T-storm"""
    existing_ids = {w.get('id') for w in existing_warnings}
    new = [w for w in current_warnings if w.get('id') not in existing_ids]
    still_active = [w for w in existing_warnings if w.get('id') in {cw.get('id') for cw in current_warnings}]
    combined = new + still_active
    combined.sort(key=lambda w: (
        0 if is_pds_warning(w) and w['properties']['event'] == "Tornado Warning" else
        1 if w['properties']['event'] == "Tornado Warning" else
        2,
        w['properties']['sent']
    ))
    return combined

def get_formatted_expiration(expires_str, local_tz_str):
    """Format expiration time for display"""
    try:
        # Attempt to parse the expires_str, handling both timezone-aware and unaware strings
        try:
            expires_dt = datetime.fromisoformat(expires_str)
        except ValueError:
            expires_dt = datetime.strptime(expires_str, "%Y-%m-%dT%H:%M:%S%z")
        
        local_tz = pytz.timezone(local_tz_str)
        expires_dt_local = expires_dt.astimezone(local_tz)
        
        # Use %#I on Windows or %-I on Unix-like systems
        try:
            # Try Unix-style format first
            return expires_dt_local.strftime("%-I:%M %p %Z")
        except ValueError:
            # Fall back to Windows-style format
            return expires_dt_local.strftime("%#I:%M %p %Z")
    except Exception as e:
        logger.error(f"WARNING: Could not format expiration time: {expires_str} - Error: {e}")
        return "N/A"  # Return N/A only if parsing fails

def extract_threats_from_description(description_text):
    """Extract wind and hail threat information from warning description"""
    threats = {'wind': None, 'hail': None}
    if not description_text:
        return threats
    
    match = re.search(r'HAZARD\.\.\.(.*)', description_text, re.IGNORECASE)
    if not match:
        return threats
    
    hazard = match.group(1).upper()
    
    if m := re.search(r'(\d+)\s*MPH', hazard):
        threats['wind'] = f"{m.group(1)} MPH"
    
    if m := re.search(r'(\d+\.?\d*)\s*INCH', hazard):
        threats['hail'] = f'{m.group(1)}"'
    else:
        for name, size in {"BASEBALL": '2.75"', "TENNIS BALL": '2.50"', "GOLF BALL": '1.75"', "QUARTER": '1.00"'}.items():
            if name in hazard:
                threats['hail'] = size
                break
    
    return threats

# Add these helper functions
def is_pds_warning(warning_feature):
    """Check if a warning is a PDS warning"""
    props = warning_feature.get('properties', {})
    headline = props.get('headline', '').upper()
    description = props.get('description', '').upper()
    return "PARTICULARLY DANGEROUS SITUATION" in headline or "PARTICULARLY DANGEROUS SITUATION" in description

def get_warning_duration(warning_feature):
    """Get the display duration for a warning based on its type and PDS status"""
    props = warning_feature.get('properties', {})
    event_type = props.get('event', 'Unknown')
    
    if is_pds_warning(warning_feature) and event_type == "Tornado Warning":
        return WARNING_DURATIONS["PDS"]
    elif event_type in WARNING_DURATIONS:
        return WARNING_DURATIONS[event_type]
    else:
        return CONFIG["WARNING_INTERLEAVE_CYCLE_SECONDS"]  # Default duration

def check_for_new_high_priority_warnings():
    """Check if there are new high-priority warnings (PDS or Tornado) that should be shown immediately"""
    global active_warnings_cache, warning_display_index
    
    if not active_warnings_cache:
        return False
    
    # Get the current warning index
    current_index = warning_display_index % len(active_warnings_cache)
    
    # Check if there are any PDS tornado warnings that we haven't shown yet
    for i, warning in enumerate(active_warnings_cache):
        if i <= current_index:
            continue  # Skip warnings we've already shown or are currently showing
        
        props = warning.get('properties', {})
        event_type = props.get('event', '')
        
        # If it's a PDS tornado warning or a regular tornado warning, we should show it immediately
        if (event_type == "Tornado Warning" and is_pds_warning(warning)) or event_type == "Tornado Warning":
            logger.info(f"Found new high-priority warning: {event_type}{' (PDS)' if is_pds_warning(warning) else ''}")
            return True
    
    return False

@rate_limit(min_interval=1.0)
def get_and_sort_active_warnings():
    """Fetch active warnings from NWS API and sort by priority"""
    try:
        r = requests.get(NWS_API_URL, headers=NWS_API_HEADERS, timeout=15)
        r.raise_for_status()

        # Simplified filtering and sorting
        warnings = [
            f for f in r.json().get('features', [])
            if f.get('properties', {}).get('status') == "Actual" and not is_warning_expired(f) and
               f.get('properties', {}).get('event') in ["Tornado Warning", "Severe Thunderstorm Warning"]
        ]
        
        warnings.sort(key=lambda w: (
            0 if w['properties']['event'] == "Tornado Warning" and is_pds_warning(w) else
            1 if w['properties']['event'] == "Tornado Warning" else
            2, 
            w['properties']['sent'] # Added sent time for proper ordering within priority
        ))
        return warnings
    except Exception as e:
        logger.error(f"NWS API call failed: {e}")
        return []

# ========================================================================================
# --- HIGH-LEVEL NAVIGATION LOGIC ---
# ========================================================================================
def navigate_to_warning(warning_feature):
    """Navigate to a warning location and display its information"""
    global last_action_timestamp, current_city
    
    # Hide only the warning box
    try:
        with open('warning_data.json', 'w') as f:
            json.dump({"visible": False}, f)
    except Exception as e:
        logger.error(f"ERROR hiding warning box: {e}")
    
    # Show warning info
    write_infobox_data(warning_feature)
    
    area_desc = warning_feature['properties'].get('areaDesc', "United States")
    
    # Parse the area description to get county and state
    parts = area_desc.split(';')[0].strip().split(',')
    if len(parts) >= 2:
        county_name = parts[0].strip()
        state_abbr = parts[1].strip()
        
        # Add "County" after the county name if not already there
        if "county" not in county_name.lower() and "parish" not in county_name.lower():
            search_term = f"{county_name} County, {state_abbr}"
        else:
            search_term = f"{county_name}, {state_abbr}"
    else:
        search_term = area_desc.split(';')[0].strip()
    
    logger.info(f"ALERT: Processing warning for '{search_term}'")
    
    if force_focus_on_app():
        pyautogui.hotkey(*CONFIG["HOTKEY_NORMAL_RADAR"])
        time.sleep(1)
        
        navigate_by_name(search_term, zoom_out_steps=CONFIG["POST_NAVIGATION_ZOOM_OUTS"])
        last_action_timestamp = time.time()
        
        # --- Get city for current conditions ---
        try:
            # Extract state abbreviation from area description
            state_abbr = parts[1].strip() if len(parts) >= 2 else ""
            
            # Find a city in the same state as the warning
            cities_in_state = [city for city in IDLE_CITY_TOUR_LIST if city.endswith(state_abbr)]
            if cities_in_state:
                current_city = random.choice(cities_in_state)  # Store the chosen city
                weather_data = get_weatherapi_data(current_city)
                write_current_conditions(current_city, weather_data)  # Show current conditions
                logger.info(f"Showing current conditions for {current_city} during warning")
            else:
                logger.warning(f"No cities found in {state_abbr} for current conditions display.")
                current_city = None  # Reset current_city if no city is found
                
        except Exception as e:
            logger.error(f"Error getting current conditions during warning: {e}")
            current_city = None  # Reset current_city in case of error
            
        return True
    
    logger.error("Navigation to warning failed.")
    return False

def navigate_to_city(city_name):
    """Navigate to a city and display its weather information"""
    global last_action_timestamp, current_display, display_start_time, city_start_time
    # Removed: global current_city  (No longer needed here)
    
    hide_all_weather_displays()
    
    weather_data = get_weatherapi_data(city_name)
    
    if force_focus_on_app():
        pyautogui.hotkey(*CONFIG["HOTKEY_COMPOSITE_RADAR"])
        time.sleep(1)
        
        navigate_by_name(city_name, zoom_out_steps=CONFIG["IDLE_CITY_TOUR_ZOOM_OUTS"])
        current_display = CONFIG["DISPLAY_SEQUENCE"][0]
        now = time.time()
        display_start_time = now
        city_start_time = now
        last_action_timestamp = now
        # Removed: current_city = city_name
        
        update_city_display(city_name, weather_data)
        return True
    
    logger.error("Navigation to city failed.")
    return False

def update_city_display(city_name, weather_data):
    """Update the current display type for a city"""
    global current_display
    
    logger.info(f"Showing {current_display} display for {city_name}")

    # Hide ALL displays first
    hide_all_weather_displays()
    
    if current_display == "current":
        write_current_conditions(city_name, weather_data)
    elif current_display == "forecast":
        write_daily_forecast(city_name, weather_data)
    elif current_display == "three_day":
        write_three_day_forecast(city_name, weather_data)
    elif current_display == "astronomy":
        write_astronomy_data(city_name, weather_data)
    elif current_display == "air_quality":
        write_air_quality_data(city_name, weather_data)

def cycle_city_display(city_name):
    """Cycle to the next display type for a city"""
    global current_display, display_start_time
    
    try:
        current_index = CONFIG["DISPLAY_SEQUENCE"].index(current_display)
        current_display = CONFIG["DISPLAY_SEQUENCE"][(current_index + 1) % len(CONFIG["DISPLAY_SEQUENCE"])]
    except ValueError:
        current_display = CONFIG["DISPLAY_SEQUENCE"][0]
    
    logger.info(f"Cycling display to: {current_display}")
    display_start_time = time.time()
    
    update_city_display(city_name, get_weatherapi_data(city_name))

# ========================================================================================
# --- MAIN LOOP & SHUTDOWN ---
# ========================================================================================
def main_loop():
    """Main application loop that manages state and navigation"""
    global active_warnings_cache, last_action_timestamp, warning_display_index
    global cities_shown_in_break, warnings_shown_in_cycle, current_mode
    global current_display, display_start_time, current_city, city_start_time
    
    # Try to load previous state
    if state := load_state():
        globals().update({k: v for k, v in state.items() if k in globals()})
    
    while True:
        try:
            logger.info(f"\n{'='*50}\nMode: {current_mode.upper()}")
            
            # --- Mode Switching Logic ---
            cleanup_old_warnings()
            current_warnings = get_and_sort_active_warnings()
            active_warnings_cache = merge_new_warnings(current_warnings, active_warnings_cache)
            has_warnings = bool(active_warnings_cache)

            # Calculate and write weather activity score
            write_weather_activity_score(active_warnings_cache)

            # Switch to warnings mode if there are any warnings
            if has_warnings and current_mode != "warnings":
                logger.info("--> Warnings are present. Switching to WARNINGS mode.")
                current_mode = "warnings"
                last_action_timestamp = 0
                warning_display_index = 0
                cities_shown_in_break = 0
                warnings_shown_in_cycle = 0
            elif not has_warnings and current_mode != "cities":
                logger.info("--> No warnings are present. Switching to CITIES mode.")
                current_mode = "cities"
                last_action_timestamp = 0
            
            # --- Action Logic ---
            
            # Handle info panel cycling for the current city
            if current_mode == "cities" and current_city:
                if time.time() - display_start_time >= CONFIG["DISPLAY_DURATION"]:
                    cycle_city_display(current_city)
            
            # Handle city or warning navigation
            if current_mode == "cities":
                if last_action_timestamp == 0 or (current_city and time.time() - city_start_time >= CONFIG["CITY_DISPLAY_DURATION"]):
                    # Select a random city and navigate to it
                    next_city = random.choice(IDLE_CITY_TOUR_LIST)
                    logger.info(f"Navigating to city: {next_city}")
                    
                    if navigate_to_city(next_city):
                        cities_shown_in_break += 1
                        logger.info(f"City {cities_shown_in_break} shown")
            
            elif current_mode == "warnings":
                if not active_warnings_cache:
                    current_mode = "cities"
                    continue
                
                # Check for new high-priority warnings (PDS or Tornado)
                new_high_priority = check_for_new_high_priority_warnings()
                
                # If there's a new high-priority warning or it's time to show the next warning
                if new_high_priority or last_action_timestamp == 0 or time.time() - last_action_timestamp >= get_warning_duration(active_warnings_cache[warning_display_index % len(active_warnings_cache)]):
                    # If there's a new high-priority warning, reset the display index to show it
                    if new_high_priority:
                        warning_display_index = 0
                    
                    # Show the next warning
                    warning_index = warning_display_index % len(active_warnings_cache)
                    current_warning = active_warnings_cache[warning_index]
                    warning_type = current_warning['properties']['event']
                    is_pds = is_pds_warning(current_warning)
                    
                    logger.info(f"Showing warning {warning_index + 1}/{len(active_warnings_cache)}: {warning_type}{' (PDS)' if is_pds else ''}")
                    
                    if navigate_to_warning(current_warning):
                        warning_display_index += 1
                        warnings_shown_in_cycle += 1
                        last_action_timestamp = time.time()
            
            save_state()
            time.sleep(CONFIG["POLLING_INTERVAL_SECONDS"])
            
        except Exception as e:
            logger.error(f"Error occurred in cycle: {e}", exc_info=True)
            time.sleep(10)

def shutdown(signal_received=None, frame=None):
    """Handle graceful shutdown"""
    if signal_received:
        logger.info(f"\nReceived exit signal {signal_received}...")
    
    logger.info("Shutting down...")
    hide_all_weather_displays()
    save_state()
    
    sys.exit(0)

def main():
    """Main entry point"""
    try:
        initialize_pyautogui()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, shutdown)
        if hasattr(signal, 'SIGTERM'):  # Windows might not have SIGTERM
            signal.signal(signal.SIGTERM, shutdown)
        
        main_loop()
    except KeyboardInterrupt:
        logger.info("\nShutdown by user.")
    except Exception as e:
        logger.critical(f"A fatal exception occurred: {e}", exc_info=True)
    finally:
        shutdown()

if __name__ == "__main__":
    main()

