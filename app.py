import streamlit as st
import pandas as pd
import numpy as np
import io
import base64
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
import re

st.set_page_config(page_title="Employee Attendance Analyzer", layout="wide")

# Define constants for standard working hours
STANDARD_HOURS = {
    'Monday': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Tuesday': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Wednesday': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Thursday': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Friday': {'start': '08:30', 'end': '14:30', 'duration': 6.0},
    'Saturday': {'start': None, 'end': None, 'duration': 0},
    'Sunday': {'start': None, 'end': None, 'duration': 0}
}

# Function to parse time strings
def parse_time(time_str):
    if pd.isna(time_str) or time_str == '':
        return None
    try:
        return datetime.strptime(time_str.strip(), '%H:%M')
    except:
        return None

# Function to calculate duration between times
def calculate_duration(entry_time, exit_time):
    if entry_time is None or exit_time is None:
        return 0
    
    duration = exit_time - entry_time
    hours = duration.total_seconds() / 3600
    return round(hours, 2)

# Function to extract employee data from the CSV content
def process_attendance_data(file_content):
    # Read the CSV content
    lines = file_content.strip().split('\n')
    
    # Extract date range from the header
    date_range_line = lines[1] if len(lines) > 1 else ""
    date_match = re.search(r'from\s+(\d+\s+\w+\s+\d+)\s+to\s+(\d+\s+\w+\s+\d+)', date_range_line)
    date_range = f"{date_match.group(1)} - {date_match.group(2)}" if date_match else "N/A"
    
    data = []
    current_employee = None
    department = None
    badge_id = None
    days_data = []
    weekdays = None
    dates = None
    
    for line in lines:
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Check if this is an employee header line
        employee_match = re.search(r',([^,]+\s+[^,]+\s+\d+),([^,]*),', line)
        if employee_match:
            # Process previous employee data if exists
            if current_employee and days_data:
                for day_idx, (day, date, time_range) in enumerate(zip(weekdays, dates, days_data)):
                    if time_range and '-' in time_range:
                        entry_time_str, exit_time_str = time_range.split(' - ')
                        entry_time = parse_time(entry_time_str)
                        exit_time = parse_time(exit_time_str)
                        
                        if entry_time and exit_time:
                            duration = calculate_duration(entry_time, exit_time)
                            standard_duration = STANDARD_HOURS.get(day, {'duration': 0})['duration']
                            
                            data.append({
                                'Employee': current_employee,
                                'Department': department,
                                'Badge ID': badge_id,
                                'Day': day,
                                'Date': date,
                                'Entry Time': entry_time_str,
                                'Exit Time': exit_time_str,
                                'Duration (Hours)': duration,
                                'Standard Hours': standard_duration,
                                'Difference': duration - standard_duration
                            })
            
            # Set new employee data
            current_employee = employee_match.group(1).strip()
            department = employee_match.group(2).strip()
            
            # Extract badge ID
            badge_match = re.search(r'(\d{3}[A-Z0-9]+)$', line)
            badge_id = badge_match.group(1) if badge_match else "N/A"
            
            days_data = []
            continue
        
        # Check if this is a weekday header line
        if line.startswith('Mon,Tue,Wed,Thu,Fri,Sat,Sun'):
            weekdays = line.split(',')
            continue
        
        # Check if this is a date line
        date_line_match = re.match(r'\d+\s+\w+,\d+\s+\w+,\d+\s+\w+,\d+\s+\w+,\d+\s+\w+,', line)
        if date_line_match:
            dates = []
            for date_str in line.split(','):
                date_str = date_str.strip()
                if date_str and re.match(r'\d+\s+\w+', date_str):
                    dates.append(date_str)
                else:
                    dates.append(None)
            continue
        
        # Check if this is a time range line
        time_range_match = re.match(r'(\d{1,2}:\d{2}\s+-\s+\d{1,2}:\d{2})?,(\d{1,2}:\d{2}\s+-\s+\d{1,2}:\d{2})?,', line)
        if time_range_match:
            days_data = line.split(',')
            days_data = [d.strip() if d.strip() else None for d in days_data]
            
            # Process current employee data
            if current_employee and days_data:
                for day_idx, (day, date, time_range) in enumerate(zip(weekdays, dates, days_data)):
                    if time_range and '-' in time_range:
                        entry_time_str, exit_time_str = time_range.split(' - ')
                        entry_time = parse_time(entry_time_str)
                        exit_time = parse_time(exit_time_str)
                        
                        if entry_time and exit_time and date:
                            duration = calculate_duration(entry_time, exit_time)
                            standard_duration = STANDARD_HOURS.get(day, {'duration': 0})['duration']
                            
                            data.append({
                                'Employee': current_employee,
                                'Department': department,
                                'Badge ID': badge_id,
                                'Day': day,
                                'Date': date,
                                'Entry Time': entry_time_str,
                                'Exit Time': exit_time_str,
                                'Duration (Hours)': duration,
                                'Standard Hours': standard_duration,
                                'Difference': duration - standard_duration
                            })
            
            days_data = []
            continue
    
    # Create DataFrame
    df = pd.DataFrame(data)
    
    # Calculate weekly totals for each employee
    weekly_data = []
    
    for employee, emp_df in df.groupby('Employee'):
        total_hours = emp_df['Duration (Hours)'].sum()
        total_standard_hours = emp_df['Standard Hours'].sum()
        
        weekly_data.append({
            'Employee': employee,
            'Department': emp_df['Department'].iloc[0],
            'Total Hours': total_hours,
            'Standard Hours': total_standard_hours,
            'Difference': total_hours - total_standard_hours
        })
    
    weekly_df = pd.DataFrame(weekly_data)
    
    # Extract month from dates for monthly calculations
    if not df.empty and 'Date' in df.columns:
        df['Month'] = df['Date'].apply(lambda x: x.split(' ')[1] if x and ' ' in x else None)
        
        # Calculate monthly totals
        monthly_data = []
        for (employee, month), month_df in df.groupby(['Employee', 'Month']):
            if month:  # Skip if month is None
                total_hours = month_df['Duration (Hours)'].sum()
                total_standard_hours = month_df['Standard Hours'].sum()
                
                monthly_data.append({
                    'Employee': employee,
                    'Department': month_df['Department'].iloc[0],
                    'Month': month,
                    'Total Hours': total_hours,
                    'Standard Hours': total_standard_hours,
                    'Difference': total_hours - total_standard_hours
                })
        
        monthly_df = pd.DataFrame(monthly_data)
    else:
        monthly_df = pd.DataFrame()
    
    return df, weekly_df, monthly_df, date_range

