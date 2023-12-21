import os
import folium
import geopandas as gpd
import rasterio
import numpy as np
from flask import Flask, render_template, request
from rasterio.crs import CRS
from shapely.geometry import Point, box, shape
from pyproj import transform
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import ArcGIS
from pyproj import Transformer
from branca.element import Template, MacroElement
from folium import Map, LayerControl, Marker, GeoJson
from folium.plugins import MousePosition
from jinja2 import Template

app = Flask(__name__)
#base_dir = r"C:/Users/Guill/OneDrive - UCL/University/Master2/LBIRE2234/Variables"
base_dir = r"/srv/data/Variables"
#base_dir = r"/export/homes/students/gujadot/website/Variables"


shp_filepaths = {
    "Floods_25": os.path.join(base_dir,r"Risques_naturels/RISQUE_INONDATION_SHAPE_31370/RI__EMP_Q025DEB.shp"),
    "Floods_2021": os.path.join(base_dir, r"Risques_naturels/Juillet2021_dissolve_boundaries/test_DissolveBoundaries.shp"),
    "SEVESO": os.path.join(base_dir, r"Risques_tech/SEVESO.gpkg"),
    "RADON": os.path.join(base_dir, r"Risques_tech/RADON/StatParCommune2022.shp"),
    "Inorganic_Pollution": os.path.join(base_dir, r"Sols_exterieurs/Sol_pol_organiques_95centile/Sol_pol_inorganiques_95centile.shp"),
    #"Organic_Pollution": os.path.join(base_dir, r"Sols_exterieurs/Sol_pol_organiques_95centile/Sol_pol_organiques_95centile.shp"),
    "Pollution_sonore_route": os.path.join(base_dir, "Pollution_sonore/BRUIT_MROAD_2017_SHAPE_31370/BRUIT_MROAD_2017__LDEN.shp"),
    "Pollution_sonore_ferroviaire": os.path.join(base_dir, r"Pollution_sonore/BRUIT_MRAIL_2017_SHAPE_31370/BRUIT_MRAIL_2017__LDEN.shp"),
    "Pollution_sonore_airport": os.path.join(base_dir, "Pollution_sonore/BRUIT_AEROPORT_SHAPE_31370/BRUIT_AEROPORT_PEB.shp"),
    #"axes_routier_agglo": r"C:/Users/Guill/OneDrive - UCL/University/Master2/LBIRE2234/Variables/Pollution_sonore/Bruit des axes routiers dans les grandes agglomérations wallonnes - Rapportage 2012 - Série/BRUIT_AGGLO_ROAD_2012__LDEN.shp",
    #"axes_ferro_agglo": r"C:/Users/Guill/OneDrive - UCL/University/Master2/LBIRE2234/Variables/Pollution_sonore/Bruit des axes ferroviaires dans les grandes agglomérations wallonnes - Rapportage 2012 - Série/BRUIT_AGGLO_RAIL_2012__LDEN.shp",
    #"bruits_industrie_agglo": r"C:/Users/Guill/OneDrive - UCL/University/Master2/LBIRE2234/Variables/Pollution_sonore/Bruit de l'industrie dans les grandes agglomérations wallonnes - Rapportage 2012 – Série/BRUIT_AGGLO_IND_2012__LDEN.shp"
}

tif_filepaths = {
    'bc': os.path.join(base_dir, r"Pollution_atm/2022/bc_anmean_2022_atmostreet_v64.tif"),
    'no2': os.path.join(base_dir, r"Pollution_atm/2022/no2_anmean_2022_atmostreet_v64.tif"),
    'pm10': os.path.join(base_dir, r"Pollution_atm/2022/pm10_anmean_2022_atmostreet_v64.tif"),
    'pm2.5': os.path.join(base_dir, r"Pollution_atm/2022/pm25_anmean_2022_atmostreet_v64.tif")
}

# Load shapefile layers
def load_shp(filepath):
    """
    Load a shapefile and convert its coordinate reference system to EPSG:4326.

    Parameters:
    filepath (str): File path to the shapefile.

    Returns:
    geopandas.GeoDataFrame: A GeoDataFrame with the loaded shapefile data.
    """
    gdf = gpd.read_file(filepath)
    gdf = gdf.to_crs(epsg=4326)
    return gdf

