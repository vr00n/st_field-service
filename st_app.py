import streamlit as st
import json
from datetime import datetime
import uuid
import pandas as pd

# --- Initial Mock Data ---
# This data will populate the app on first run and will reset on refresh.
def get_initial_data():
    """Returns the initial mock data for the session."""
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
                    "createdAt": datetime(2025, 7, 14, 10, 0, 0).isoformat(),
                    "logs": [
                        {
                            "timestamp": datetime(2025, 7, 14, 10, 0, 0).isoformat(),
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
                    "createdAt": datetime(2025, 7, 13, 14, 30, 0).isoformat(),
                    "logs": [
                         {
                            "timestamp": datetime(2025, 7, 13, 14, 30, 0).isoformat(),
                            "user": "admin",
                            "action": "Activity created."
                        },
                        {
                            "timestamp": datetime(2025, 7, 14, 9, 5, 0).isoformat(),
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

    # --- Export Feature ---
    col1, col2 = st.columns([3, 1])
    with col1:
        if user['role'] == 'admin':
            if st.button("➕ Create New Activity"):
                st.session_state['view'] = 'create_activity'
                st.rerun()
    with col2:
        # Prepare data for download
        export_data = json.dumps(activities, indent=4)
        st.download_button(
            label="📥 Export All Activities",
            data=export_data,
            file_name=f"site_activities_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

    st.divider()

    # Filter activities based on user role
    if user['role'] == 'vendor':
        activities_to_show = [act for act in activities if act.get('properties', {}).get('vendor') == user['username']]
    else:
        activities_to_show = activities

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
    
    # Find the activity in session state
    activity_index = next((i for i, act in enumerate(st.session_state.data['activities']) if act['id'] == activity_id), None)
    if activity_index is None:
        st.error("Activity not found.")
        if st.button("Back to List"):
            st.session_state['view'] = 'list'
            st.rerun()
        return

    activity_data = st.session_state.data['activities'][activity_index]
    props = activity_data.get('properties', {})
    logs = props.get('logs', [])
    user = st.session_state['logged_in_user']
    
    st.title(props.get('title'))
    st.caption(f"Activity ID: `{activity_id}`")

    # Status and Actions
    st.header(f"Status: {props.get('status')}")
    if user['role'] in ['admin', 'vendor']:
        with st.container(border=True):
            st.subheader("Actions")
            cols = st.columns(5)
            
            def update_status(new_status, action_text):
                st.session_state.data['activities'][activity_index]['properties']['status'] = new_status
                st.session_state.data['activities'][activity_index]['properties']['logs'].append({
                    "timestamp": datetime.now().isoformat(), 
                    "user": user['username'], 
                    "action": action_text
                })
                st.rerun()

            with cols[0]:
                if st.button("Start", disabled=props['status'] != 'Pending'):
                    update_status('In Progress', 'Work Started')
            with cols[1]:
                if st.button("Pause", disabled=props['status'] != 'In Progress'):
                    update_status('Paused', 'Work Paused')
            with cols[2]:
                 if st.button("Resume", disabled=props['status'] != 'Paused'):
                    update_status('In Progress', 'Work Resumed')
            with cols[3]:
                if st.button("Complete", disabled=props['status'] not in ['In Progress', 'Paused']):
                    update_status('Completed', 'Work Completed')
            with cols[4]:
                if user['role'] == 'admin':
                    if st.button("Verify", disabled=props['status'] != 'Completed'):
                        update_status('Verified', 'Work Verified')
    
    # Details
    st.divider()
    st.subheader("Details")
    st.write(f"**Vendor:** {props.get('vendor')}")
    st.write(f"**Site:** {props.get('site')}")
    st.write(f"**Category:** {props.get('category')}")
    st.write(f"**Description:** {props.get('description')}")

    # Log
    st.divider()
    st.subheader("Activity Log")
    log_df = pd.DataFrame(logs)
    log_df['timestamp'] = pd.to_datetime(log_df['timestamp'])
    st.dataframe(log_df.sort_values(by="timestamp", ascending=False), use_container_width=True)


    # Add Comment
    with st.form("comment_form"):
        comment = st.text_area("Add a comment or note")
        submitted = st.form_submit_button("Submit Comment")
        if submitted and comment:
            st.session_state.data['activities'][activity_index]['properties']['logs'].append({
                "timestamp": datetime.now().isoformat(), 
                "user": user['username'], 
                "action": f"Comment: {comment}"
            })
            st.rerun()

    if st.button("Back to List"):
        del st.session_state['selected_activity_id']
        st.session_state['view'] = 'list'
        st.rerun()

def create_activity_view():
    """Renders the form to create a new activity."""
    st.title("Create New Site Activity")

    with st.form("new_activity_form"):
        title = st.text_input("Title")
        description = st.text_area("Description")
        vendor_emails = list(st.session_state.data['users'].keys())
        vendor = st.selectbox("Assign Vendor", options=vendor_emails)
        site = st.text_input("Site / Location")
        category = st.selectbox("Category", ["General Maintenance", "Repair EV Charger", "Install Equipment"])
        
        submitted = st.form_submit_button("Create Activity")
        if submitted:
            new_activity_data = {
                "id": str(uuid.uuid4()),
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": []},
                "properties": {
                    "title": title,
                    "description": description,
                    "vendor": vendor,
                    "site": site,
                    "category": category,
                    "status": "Pending",
                    "createdAt": datetime.now().isoformat(),
                    "logs": [{
                        "timestamp": datetime.now().isoformat(),
                        "user": st.session_state['logged_in_user']['username'],
                        "action": "Activity created."
                    }]
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

    # Initialize session state
    if 'data' not in st.session_state:
        st.session_state['data'] = get_initial_data()
    if 'logged_in_user' not in st.session_state:
        st.session_state['logged_in_user'] = None
    if 'view' not in st.session_state:
        st.session_state['view'] = 'list'

    # Sidebar for logout
    if st.session_state.get('logged_in_user'):
        st.sidebar.header("User")
        st.sidebar.write(f"Welcome, **{st.session_state['logged_in_user']['username']}**!")
        st.sidebar.write(f"Role: `{st.session_state['logged_in_user']['role']}`")
        if st.sidebar.button("Logout"):
            st.session_state['logged_in_user'] = None
            st.session_state['view'] = 'list' # Reset view on logout
            st.rerun()
    
    # Main content router
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
