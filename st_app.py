import streamlit as st
import json
from datetime import datetime, timedelta
import uuid
import pandas as pd
from streamlit_js_eval import streamlit_js_eval, get_geolocation
from math import radians, cos, sin, asin, sqrt

# --- Geofence Helper Function ---
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees)
    """
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in kilometers.
    return c * r * 1000 # convert to meters

# --- Initial Mock Data ---
def get_initial_data():
    """Returns the initial mock data for the session."""
    now = datetime.now()
    return {
        "activities": [
            {
                "id": "activity-1",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-73.844, 40.85]},
                "properties": {
                    "title": "Repair Charger #3 at Zerega",
                    "description": "Charger is offline. Error code 501.",
                    "vendor": "vendor@example.com",
                    "site": "Zerega",
                    "category": "Repair EV Charger",
                    "status": "Pending",
                    "createdAt": (now - timedelta(days=1)).isoformat(),
                    "geofence_center": [40.85, -73.844], # lat, lon
                    "geofence_radius": 500, # in meters
                    "logs": [
                        {
                            "timestamp": (now - timedelta(days=1)).isoformat(),
                            "user": "admin",
                            "action": "Activity created."
                        }
                    ]
                }
            },
            {
                "id": "activity-2",
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [-73.778, 40.641]},
                "properties": {
                    "title": "Install Camera on Bus 4501",
                    "description": "Install new 360-degree camera system.",
                    "vendor": "vendor@example.com",
                    "site": "JFK Depot",
                    "category": "Install Equipment",
                    "status": "In Progress",
                    "createdAt": (now - timedelta(days=2)).isoformat(),
                    "geofence_center": [40.641, -73.778], # lat, lon
                    "geofence_radius": 1000, # in meters
                    "logs": [
                         {
                            "timestamp": (now - timedelta(days=2)).isoformat(),
                            "user": "admin",
                            "action": "Activity created."
                        },
                        {
                            "timestamp": (now - timedelta(hours=1)).isoformat(),
                            "user": "vendor@example.com",
                            "action": "Work Started"
                        }
                    ]
                }
            }
        ],
        "users": {
            "vendor@example.com": {"password": "password", "role": "vendor"}
        }
    }

# --- Authentication ---
def check_password(username, password):
    """Validates user credentials against session state data."""
    if username.lower() == 'admin' and password == 'admin':
        return {"username": "admin", "role": "admin"}
    
    user_data = st.session_state.data['users'].get(username)
    if user_data and user_data['password'] == password:
        return {"username": username, "role": user_data['role']}
    return None

def login_page():
    """Renders the login form."""
    st.header("NYCSBUS Site Activity Tracker")
    st.subheader("Login")

    with st.form("login_form"):
        username = st.text_input("Username or Email", help="Use `admin` / `admin` or `vendor@example.com` / `password`")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            user = check_password(username, password)
            if user:
                st.session_state['logged_in_user'] = user
                st.rerun()
            else:
                st.error("Invalid username or password")

# --- UI Components ---
def activity_list_view():
    """Displays the list of all activities and the export button."""
    st.title("Site Activities")
    
    user = st.session_state['logged_in_user']
    activities = st.session_state.data['activities']

    if user['role'] == 'vendor':
        activities_to_show = [act for act in activities if act.get('properties', {}).get('vendor') == user['username']]
    else:
        activities_to_show = activities

    st.subheader("Activity Locations")
    map_data = []
    for activity in activities_to_show:
        coords = activity.get("geometry", {}).get("coordinates")
        if coords and len(coords) == 2:
            map_data.append({"lon": coords[0], "lat": coords[1]})

    if map_data:
        df = pd.DataFrame(map_data)
        st.map(df, zoom=10)
    else:
        st.info("No activities with valid locations to display.")

    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        if user['role'] == 'admin':
            if st.button("➕ Create New Activity"):
                st.session_state['view'] = 'create_activity'
                st.rerun()
    with col2:
        export_data = json.dumps(activities, indent=4)
        st.download_button(
            label="📥 Export All Activities",
            data=export_data,
            file_name=f"site_activities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    st.subheader("Activity List")
    if not activities_to_show:
        st.info("No activities found for your user.")
        return

    for activity in sorted(activities_to_show, key=lambda x: x.get('properties', {}).get('createdAt', ''), reverse=True):
        props = activity.get('properties', {})
        with st.container(border=True):
            col1, col2 = st.columns([3, 1])
            with col1:
                st.subheader(props.get('title', 'No Title'))
            with col2:
                st.info(props.get('status', 'Unknown'))
            st.write(f"**Vendor:** {props.get('vendor', 'N/A')}")
            st.write(f"**Site:** {props.get('site', 'N/A')}")
            if st.button("View Details", key=activity['id']):
                st.session_state['view'] = 'detail'
                st.session_state['selected_activity_id'] = activity['id']
                st.rerun()

def detail_view():
    """Displays the details of a single activity."""
    activity_id = st.session_state['selected_activity_id']
    
    activity_index = next((i for i, act in enumerate(st.session_state.data['activities']) if act['id'] == activity_id), None)
    if activity_index is None:
        st.error("Activity not found."); return

    activity_data = st.session_state.data['activities'][activity_index]
    props = activity_data.get('properties', {})
    logs = props.get('logs', [])
    user = st.session_state['logged_in_user']
    
    st.title(props.get('title'))
    st.caption(f"Activity ID: `{activity_id}`")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Details")
        st.write(f"**Vendor:** {props.get('vendor')}")
        st.write(f"**Site:** {props.get('site')}")
        st.write(f"**Category:** {props.get('category')}")
        st.write(f"**Description:** {props.get('description')}")
        st.write(f"**Geofence Radius:** {props.get('geofence_radius')} meters")

    with col2:
        coords = activity_data.get("geometry", {}).get("coordinates")
        if coords and len(coords) == 2:
            st.subheader("Location")
            st.map(pd.DataFrame([{"lon": coords[0], "lat": coords[1]}]))
        
    st.divider()
    
    st.header(f"Status: {props.get('status')}")
    
    # --- Geofence and Action Logic ---
    # Get location once when the button is clicked
    if st.button("Get Current Location to Enable Actions"):
        location = get_geolocation()
        if location:
            st.session_state['current_location'] = location
            st.success(f"Location captured at {datetime.now().strftime('%H:%M:%S')}. You can now perform actions.")
            st.rerun()
        else:
            st.error("Failed to get location. Please ensure you have granted permission.")

    current_location = st.session_state.get('current_location')
    
    if current_location:
        st.info(f"Using location from {datetime.fromtimestamp(current_location['timestamp']/1000).strftime('%H:%M:%S')}")

    if user['role'] in ['admin', 'vendor']:
        with st.container(border=True):
            st.subheader("Actions")
            
            def perform_action(new_status, action_text):
                location = st.session_state.get('current_location')
                if not location:
                    st.warning("Please get your location before performing an action.")
                    return

                center = props.get('geofence_center')
                radius = props.get('geofence_radius')
                if not center or not radius:
                    st.error("This activity does not have a geofence defined.")
                    return
                
                current_lat = location['coords']['latitude']
                current_lon = location['coords']['longitude']
                distance = haversine(current_lon, current_lat, center[1], center[0])

                if distance > radius:
                    st.error(f"Action denied. You are {int(distance)}m away from the site, which is outside the {radius}m geofence.")
                    return

                st.session_state.data['activities'][activity_index]['properties']['status'] = new_status
                st.session_state.data['activities'][activity_index]['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": action_text})
                st.success(f"Action '{action_text}' successful. You are {int(distance)}m from the site center.")
                del st.session_state['current_location'] # Require new location for next action
                st.rerun()

            cols = st.columns(5)
            with cols[0]:
                st.button("Start", on_click=perform_action, args=('In Progress', 'Work Started'), disabled=props['status'] != 'Pending' or not current_location)
            with cols[1]:
                if st.button("Pause", disabled=props['status'] != 'In Progress'):
                    st.session_state.data['activities'][activity_index]['properties']['status'] = 'Paused'
                    st.session_state.data['activities'][activity_index]['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": "Work Paused"})
                    st.rerun()
            with cols[2]:
                 st.button("Resume", on_click=perform_action, args=('In Progress', 'Work Resumed'), disabled=props['status'] != 'Paused' or not current_location)
            with cols[3]:
                st.button("Complete", on_click=perform_action, args=('Completed', 'Work Completed'), disabled=props['status'] not in ['In Progress', 'Paused'] or not current_location)
            with cols[4]:
                if user['role'] == 'admin':
                    if st.button("Verify", disabled=props['status'] != 'Completed'):
                        st.session_state.data['activities'][activity_index]['properties']['status'] = 'Verified'
                        st.session_state.data['activities'][activity_index]['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": "Work Verified"})
                        st.rerun()
    
    st.divider()
    st.subheader("Activity Log")
    if logs:
        log_df = pd.DataFrame(logs)
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], errors='coerce')
        log_df.dropna(subset=['timestamp'], inplace=True)
        st.dataframe(log_df.sort_values(by="timestamp", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.write("No log entries yet.")

    with st.form("comment_form"):
        comment = st.text_area("Add a comment or note")
        submitted = st.form_submit_button("Submit Comment")
        if submitted and comment:
            st.session_state.data['activities'][activity_index]['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": f"Comment: {comment}"})
            st.rerun()

    if st.button("Back to List"):
        if 'current_location' in st.session_state: del st.session_state['current_location']
        del st.session_state['selected_activity_id']
        st.session_state['view'] = 'list'
        st.rerun()

def create_activity_view():
    """Renders the form to create a new activity."""
    st.title("Create New Site Activity")

    with st.form("new_activity_form"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        
        col1, col2 = st.columns(2)
        with col1:
            vendor_emails = list(st.session_state.data['users'].keys())
            vendor = st.selectbox("Assign Vendor", options=vendor_emails)
            site = st.text_input("Site / Location")
            category = st.selectbox("Category", ["General Maintenance", "Repair EV Charger", "Install Equipment"])
        with col2:
            st.subheader("Geofence")
            lat = st.number_input("Center Latitude", value=40.7128, format="%.6f")
            lon = st.number_input("Center Longitude", value=-74.0060, format="%.6f")
            radius = st.number_input("Radius (meters)", value=500, min_value=50, step=50)
        
        submitted = st.form_submit_button("Create Activity")
        if submitted:
            new_activity_data = {
                "id": str(uuid.uuid4()),
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "title": title,
                    "description": description,
                    "vendor": vendor,
                    "site": site,
                    "category": category,
                    "status": "Pending",
                    "createdAt": datetime.now().isoformat(),
                    "geofence_center": [lat, lon],
                    "geofence_radius": radius,
                    "logs": [{"timestamp": datetime.now().isoformat(), "user": st.session_state['logged_in_user']['username'], "action": "Activity created."}]
                }
            }
            st.session_state.data['activities'].append(new_activity_data)
            st.success("Activity created successfully!")
            st.session_state['view'] = 'list'
            st.rerun()

    if st.button("Cancel"):
        st.session_state['view'] = 'list'
        st.rerun()

# --- Main App Router ---
def main():
    """Main application router."""
    st.set_page_config(layout="wide")

    if 'data' not in st.session_state:
        st.session_state['data'] = get_initial_data()
    if 'logged_in_user' not in st.session_state:
        st.session_state['logged_in_user'] = None
    if 'view' not in st.session_state:
        st.session_state['view'] = 'list'
    if 'current_location' not in st.session_state:
        st.session_state['current_location'] = None

    if st.session_state.get('logged_in_user'):
        st.sidebar.header("User")
        st.sidebar.write(f"Welcome, **{st.session_state['logged_in_user']['username']}**!")
        st.sidebar.write(f"Role: `{st.session_state['logged_in_user']['role']}`")
        if st.sidebar.button("Logout"):
            st.session_state['logged_in_user'] = None
            st.session_state['view'] = 'list'
            st.rerun()
    
    if not st.session_state.get('logged_in_user'):
        login_page()
    else:
        if st.session_state['view'] == 'list':
            activity_list_view()
        elif st.session_state['view'] == 'detail':
            detail_view()
        elif st.session_state['view'] == 'create_activity':
            create_activity_view()

if __name__ == "__main__":
    main()