shp_layers = {}
for name, filepath in shp_filepaths.items():
    try:
        shp_layers[name] = load_shp(filepath)
    except Exception as e:
        print(f"Error loading {name} from {filepath}: {e}")

# Sample value from raster
def sample_tif_value(tif_filepath, longitude, latitude):
    try:
        with rasterio.open(tif_filepath) as src:
            # Create a transformer to convert from WGS 84 to the raster's CRS
            transformer = Transformer.from_crs(4326, src.crs, always_xy=True)
            x, y = transformer.transform(longitude, latitude)
            # Sample the raster at the transformed coordinates
            sampled_values = src.sample([(x, y)])
            sample = next(sampled_values)  # Get the next (and hopefully only) sample
            # Debugging: print the sample to see what we got
            print(f"Sample: {sample}")
            # If it's a single float value, return it directly
            if isinstance(sample, float):
                return f"Sampled Value: {sample}"
            # Otherwise, attempt to extract the value from the array or list
            value = sample[0]
            
            if value == src.nodata or np.isnan(value):  # Check if the value is NoData or NaN
                return "No data available at the specified coordinates."
            else:
                return f"Sampled Value: {value}"

    except Exception as e:
        return f"An error occurred while sampling the raster file: {e}"


# check_risk function 
def check_shapefile_risk(layer, longitude, latitude, buffer_size=10): # lower buffer_size reduces the number of features checked during spatial query
    point = Point(longitude, latitude)
    bbox = point.buffer(buffer_size).bounds
    possible_matches_index = list(layer.sindex.intersection(bbox))
    if not possible_matches_index:
        return gpd.GeoDataFrame()  # Empty DataFrame if no intersection
    possible_matches = layer.iloc[possible_matches_index]
    precise_matches = possible_matches[possible_matches.contains(point)]
    return precise_matches


# Create Folium map
def create_map(latitude, longitude, shp_layers, zoom_start=15):
    """
    Create a map with specified layers and a marked point.
    
    Parameters:
    latitude (float): Latitude of the location to mark.
    longitude (float): Longitude of the location to mark.
    shp_layers (dict): Dictionary of GeoDataFrames representing various layers.
    zoom_start (int): Initial zoom level of the map.        
    
    Returns:
    str: HTML representation of the map.
    """
    m = folium.Map(location=[latitude, longitude], zoom_start=zoom_start)

    # Add WMS Tile
    # Add WMS Tile Layer for Floods 2021
    folium.raster_layers.WmsTileLayer(
        url='http://maps.elie.ucl.ac.be/cgi-bin/mapserv72?map=/maps_server/prism/mapfiles/floods2021.map',
        name='Floods_2021',
        fmt='image/png',
        layers='floods2021',
        transparent=True
    ).add_to(m)
    # Add WMS Tile Layer for Floods 25
    folium.raster_layers.WmsTileLayer(
        url='http://maps.elie.ucl.ac.be/cgi-bin/mapserv72?map=/maps_server/prism/mapfiles/floods25.map',
        name='Floods_25',
        fmt='image/png',
        layers='floods25',
        transparent=True
    ).add_to(m)

    # GeoJSON layers
    excluded_layers = ['Organic_Pollution', 'Inorganic_Pollution', 'RADON', 'Floods_2021','Floods_25', "Pollution_sonore_route", "Pollution_sonore_ferroviaire"]  # List of layers to exclude
    # Create a dictionnary with the color for each .shp layer
    layer_colors = {
    "Floods_25": "blue",
    "Floods_2021": "darkblue", 
    "SEVESO": "green",
    "Pollution_sonore_airport": "gray",
    #"Organic_Pollution": "purple",
    #"Inorganic_Pollution": "orange",
    #"axes_routier_agglo": "darkred",
    #"axes_ferro_agglo": "orange",
    #"bruits_industrie_agglo": "cadetblue"
    }
    for name, layer in shp_layers.items():
        if name not in excluded_layers:  # Only add the layer if it's not in the excluded list
            color = layer_colors.get(name, "gray")  # Default to gray if the layer is not in the dictionary
            style_function = lambda x, color=color: {"fillColor": color, "color": color, "weight": 1.5, "fillOpacity": 0.5}
            # Apply the style function when creating the GeoJson object
            folium.GeoJson(layer, name=name, style_function=style_function).add_to(m)

    folium.Marker([latitude, longitude], popup=f'Lat: {latitude}, Lon: {longitude}').add_to(m)
    LayerControl().add_to(m)

    # Create a legend
    legend_html = '''
    <div style="position: fixed; 
                bottom: 50px; left: 50px; width: auto; height: auto; 
                border:2px solid grey; z-index:9999; font-size:14px;
                background-color:white; padding:5px; overflow: auto;">
                <h4>Légende</h4>'''

    legend_labels = {
    "Floods_25": "Inondations retour 25 ans",
    "Floods_2021": "Inondations de 2021",
    "SEVESO": "SEVESO",
    "Pollution_sonore_airport": "Bruit aéroports",
    }

    for layer_name, label in legend_labels.items():
        color = layer_colors.get(layer_name, "gray")  # Get the color for the layer
        legend_html += f'<div><span style="background:{color}; width: 12px; height: 12px; display: inline-block; margin-right: 5px;"></span>{label}</div>'
    
    legend_html += '</div>'

    m.get_root().html.add_child(folium.Element(legend_html))

    # for web flask interface
    return m._repr_html_()  # Return the HTML representation of the map



