import streamlit as st
import json
import requests
import base64
from datetime import datetime, timedelta
import uuid
import pandas as pd
import pydeck as pdk
from streamlit_geolocation import streamlit_geolocation
from math import radians, cos, sin, asin, sqrt

# --- GitHub Configuration ---
# These should be set as Streamlit secrets.
try:
    GITHUB_TOKEN = st.secrets["GITHUB_TOKEN"]
    REPO_OWNER = st.secrets["REPO_OWNER"]
    REPO_NAME = st.secrets["REPO_NAME"]
    PATH_IN_REPO = st.secrets["PATH_IN_REPO"]
except (KeyError, AttributeError):
    st.warning("GitHub credentials not found in Streamlit secrets. Using placeholders. Please configure secrets for deployment.")
    GITHUB_TOKEN = "YOUR_GITHUB_PERSONAL_ACCESS_TOKEN"
    REPO_OWNER = "YOUR_GITHUB_USERNAME"
    REPO_NAME = "YOUR_GITHUB_REPO_NAME"
    PATH_IN_REPO = "activities"


# --- GitHub API Helper Functions ---
BASE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github.v3+json"
}

@st.cache_data(ttl=60)
def get_repo_contents(path):
    """Fetches the contents of a directory in the GitHub repo."""
    url = f"{BASE_URL}{path}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 404:
            return [] # Directory doesn't exist yet, return empty list
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to connect to GitHub: {e}")
        return None

@st.cache_data(ttl=60)
def get_file_content(filepath):
    """Fetches and decodes the content of a single file from GitHub."""
    url = f"{BASE_URL}{filepath}"
    try:
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 404:
            return None, None
        response.raise_for_status()
        data = response.json()
        content = base64.b64decode(data['content']).decode('utf-8')
        return json.loads(content), data['sha']
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to read file from GitHub: {e}")
        return None, None


def create_or_update_file(filepath, content, sha=None, message="Update file"):
    """Creates a new file or updates an existing one in the GitHub repo."""
    url = f"{BASE_URL}{filepath}"
    encoded_content = base64.b64encode(json.dumps(content, indent=4).encode('utf-8')).decode('utf-8')
    
    data = {
        "message": f"{message} at {datetime.now().isoformat()}",
        "content": encoded_content,
        "committer": {"name": "Streamlit App", "email": "app@streamlit.io"}
    }
    if sha:
        data["sha"] = sha

    try:
        response = requests.put(url, headers=HEADERS, data=json.dumps(data))
        response.raise_for_status()
        st.cache_data.clear() # Clear cache after writing
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Failed to write to GitHub: {e}")
        return None

# --- Geofence Helper ---
def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371 # Radius of earth in km
    return c * r * 1000 # in meters

# --- Authentication & User Management ---
@st.cache_data(ttl=300)
def get_users():
    content, _ = get_file_content("users.json")
    return content if content else {"vendor@example.com": {"password": "password", "role": "vendor"}}

def check_password(username, password):
    if username.lower() == 'admin' and password == 'admin':
        return {"username": "admin", "role": "admin"}
    
    users_data = get_users()
    user_data = users_data.get(username)
    if user_data and user_data['password'] == password:
        return {"username": username, "role": user_data['role']}
    return None

def login_page():
    st.header("NYCSBUS Site Activity Tracker")
    st.subheader("Login")
    with st.form("login_form"):
        username = st.text_input("Username or Email", help="Use `admin` / `admin` or a vendor account.")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            user = check_password(username, password)
            if user:
                st.session_state['logged_in_user'] = user
                st.rerun()
            else:
                st.error("Invalid username or password")

