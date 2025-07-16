# NYCSBUS Site Activity Tracker

This is a Streamlit web application designed to help facilities and operations managers at NYCSBUS initiate, track, and verify activities performed by external vendors on company assets across multiple sites.

The application uses a GitHub repository as a file-based backend, storing each site activity as a version-controlled GeoJSON file. This provides a transparent and easily manageable data store without the need for a traditional database.

## Key Features

-   **Role-Based Access:**
    
    -   **Admin:** Full access to create, view, and manage all activities.
        
    -   **Vendor:** Can only view and update activities specifically assigned to them.
        
-   **Geofence Enforcement:**
    
    -   Activities can be assigned a geofence (a location and a radius).
        
    -   Vendors must be within the geofence to start, resume, or complete work, verifying their on-site presence.
        
-   **Location Tracking:**
    
    -   When a job is "In Progress," the vendor's location is logged periodically, creating a breadcrumb trail.
        
    -   Location is also logged on key actions like starting, pausing, and completing work.
        
-   **Interactive Map View:**
    
    -   A dashboard map shows the locations of all activities with clustered icons.
        
    -   Detailed views show the specific location and geofence of an individual activity.
        
-   **Shareable Links:**
    
    -   Generate read-only links for any activity that can be shared with non-users.
        
-   **Data Export:**
    
    -   Admins can download a complete JSON file of all activity data at any time.
        

## Setup and Installation

To run this application, you will need Python 3.8+ and `pip` installed.

### 1. Create Project Files

Create a folder for your project and add the following two files:

**`requirements.txt`:**

```
streamlit
pandas
requests
streamlit-geolocation
pydeck

```

**`st_app.py`:**

-   Copy the entire Python code from the main application file into `st_app.py`.
    

### 2. Install Dependencies

Open a terminal in your project folder and run the following command:

```
pip install -r requirements.txt

```

### 3. GitHub Repository Setup

This application uses a GitHub repository as its database.

1.  **Create a new GitHub Repository:** It is recommended to make this a **private** repository.
    
2.  **Create a `users.json` file (Optional):** In the root of your new repository, you can create a `users.json` file to manage vendor accounts. If you skip this, the app will use a default mock user.
    
    ```
    {
      "vendor@example.com": {
        "password": "password",
        "role": "vendor"
      },
      "another.vendor@company.com": {
        "password": "securepassword123",
        "role": "vendor"
      }
    }
    
    ```
    

### 4. Create a GitHub Personal Access Token (PAT)

1.  Go to your GitHub Settings > Developer settings > Personal access tokens > **Fine-grained tokens**.
    
2.  Click **"Generate new token"**.
    
3.  Give the token a name (e.g., "Streamlit App Token") and set an expiration date.
    
4.  Under **Repository access**, select **"Only select repositories"** and choose the repository you just created.
    
5.  Under **Repository permissions**, find **"Contents"** and set its access level to **"Read and write"**.
    
6.  Click **"Generate token"** and copy the token. You will not be able to see it again.
    

### 5. Configure Streamlit Secrets

For deployment on Streamlit Community Cloud, you must set the following secrets in your app's settings. For local development, you can create a file named `.streamlit/secrets.toml`.

**`.streamlit/secrets.toml`:**

```
# GitHub Personal Access Token (Fine-grained)
GITHUB_TOKEN = "ghp_YourGitHubTokenHere"

# Your GitHub username or organization name
REPO_OWNER = "YourGitHubUsername"

# The name of the repository you created
REPO_NAME = "your-repo-name"

# The folder inside the repo to store activity files
PATH_IN_REPO = "activities"

```

### 6. Running the Application

Open a terminal in your project folder and run:

```
streamlit run st_app.py

```

## How to Use the App

-   **Admin Login:**
    
    -   Username: `admin`
        
    -   Password: `admin`
        
-   **Vendor Login:**
    
    -   Use the credentials you defined in your `users.json` file (or the default `vendor@example.com` / `password`).
        
-   **Creating an Activity (Admin):**
    
    1.  Click "Create New Activity".
        
    2.  Fill in the details, including assigning a vendor and setting a geofence.
        
-   **Performing Work (Vendor):**
    
    1.  Log in and select an activity assigned to you.
        
    2.  Click the "Share location" button to enable action buttons.
        
    3.  Click "Start" to begin work. You must be within the geofence.
        
    4.  While the job is "In Progress", the app will automatically track your location.
        
    5.  Use the "Pause", "Resume", and "Complete" buttons as needed.