# Main function
def analyze_location(latitude, longitude, shp_filepaths, tif_filepaths):
    analysis_results = []
    WHO_LIMITS = {'no2': 25, 'pm10': 15, 'pm2.5': 5}  # Define WHO limits for pollutants

    # Floods analysis
    floods_layers = {'Floods_25': 'inondations avec une période de retour de 25 ans', 'Floods_2021': 'inondations de juillet 2021'}
    floods_intersects = []
    for layer_name, description in floods_layers.items():
        if layer_name in shp_layers:
            precise_matches = check_shapefile_risk(shp_layers[layer_name], longitude, latitude)
            if not precise_matches.empty:
                floods_intersects.append(description)

    if floods_intersects:
        floods_color = 'red'
        floods_message = 'La localisation est dans une zone à risques pour les ' + ' et les '.join(floods_intersects)
    else:
        floods_color = 'green'
        floods_message = 'La localisation n\'est pas dans une zone à risque d\'inondations.'

    analysis_results.append({
        'type': 'floods',
        'color': floods_color,
        'message': floods_message,
        'details': floods_intersects
    })

    # SEVESOs
    seveso_layer = shp_layers.get("SEVESO")
    if seveso_layer is not None:
        seveso_matches = check_shapefile_risk(seveso_layer, longitude, latitude)
        if not seveso_matches.empty:
            seveso_color = 'red'
            seveso_name = seveso_matches.iloc[0]['SOC_NOM']  # Extract the SOC_NOM value
            seveso_message = f"La localisation se trouve dans la zone SEVESO de l'entreprise: {seveso_name}."
        else:
            seveso_color = 'green'
            seveso_message = "La localisation n'est pas dans une zone SEVESO."

        analysis_results.append({
            'type': 'seveso',
            'color': seveso_color,
            'message': seveso_message
        })

    # RADON analysis
    radon_layer = shp_layers.get("RADON")
    if radon_layer is not None:
        radon_match = check_shapefile_risk(radon_layer, longitude, latitude)
        if not radon_match.empty:
            radon_class = radon_match.iloc[0]['ClassRad_1']
            radon_color_map = {
                'Class 0': 'green',
                'Class 1a': 'lightgreen',
                'Class 1b': 'yellow',
                'Class 2a': 'orange',
                'Class 2b': 'red'
            }
            radon_color = radon_color_map.get(radon_class, 'grey')
            radon_detail = {
                'Class 0': '<=1% >300 Bq/m3',
                'Class 1a': '1-2% > 300 Bq/m3',
                'Class 1b': '2-5% > 300 Bq/m3',
                'Class 2a': '5-10% > 300 Bq/m3',
                'Class 2b': '>10% > 300 Bq/m3'
            }.get(radon_class, 'No data')
            analysis_results.append({
                'type': 'radon',
                'color': radon_color,
                'message': f"Risque radon : {radon_class} - {radon_detail}"
            })
        else:
            analysis_results.append({
                'type': 'radon',
                'message': 'Pas de données disponibles pour le radon à cette localisation.'
            })

    # Inorganic Pollutants analysis
    inorganic_pollutants = {
        'As': 30,   # Arsenic threshold in mg/kg
        'Cd': 10.85,  # Cadmium threshold
        'Mn': 585,   # Manganese threshold
        'Mo': 13,   # Molybdenum threshold
        'Pb': 200,   # Lead (Plomb) threshold
        'Zn': 259   # Zinc threshold
    }

    inorganic_pollutants_exceeds = []
    pollutants_layer = shp_layers.get("Inorganic_Pollution")

    if pollutants_layer is not None:
        precise_matches = check_shapefile_risk(pollutants_layer, longitude, latitude)
        if not precise_matches.empty:
            for pollutant, threshold in inorganic_pollutants.items():
                value_str = precise_matches.iloc[0].get(pollutant, '0')
                try:
                    value = float(value_str)  # Convert to float for comparison
                    if value > threshold:
                        inorganic_pollutants_exceeds.append(f"{pollutant}: {value} mg/kg")
                except ValueError:
                    # if value_str cannot be converted to float
                    print(f"Error converting {pollutant} value to float: {value_str}")

    if inorganic_pollutants_exceeds:
        inorganic_color = 'red'
        inorganic_message = 'Seuil dépassé pour : ' + ', '.join(inorganic_pollutants_exceeds)
    else:
        inorganic_color = 'green'
        inorganic_message = 'Aucun seuil de polluants inorganiques dépassé'

    analysis_results.append({
        'type': 'inorganic_pollutants',
        'color': inorganic_color,
        'message': inorganic_message,
        'details': inorganic_pollutants_exceeds
    })

    # Pollution Sonore Route analysis
    # Determine the color based on the classe
    sonor_color = {
        'moins de 55': 'lightgreen',
        'de 55 à 59': 'green',
        'de 60 à 64': 'yellow',
        'de 65 à 69': 'orange',
        'de 70 à 74': 'red',
        'plus de 75': 'purple',
    }
    pollution_sonore_route_layer = shp_layers.get("Pollution_sonore_route")
    if pollution_sonore_route_layer is not None:
        sonore_route_match = check_shapefile_risk(pollution_sonore_route_layer, longitude, latitude)
        if not sonore_route_match.empty:
            classe_route = sonore_route_match.iloc[0]['CLASSE']
            sonore_route_color = sonor_color.get(classe_route, 'grey')
            sonore_route_message = f"Niveau de bruit routier en dB : {classe_route}"
            analysis_results.append({
                'type': 'pollution_sonore_route',
                'color': sonore_route_color,
                'message': sonore_route_message
            })
        else:
            analysis_results.append({
                'type': 'pollution_sonore_route',
                'color': 'green',
                'message': 'Il n\'a y pas de pollution sonore liée aux grands axes routiers pour cette localisation'
            })

    # Pollution Sonore Ferroviaire analysis
    pollution_sonore_ferroviaire_layer = shp_layers.get("Pollution_sonore_ferroviaire")
    if pollution_sonore_ferroviaire_layer is not None:
        sonore_ferroviaire_match = check_shapefile_risk(pollution_sonore_ferroviaire_layer, longitude, latitude)
        if not sonore_ferroviaire_match.empty:
            classe_ferroviaire = sonore_ferroviaire_match.iloc[0]['CLASSE']
            sonore_ferroviaire_color = sonor_color.get(classe_ferroviaire, 'grey')
            sonore_ferroviaire_message = f"Niveau de bruit ferroviaire en dB : {classe_ferroviaire}"
            analysis_results.append({
                'type': 'pollution_sonore_ferroviaire',
                'color': sonore_ferroviaire_color,
                'message': sonore_ferroviaire_message
            })
        else:
            analysis_results.append({
                'type': 'pollution_sonore_ferroviaire',
                'color': 'green',
                'message': 'Il n\'a y pas de pollution sonore liée aux grand axes ferroviaires pour cette localisation'
            })

    # Pollution Sonore airport analysis
    pollution_sonore_airport_layer = shp_layers.get("Pollution_sonore_airport")
    airport_color = {
        "Zone A'": 'red',
        "Zone B'": 'orange',
        "Zone C'": 'yellow',
        "Zone D'": 'green',
    }
    if pollution_sonore_airport_layer is not None:
        sonore_airport_match = check_shapefile_risk(pollution_sonore_airport_layer, longitude, latitude)
        if not sonore_airport_match.empty:
            classe_airport = sonore_airport_match.iloc[0]['ZONAGE']
            sonore_airport_color = airport_color.get(classe_airport, 'grey')
            airport_detail = {
                "Zone A'": '70 dB',
                "Zone B'": 'entre 70 et 65 dB',
                "Zone C'": 'entre 65 et 60 dB',
                "Zone D'": 'entre 60 et 55 dB',
            }.get(classe_airport, 'No data')
            sonore_airport_message = f"Niveau de bruit airport en dB : {classe_airport} - {airport_detail}"
            analysis_results.append({
                'type': 'pollution_sonore_airport',
                'color': sonore_airport_color,
                'message': sonore_airport_message
            })
        else:
            analysis_results.append({
                'type': 'pollution_sonore_airport',
                'color': 'green',
                'message': 'Il n\'a y pas de pollution sonore liée aux aéroports pour cette localisation'
            })

    # atmospheric pollutants
    pollution_exceeds = 0
    pollution_details = []
    for name, filepath in tif_filepaths.items():
        message = sample_tif_value(filepath, longitude, latitude)
        try:
            # Extract the numeric value from the message string
            value = float(message.split(": ")[-1])
            # Round the value to 3 decimal places
            value = round(value, 3)
            exceeds_limit = value > WHO_LIMITS.get(name, float('inf'))
            if exceeds_limit:
                pollution_exceeds += 1
            pollution_details.append({
                'pollutant': name.upper(),
                'value': value,
                'limit_exceeded': exceeds_limit
            })
        except (IndexError, ValueError):
            # Handle error
            pollution_details.append({
                'pollutant': name.upper(),
                'message': message
            })
    # Determine the color based on the number of limits exceeded
    if pollution_exceeds == 0:
        color = "green"
    elif pollution_exceeds == 1:
        color = "yellow"
    elif pollution_exceeds == 2 or pollution_exceeds == 3:
        color = "orange"
    else:
        color = "red"
    # Add a summary result for pollution
    analysis_results.append({
        'type': 'pollution_summary',
        'color': color,
        'details': pollution_details
    })
        
    # Create map with shapefile layers
    create_map(latitude, longitude, shp_layers)
    return analysis_results