# --- UI Views ---
def activity_list_view():
    st.title("Site Activities")
    user = st.session_state['logged_in_user']
    
    contents = get_repo_contents(PATH_IN_REPO)
    if contents is None: 
        st.error("Could not fetch activity list from GitHub. Check token permissions and repository path.")
        return

    all_activities = []
    for item in contents:
        if item['name'].endswith('.geojson'):
            content, _ = get_file_content(item['path'])
            if content:
                content['filename'] = item['name']
                all_activities.append(content)

    if user['role'] == 'vendor':
        activities_to_show = [act for act in all_activities if act.get('properties', {}).get('vendor') == user['username']]
    else:
        activities_to_show = all_activities

    st.subheader("Activity Locations")
    map_data = []
    for activity in activities_to_show:
        coords = activity.get("geometry", {}).get("coordinates")
        if coords and len(coords) == 2:
            map_data.append({
                "lon": coords[0],
                "lat": coords[1],
                "title": activity["properties"].get("title", "N/A"),
                "status": activity["properties"].get("status", "N/A")
            })

    if map_data:
        df = pd.DataFrame(map_data)
        
        view_state = pdk.ViewState(
            latitude=df["lat"].mean(),
            longitude=df["lon"].mean(),
            zoom=10,
            pitch=45,
        )

        scatterplot_layer = pdk.Layer(
            "ScatterplotLayer",
            data=df,
            get_position='[lon, lat]',
            get_fill_color='[200, 30, 0, 160]',
            get_radius=100,
            pickable=True,
        )

        text_layer = pdk.Layer(
            "TextLayer",
            data=df,
            get_position='[lon, lat]',
            get_text='"📍"',
            get_size=24,
            get_color='[0, 0, 0]',
            get_angle=0,
        )

        tooltip = {
            "html": "<b>{title}</b><br/>Status: {status}",
            "style": {"backgroundColor": "steelblue", "color": "white"},
        }
        
        deck = pdk.Deck(
            map_style=None,
            initial_view_state=view_state,
            layers=[scatterplot_layer, text_layer],
            tooltip=tooltip
        )
        st.pydeck_chart(deck)
    else:
        st.info("No activities with valid locations to display on the map.")

    st.divider()
    col1, col2 = st.columns([3, 1])
    with col1:
        if user['role'] == 'admin':
            if st.button("➕ Create New Activity"):
                st.session_state['view'] = 'create_activity'
                st.rerun()
    with col2:
        export_data = json.dumps(all_activities, indent=4)
        st.download_button("📥 Export All Activities", export_data, f"activities_{datetime.now().strftime('%Y%m%d')}.json", "application/json")

    st.subheader("Activity List")
    
    if not activities_to_show:
        st.info("No activities found.")
        return

    table_data = []
    for activity in sorted(activities_to_show, key=lambda x: x.get('properties', {}).get('createdAt', ''), reverse=True):
        props = activity.get('properties', {})
        table_data.append({
            "Status": props.get('status', 'Unknown'),
            "Title": props.get('title', 'N/A'),
            "Vendor": props.get('vendor', 'N/A'),
            "Site": props.get('site', 'N/A'),
            "filename": activity.get('filename') 
        })
    
    if table_data:
        df_table = pd.DataFrame(table_data)
        
        selection = st.dataframe(
            df_table,
            on_select="rerun",
            selection_mode="single-row",
            hide_index=True,
            column_order=("Status", "Title", "Vendor", "Site"),
            column_config={"filename": None}
        )

        if selection.selection['rows']:
            selected_row_index = selection.selection['rows'][0]
            selected_filename = df_table.iloc[selected_row_index]['filename']
            
            st.session_state['view'] = 'detail'
            st.session_state['selected_activity_filename'] = selected_filename
            st.rerun()