# Function to create download link
def get_download_link(df, filename, link_text):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}" class="download-link">{link_text}</a>'
    return href

# Function to create Excel download link
def get_excel_download_link(df, filename, link_text):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}" class="download-link">{link_text}</a>'
    return href

# Define custom CSS
st.markdown("""
<style>
    .main {
        padding: 2rem;
    }
    .download-link {
        background-color: #4CAF50;
        color: white;
        padding: 10px 15px;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 16px;
        margin: 4px 2px;
        cursor: pointer;
        border-radius: 5px;
    }
    .highlight-positive {
        color: green;
        font-weight: bold;
    }
    .highlight-negative {
        color: red;
        font-weight: bold;
    }
    .section-title {
        font-size: 24px;
        font-weight: bold;
        margin-top: 20px;
        margin-bottom: 10px;
    }
    .subsection-title {
        font-size: 18px;
        font-weight: bold;
        margin-top: 15px;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# App header
st.title("📊 Employee Attendance Analyzer")
st.markdown("Upload your attendance data and get comprehensive analysis")

# File upload section
st.markdown("### Upload Attendance Data")
uploaded_file = st.file_uploader("Choose a file", type=['xlsx', 'csv'])

if uploaded_file is not None:
    try:
        # Process the uploaded file
        if uploaded_file.name.endswith('.xlsx'):
            # For Excel files
            xls = pd.ExcelFile(uploaded_file)
            sheet_name = st.selectbox("Select Sheet", xls.sheet_names)
            df_raw = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            file_content = df_raw.to_csv(index=False)
        else:
            # For CSV files
            file_content = uploaded_file.getvalue().decode('utf-8')
        
        # Process the data
        daily_df, weekly_df, monthly_df, date_range = process_attendance_data(file_content)
        
        if not daily_df.empty:
            st.success(f"✅ Data successfully processed! Date range: {date_range}")
            
            # Create tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Daily Analysis", "📅 Weekly Summary", "📆 Monthly Overview", "📊 Visualizations"])
            
            with tab1:
                st.markdown("### Daily Attendance Records")
                
                # Allow filtering by employee
                if 'Employee' in daily_df.columns:
                    employees = sorted(daily_df['Employee'].unique())
                    selected_employee = st.selectbox("Select Employee", ['All'] + list(employees))
                    
                    if selected_employee != 'All':
                        filtered_df = daily_df[daily_df['Employee'] == selected_employee]
                    else:
                        filtered_df = daily_df
                else:
                    filtered_df = daily_df
                
                # Format the DataFrame for display
                display_df = filtered_df.copy()
                
                # Highlight differences
                def highlight_difference(val):
                    if val > 0:
                        return 'background-color: #c6efce; color: #006100'  # Green for positive
                    elif val < 0:
                        return 'background-color: #ffc7ce; color: #9c0006'  # Red for negative
                    return ''
                
                styled_df = display_df.style.applymap(highlight_difference, subset=['Difference'])
                
                st.dataframe(styled_df, use_container_width=True)
                
                # Download links
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(get_download_link(filtered_df, "daily_attendance.csv", "📥 Download Daily Data (CSV)"), unsafe_allow_html=True)
                with col2:
                    st.markdown(get_excel_download_link(filtered_df, "daily_attendance.xlsx", "📥 Download Daily Data (Excel)"), unsafe_allow_html=True)
            
            with tab2:
                st.markdown("### Weekly Attendance Summary")
                
                # Format the DataFrame for display
                styled_weekly_df = weekly_df.style.applymap(
                    highlight_difference, 
                    subset=['Difference']
                )
                
                st.dataframe(styled_weekly_df, use_container_width=True)
                
                # Download links
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(get_download_link(weekly_df, "weekly_attendance.csv", "📥 Download Weekly Data (CSV)"), unsafe_allow_html=True)
                with col2:
                    st.markdown(get_excel_download_link(weekly_df, "weekly_attendance.xlsx", "📥 Download Weekly Data (Excel)"), unsafe_allow_html=True)
            
            with tab3:
                st.markdown("### Monthly Attendance Overview")
                
                if not monthly_df.empty:
                    # Format the DataFrame for display
                    styled_monthly_df = monthly_df.style.applymap(
                        highlight_difference, 
                        subset=['Difference']
                    )
                    
                    st.dataframe(styled_monthly_df, use_container_width=True)
                    
                    # Download links
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(get_download_link(monthly_df, "monthly_attendance.csv", "📥 Download Monthly Data (CSV)"), unsafe_allow_html=True)
                    with col2:
                        st.markdown(get_excel_download_link(monthly_df, "monthly_attendance.xlsx", "📥 Download Monthly Data (Excel)"), unsafe_allow_html=True)
                else:
                    st.info("Monthly data could not be calculated. Please check if the date format is correct.")
            
            with tab4:
                st.markdown("### Attendance Visualizations")
                
                # Select visualization type
                viz_type = st.selectbox(
                    "Select Visualization", 
                    ["Daily Hours by Employee", "Weekly Comparison", "Arrival Time Distribution", "Departure Time Distribution"]
                )
                
                if viz_type == "Daily Hours by Employee":
                    # Group by employee and date
                    pivot_df = daily_df.pivot_table(
                        index='Date', 
                        columns='Employee', 
                        values='Duration (Hours)',
                        aggfunc='sum'
                    ).fillna(0)
                    
                    # Create a bar chart
                    fig = px.bar(
                        pivot_df, 
                        barmode='group',
                        title="Daily Hours Worked by Employee",
                        labels={"value": "Hours", "Date": "Date", "variable": "Employee"},
                        height=600
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                elif viz_type == "Weekly Comparison":
                    # Create comparison chart
                    weekly_comp_fig = px.bar(
                        weekly_df,
                        x='Employee',
                        y=['Total Hours', 'Standard Hours'],
                        barmode='group',
                        title="Weekly Hours: Actual vs. Standard",
                        labels={"value": "Hours", "variable": "Category"},
                        height=500
                    )
                    
                    st.plotly_chart(weekly_comp_fig, use_container_width=True)
                    
                    # Create difference chart
                    weekly_diff_fig = px.bar(
                        weekly_df,
                        x='Employee',
                        y='Difference',
                        title="Hours Difference from Standard Schedule",
                        labels={"Difference": "Hours +/-"},
                        color='Difference',
                        color_continuous_scale=["red", "yellow", "green"],
                        height=500
                    )
                    
                    weekly_diff_fig.add_hline(y=0, line_width=2, line_dash="dash", line_color="gray")
                    
                    st.plotly_chart(weekly_diff_fig, use_container_width=True)
                    
                elif viz_type == "Arrival Time Distribution":
                    # Convert time strings to datetime for visualization
                    arrival_df = daily_df.copy()
                    arrival_df['Entry Hour'] = arrival_df['Entry Time'].apply(
                        lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60 if isinstance(x, str) and ':' in x else None
                    )
                    
                    # Filter out None values
                    arrival_df = arrival_df.dropna(subset=['Entry Hour'])
                    
                    # Create arrival time histogram
                    arrival_fig = px.histogram(
                        arrival_df,
                        x='Entry Hour',
                        color='Employee',
                        nbins=24,
                        range_x=[6, 12],  # Focus on 6 AM to 12 PM
                        title="Arrival Time Distribution",
                        labels={"Entry Hour": "Hour of Day", "count": "Frequency"},
                        height=500
                    )
                    
                    # Add reference line for standard start time (8:30 AM)
                    arrival_fig.add_vline(x=8.5, line_width=2, line_dash="dash", line_color="red", annotation_text="Standard Start (8:30)")
                    
                    st.plotly_chart(arrival_fig, use_container_width=True)
                    
                elif viz_type == "Departure Time Distribution":
                    # Convert time strings to datetime for visualization
                    departure_df = daily_df.copy()
                    departure_df['Exit Hour'] = departure_df['Exit Time'].apply(
                        lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60 if isinstance(x, str) and ':' in x else None
                    )
                    
                    # Filter out None values
                    departure_df = departure_df.dropna(subset=['Exit Hour'])
                    
                    # Create departure time histogram
                    departure_fig = px.histogram(
                        departure_df,
                        x='Exit Hour',
                        color='Employee',
                        nbins=24,
                        range_x=[14, 20],  # Focus on 2 PM to 8 PM
                        title="Departure Time Distribution",
                        labels={"Exit Hour": "Hour of Day", "count": "Frequency"},
                        height=500
                    )
                    
                    # Add reference lines for standard end times
                    departure_fig.add_vline(x=17, line_width=2, line_dash="dash", line_color="red", annotation_text="Mon-Thu End (17:00)")
                    departure_fig.add_vline(x=14.5, line_width=2, line_dash="dash", line_color="orange", annotation_text="Fri End (14:30)")
                    
                    st.plotly_chart(departure_fig, use_container_width=True)
                    
        else:
            st.error("❌ Could not process the data. Please check the file format.")
            
    except Exception as e:
        st.error(f"❌ Error processing file: {str(e)}")
        st.exception(e)
else:
    # Show sample data and instructions
    st.info("📌 Please upload an Excel (.xlsx) or CSV file containing employee attendance data.")
    
    st.markdown("""
    ### Expected Data Format
    
    The application expects attendance data in a format similar to the following:
    
    ```
    Report by first and last card presenting per calendar day
    from 24 March 2025 to 27 March 2025
    
    EMPLOYEE_NAME EMPLOYEE_ID,DEPARTMENT,,,,ID_NUMBER
    Mon,Tue,Wed,Thu,Fri,Sat,Sun
    24 March,25 March,26 March,27 March,28 March,,
    08:26 - 17:26,09:00 - 17:10,08:58 - 17:15,08:37 - 17:11,,,
    ```
    
    ### Features
    
    - **Automatic Data Processing**: Extract employee attendance data and calculate working hours
    - **Standard Schedule Comparison**: Compare actual hours with standard working schedule
    - **Comprehensive Analysis**: View daily, weekly, and monthly attendance reports
    - **Visual Insights**: Visualize attendance patterns with interactive charts
    - **Export Functionality**: Download processed data in CSV or Excel formats
    """)

# Footer
st.markdown("---")
st.markdown("### 📋 Standard Working Hours")
st.markdown("""
- **Monday-Thursday**: 08:30 - 17:00 (8.5 hours)
- **Friday**: 08:30 - 14:30 (6 hours)
- **Saturday-Sunday**: Days off
""")