def geocode_address_arcgis(address):
    geolocator = ArcGIS(user_agent="geoapiExercises", timeout=10)
    try:
        location = geolocator.geocode(address)
        if location:
            return location.latitude, location.longitude
        else:
            return None, None
    except Exception as e:
        print(f"An error occurred: {e}")
        return None, None


@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Main route that handles GET and POST requests.
    Renders the map and performs geospatial analysis based on user input.
    """
    map_html = ""
    analysis_results = []
    error_message = None

    if request.method == 'POST':
        location_type = request.form.get('location_type')  # Using .get() to avoid KeyError
        latitude, longitude = None, None  # Initialize to None
    
        # Geocode based on the input type
        if location_type == 'coordinates':
            try:
                latitude = float(request.form.get('latitude'))
                longitude = float(request.form.get('longitude'))
            except ValueError:
                error_message = "Invalid coordinates entered."
        elif location_type == 'address':
            address = request.form.get('address')
            latitude, longitude = geocode_address_arcgis(address)
            if latitude is None or longitude is None:
                error_message = "Unable to geocode the provided address."

        # Perform analysis if coordinates are available
        if latitude is not None and longitude is not None:
            analysis_results = analyze_location(latitude, longitude, shp_filepaths, tif_filepaths)
            map_html = create_map(latitude, longitude, shp_layers)

    # Render template with available data
    return render_template('index.html', map_html=map_html, analysis_results=analysis_results, error_message=error_message)

if __name__ == "__main__":
    app.run() #debug=True)