def detail_view(activity_filename, read_only=False):
    filepath = f"{PATH_IN_REPO}/{activity_filename}"
    activity_data, sha = get_file_content(filepath)
    if not activity_data:
        st.error("Activity not found or could not be loaded."); return

    props = activity_data.get('properties', {})
    logs = props.get('logs', [])
    user = st.session_state.get('logged_in_user', {"username": "Public", "role": "public"})

    st.title(props.get('title'))
    if not read_only: st.caption(f"Activity File: `{activity_filename}`")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Details")
        st.write(f"**Vendor:** {props.get('vendor')}")
        st.write(f"**Site:** {props.get('site')}")
        st.write(f"**Description:** {props.get('description')}")
    with col2:
        coords = activity_data.get("geometry", {}).get("coordinates")
        if coords: st.map(pd.DataFrame([{"lon": coords[0], "lat": coords[1]}]))

    st.divider()
    st.header(f"Status: {props.get('status')}")

    location = None
    if not read_only and user['role'] in ['admin', 'vendor']:
        st.subheader("Location & Actions")
        # This is now the single source for location data on this page.
        location = streamlit_geolocation()

        if props.get('status') == 'In Progress':
            st.html("<meta http-equiv='refresh' content='30'>")
            if location and location.get('latitude') is not None:
                last_log_time = datetime.fromisoformat(logs[-1]['timestamp']) if logs else datetime.min
                if (datetime.now() - last_log_time).total_seconds() > 25:
                    activity_data['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": "System", "action": "Periodic location check."})
                    if 'location_trail' not in activity_data['properties']:
                        activity_data['properties']['location_trail'] = []
                    activity_data['properties']['location_trail'].append({"timestamp": datetime.now().isoformat(), "coordinates": [location['longitude'], location['latitude']]})
                    create_or_update_file(filepath, activity_data, sha, "Periodic location update")
                    st.rerun()
        
        def perform_action(new_status, action_text):
            if not location or location.get('latitude') is None:
                st.warning("Please share location to perform actions."); return
            
            center = props.get('geofence_center')
            radius = props.get('geofence_radius')
            if not center or not radius:
                st.error("Activity has no geofence defined."); return

            distance = haversine(location['longitude'], location['latitude'], center[1], center[0])
            if distance > radius:
                st.error(f"Action denied. You are {int(distance)}m away, outside the {radius}m geofence."); return
            
            activity_data['properties']['status'] = new_status
            activity_data['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": action_text})
            if 'location_trail' not in activity_data['properties']:
                activity_data['properties']['location_trail'] = []
            activity_data['properties']['location_trail'].append({"timestamp": datetime.now().isoformat(), "coordinates": [location['longitude'], location['latitude']]})

            create_or_update_file(filepath, activity_data, sha, f"{action_text} by {user['username']}")
            st.success(f"Action '{action_text}' successful.")
            st.rerun()

        cols = st.columns(5)
        with cols[0]: st.button("Start", on_click=perform_action, args=('In Progress', 'Work Started'), disabled=(props['status'] != 'Pending' or not location))
        with cols[1]: 
            if st.button("Pause", disabled=props['status'] != 'In Progress'):
                activity_data['properties']['status'] = 'Paused'
                activity_data['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": "Work Paused"})
                create_or_update_file(filepath, activity_data, sha, f"Paused by {user['username']}")
                st.rerun()
        with cols[2]: st.button("Resume", on_click=perform_action, args=('In Progress', 'Work Resumed'), disabled=(props['status'] != 'Paused' or not location))
        with cols[3]: st.button("Complete", on_click=perform_action, args=('Completed', 'Work Completed'), disabled=(props['status'] not in ['In Progress', 'Paused'] or not location))
        with cols[4]:
            if user['role'] == 'admin':
                if st.button("Verify", disabled=props['status'] != 'Completed'):
                    activity_data['properties']['status'] = 'Verified'
                    activity_data['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": "Work Verified"})
                    create_or_update_file(filepath, activity_data, sha, f"Verified by {user['username']}")
                    st.rerun()

    st.divider()
    st.subheader("Activity Log")
    if logs:
        log_df = pd.DataFrame(logs)
        log_df['timestamp'] = pd.to_datetime(log_df['timestamp'], format='ISO8601', errors='coerce')
        log_df.dropna(subset=['timestamp'], inplace=True)
        st.dataframe(log_df.sort_values(by="timestamp", ascending=False), use_container_width=True, hide_index=True)

    if not read_only:
        with st.form("comment_form"):
            comment = st.text_area("Add a comment")
            if st.form_submit_button("Submit Comment") and comment:
                activity_data['properties']['logs'].append({"timestamp": datetime.now().isoformat(), "user": user['username'], "action": f"Comment: {comment}"})
                create_or_update_file(filepath, activity_data, sha, f"Comment by {user['username']}")
                st.rerun()
        if st.button("Back to List"):
            st.session_state['view'] = 'list'
            st.rerun()

def create_activity_view():
    st.title("Create New Site Activity")
    with st.form("new_activity_form"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        vendor = st.selectbox("Assign Vendor", options=list(get_users().keys()))
        site = st.text_input("Site / Location")
        lat = st.number_input("Center Latitude", value=40.7128, format="%.6f")
        lon = st.number_input("Center Longitude", value=-74.0060, format="%.6f")
        radius = st.number_input("Geofence Radius (meters)", value=500, min_value=50)
        
        if st.form_submit_button("Create Activity"):
            filename = f"activity_{datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}.geojson"
            filepath = f"{PATH_IN_REPO}/{filename}"
            
            new_activity_data = {
                "id": str(uuid.uuid4()), "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [lon, lat]},
                "properties": {
                    "title": title, "description": description, "vendor": vendor,
                    "site": site, "status": "Pending", "createdAt": datetime.now().isoformat(),
                    "geofence_center": [lat, lon], "geofence_radius": radius,
                    "logs": [{"timestamp": datetime.now().isoformat(), "user": st.session_state['logged_in_user']['username'], "action": "Activity created."}],
                    "location_trail": []
                }
            }
            create_or_update_file(filepath, new_activity_data, message=f"Create {title}")
            st.success("Activity created!"); st.session_state['view'] = 'list'; st.rerun()
    if st.button("Cancel"): st.session_state['view'] = 'list'; st.rerun()

# --- Main App Router ---
def main():
    st.set_page_config(layout="wide")
    
    query_params = st.query_params
    if 'activity_id' in query_params:
        detail_view(query_params['activity_id'], read_only=True)
        return

    if 'logged_in_user' not in st.session_state: st.session_state['logged_in_user'] = None
    if 'view' not in st.session_state: st.session_state['view'] = 'list'

    if st.session_state.get('logged_in_user'):
        with st.sidebar:
            st.header("User")
            st.write(f"Welcome, **{st.session_state['logged_in_user']['username']}**!")
            st.write(f"Role: `{st.session_state['logged_in_user']['role']}`")
            st.divider()
            
            st.header("Navigation")
            if st.button("🏠 Home / Activities List"):
                st.session_state['view'] = 'list'
                if 'selected_activity_filename' in st.session_state:
                    del st.session_state['selected_activity_filename']
                st.rerun()

            if st.button("❔ Quick Start Guide"):
                st.session_state.show_guide = True

            st.divider()
            if st.button("Logout"):
                st.session_state['logged_in_user'] = None
                st.session_state['view'] = 'list'
                st.rerun()
    
    # --- Quick Start Guide Dialog ---
    if st.session_state.get('show_guide', False):
        @st.dialog("Quick Start Guide")
        def show_guide():
            st.markdown("""
            ### Welcome to the NYCSBUS Site Activity Tracker!

            This guide will help you get started with the app's main features.

            #### **1. Logging In**
            - **Admin:** Use `admin` / `admin` to log in with full permissions.
            - **Vendor:** Use the credentials provided by an admin (e.g., `vendor@example.com` / `password`).

            #### **2. Main Dashboard (Home)**
            - **Map View:** See all site activities at a glance. Icons are clustered together on zoom.
            - **Activity List:** A filterable list of all activities. Click "View Details" to see more.
            - **Create Activity (Admin Only):** Click the "Create New Activity" button to start a new work order.
            - **Export Data:** Click "Export All Activities" to download a JSON file of all current data.

            #### **3. Activity Details**
            - **Actions:** As a vendor or admin, you can update the status of a job.
            - **Geofence:** To **Start**, **Resume**, or **Complete** a job, you must be within the defined geofence radius.
              1. Click the **"Share location"** button. Your browser will ask for permission.
              2. Once your location is shared, the action buttons will become active.
              3. Click the desired action (e.g., "Start").
            - **In Progress Tracking:** While a job is "In Progress", the app will automatically log your location every 30 seconds.
            - **Comments:** Add comments or notes to the activity log at any time.

            #### **4. Shareable Links**
            - To share a read-only view of an activity, simply copy the URL from your browser when you are on the detail page and send it to anyone. They will not need to log in to view it.
            """)
            if st.button("Close"):
                st.session_state.show_guide = False
                st.rerun()
        show_guide()


    # Main content router
    if not st.session_state.get('logged_in_user'):
        login_page()
    else:
        view = st.session_state.get('view', 'list')
        if view == 'list':
            activity_list_view()
        elif view == 'detail':
            detail_view(st.session_state['selected_activity_filename'])
        elif view == 'create_activity':
            create_activity_view()

if __name__ == "__main__":
    main()
