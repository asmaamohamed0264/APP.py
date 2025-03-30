import streamlit as st
import pandas as pd
import numpy as np
import io
import base64
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
import re
import calendar
import os

# Configure page
st.set_page_config(page_title="Analizor Prezență Angajați", layout="wide")

# Initialize session state variables
if 'historical_data' not in st.session_state:
    st.session_state.historical_data = pd.DataFrame()

# Ensure data directory exists
if not os.path.exists('data'):
    os.makedirs('data', exist_ok=True)

# Romanian holidays by year
ROMANIAN_HOLIDAYS = {
    2024: [
        "2024-01-01", "2024-01-02", "2024-01-24", 
        "2024-05-01", "2024-05-03", "2024-05-05", "2024-05-06",
        "2024-06-23", "2024-06-24", "2024-08-15",
        "2024-11-30", "2024-12-01", "2024-12-25", "2024-12-26"
    ],
    2025: [
        "2025-01-01", "2025-01-02", "2025-01-24",
        "2025-04-18", "2025-04-20", "2025-04-21",
        "2025-05-01", "2025-06-08", "2025-06-09",
        "2025-08-15", "2025-11-30", "2025-12-01",
        "2025-12-25", "2025-12-26"
    ]
}

# Function to get holidays for a specific year
def get_holidays_for_year(year):
    if year in ROMANIAN_HOLIDAYS:
        return ROMANIAN_HOLIDAYS[year]
    
    # If we don't have data for the requested year, extrapolate from 2025
    extrapolated_holidays = []
    for holiday in ROMANIAN_HOLIDAYS[2025]:
        parts = holiday.split('-')
        if len(parts) == 3:
            new_date = f"{year}-{parts[1]}-{parts[2]}"
            extrapolated_holidays.append(new_date)
    return extrapolated_holidays

# Function to check if a date is a holiday
def is_holiday(check_date):
    year = check_date.year
    date_str = check_date.strftime("%Y-%m-%d")
    return date_str in get_holidays_for_year(year)

# Function to calculate working days in a month
def calculate_working_days(year, month):
    num_days = calendar.monthrange(year, month)[1]
    working_days = 0
    
    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        if current_date.weekday() < 5:  # 0-4 are Monday-Friday
            if not is_holiday(current_date):
                working_days += 1
    
    return working_days

# Function to calculate standard monthly hours
def calculate_standard_monthly_hours(year, month):
    num_days = calendar.monthrange(year, month)[1]
    total_hours = 0
    
    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        weekday = current_date.weekday()
        
        # Skip weekends and holidays
        if weekday >= 5 or is_holiday(current_date):
            continue
        
        # Add hours based on day of week
        if weekday == 4:  # Friday
            total_hours += 6.0
        else:  # Monday to Thursday
            total_hours += 8.5
    
    return total_hours

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

# Function to convert date string to datetime
def convert_date_string(date_str, year=None):
    if pd.isna(date_str) or not date_str:
        return None
    
    # Clean up the date string
    date_str = date_str.strip()
    
    # Try different date formats
    formats = ['%d %B %Y', '%d %B', '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d']
    
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            if '%Y' not in fmt and year:
                # If year is not in the format, set it
                dt = dt.replace(year=year)
            return dt
        except ValueError:
            continue
    
    return None

# Function to load historical data
def load_historical_data():
    try:
        if os.path.exists('data/attendance_history.csv'):
            return pd.read_csv('data/attendance_history.csv')
        return pd.DataFrame()
    except Exception as e:
        st.warning(f"Nu s-a putut încărca istoricul: {e}")
        return pd.DataFrame()

# Function to save data to historical record
def save_to_historical_data(new_data):
    try:
        if new_data.empty:
            return pd.DataFrame()
            
        # Load existing data first
        historical_df = load_historical_data()
        
        if historical_df.empty:
            historical_df = new_data
        else:
            # Remove duplicates based on Employee + Date
            if 'Angajat' in new_data.columns and 'Data' in new_data.columns:
                for _, row in new_data.iterrows():
                    mask = (historical_df['Angajat'] == row['Angajat']) & (historical_df['Data'] == row['Data'])
                    historical_df = historical_df[~mask]
                
                # Add new data
                historical_df = pd.concat([historical_df, new_data], ignore_index=True)
        
        # Save locally
        historical_df.to_csv('data/attendance_history.csv', index=False)
        
        st.session_state.historical_data = historical_df
        return historical_df
    except Exception as e:
        st.warning(f"Nu s-a putut salva istoricul: {e}")
        return pd.DataFrame()

# Function to create download link
def get_download_link(df, filename, link_text):
    try:
        csv = df.to_csv(index=False)
        b64 = base64.b64encode(csv.encode()).decode()
        href = f'<a href="data:file/csv;base64,{b64}" download="{filename}" class="download-link">{link_text}</a>'
        return href
    except Exception as e:
        st.warning(f"Nu s-a putut crea link-ul de descărcare: {e}")
        return ""

# Function to create Excel download link
def get_excel_download_link(df, filename, link_text):
    try:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Sheet1')
        excel_data = output.getvalue()
        b64 = base64.b64encode(excel_data).decode()
        href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}" class="download-link">{link_text}</a>'
        return href
    except Exception as e:
        st.warning(f"Nu s-a putut crea link-ul de descărcare Excel: {e}")
        return ""

# Helper function to process employee data entries (removes duplication)
def process_employee_entry(current_employee, department, badge_id, weekdays, dates, time_range, report_year):
    data_entries = []
    
    for day_idx, (day, date_str, time_range_val) in enumerate(zip(weekdays, dates, time_range)):
        if date_str:  # Check if date exists
            date_obj = convert_date_string(date_str, report_year)
            weekday_name = day
            
            if time_range_val and '-' in time_range_val:
                entry_time_str, exit_time_str = time_range_val.split(' - ')
                entry_time = parse_time(entry_time_str)
                exit_time = parse_time(exit_time_str)
                
                if entry_time and exit_time:
                    duration = calculate_duration(entry_time, exit_time)
                    standard_duration = 0
                    
                    # Calculate standard hours based on weekday
                    if weekday_name in ['Mon', 'Tue', 'Wed', 'Thu']:
                        standard_duration = 8.5
                    elif weekday_name == 'Fri':
                        standard_duration = 6.0
                    
                    # Check if it's a holiday
                    if date_obj and is_holiday(date_obj):
                        standard_duration = 0
                    
                    data_entries.append({
                        'Angajat': current_employee,
                        'Departament': department,
                        'ID Legitimație': badge_id,
                        'Zi': weekday_name,
                        'Data': date_str,
                        'Data_Obiect': date_obj,
                        'Ora Sosire': entry_time_str,
                        'Ora Plecare': exit_time_str,
                        'Durata (Ore)': duration,
                        'Ore Standard': standard_duration,
                        'Diferență': duration - standard_duration
                    })
            else:
                # Date exists but no time range (absent day)
                standard_duration = 0
                if weekday_name in ['Mon', 'Tue', 'Wed', 'Thu']:
                    standard_duration = 8.5
                elif weekday_name == 'Fri':
                    standard_duration = 6.0
                
                # Check if it's a holiday
                if date_obj and is_holiday(date_obj):
                    standard_duration = 0
                
                data_entries.append({
                    'Angajat': current_employee,
                    'Departament': department,
                    'ID Legitimație': badge_id,
                    'Zi': weekday_name,
                    'Data': date_str,
                    'Data_Obiect': date_obj,
                    'Ora Sosire': '',
                    'Ora Plecare': '',
                    'Durata (Ore)': 0,
                    'Ore Standard': standard_duration,
                    'Diferență': -standard_duration
                })
    
    return data_entries

# Function to process attendance data
def process_attendance_data(file_content):
    try:
        # Read CSV content
        lines = file_content.strip().split('\n')
        
        # Extract date range from header
        date_range_line = lines[1] if len(lines) > 1 else ""
        date_match = re.search(r'from\s+(\d+\s+\w+\s+\d+)\s+to\s+(\d+\s+\w+\s+\d+)', date_range_line)
        date_range = f"{date_match.group(1)} - {date_match.group(2)}" if date_match else "N/A"
        
        # Extract start and end dates
        start_date_str = date_match.group(1) if date_match else None
        end_date_str = date_match.group(2) if date_match else None
        
        start_date = convert_date_string(start_date_str)
        end_date = convert_date_string(end_date_str)
        report_year = start_date.year if start_date else datetime.now().year
        
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
                # Process previous employee data if it exists
                if current_employee and days_data:
                    data_entries = process_employee_entry(current_employee, department, badge_id, weekdays, dates, days_data, report_year)
                    data.extend(data_entries)
                
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
                    data_entries = process_employee_entry(current_employee, department, badge_id, weekdays, dates, days_data, report_year)
                    data.extend(data_entries)
                
                days_data = []
                continue
        
        # Create DataFrame
        df = pd.DataFrame(data)
        
        # Add missing working days for each employee
        if not df.empty and start_date and end_date:
            all_employees = df['Angajat'].unique()
            
            for employee in all_employees:
                # Get department and badge ID for this employee
                emp_df = df[df['Angajat'] == employee]
                if not emp_df.empty:
                    department = emp_df['Departament'].iloc[0] if 'Departament' in emp_df.columns else ""
                    badge_id = emp_df['ID Legitimație'].iloc[0]
                    
                    current_date = start_date
                    while current_date <= end_date:
                        weekday_num = current_date.weekday()
                        weekday_name = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday_num]
                        date_str = current_date.strftime("%d %B")
                        
                        # Skip weekends
                        if weekday_num < 5:
                            # Check if this day already exists for this employee
                            date_exists = False
                            for _, row in emp_df.iterrows():
                                row_date = row.get('Data_Obiect')
                                if row_date and row_date.date() == current_date.date():
                                    date_exists = True
                                    break
                            
                            if not date_exists:
                                # Calculate standard hours
                                standard_duration = 0
                                if weekday_name in ['Mon', 'Tue', 'Wed', 'Thu']:
                                    standard_duration = 8.5
                                elif weekday_name == 'Fri':
                                    standard_duration = 6.0
                                
                                # Check if it's a holiday
                                if is_holiday(current_date):
                                    standard_duration = 0
                                
                                # Add the missing day
                                new_row = {
                                    'Angajat': employee,
                                    'Departament': department,
                                    'ID Legitimație': badge_id,
                                    'Zi': weekday_name,
                                    'Data': date_str,
                                    'Data_Obiect': current_date,
                                    'Ora Sosire': '',
                                    'Ora Plecare': '',
                                    'Durata (Ore)': 0,
                                    'Ore Standard': standard_duration,
                                    'Diferență': -standard_duration
                                }
                                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                        
                        current_date += timedelta(days=1)
        
        # Extract year, month info and add them as columns
        if not df.empty and 'Data_Obiect' in df.columns:
            df['An'] = df['Data_Obiect'].apply(lambda x: x.year if x else None)
            df['Luna'] = df['Data_Obiect'].apply(lambda x: x.month if x else None)
            df['Luna_Nume'] = df['Data_Obiect'].apply(lambda x: x.strftime('%B') if x else None)
            df['Săptămână'] = df['Data_Obiect'].apply(lambda x: x.isocalendar()[1] if x else None)
        
        # Sort DataFrame by employee and date
        if 'Data_Obiect' in df.columns and not df.empty:
            df = df.sort_values(['Angajat', 'Data_Obiect']).reset_index(drop=True)
        
        # Calculate weekly totals for each employee
        weekly_data = []
        
        if not df.empty and 'Săptămână' in df.columns:
            for (employee, year, week), week_df in df.groupby(['Angajat', 'An', 'Săptămână']):
                if pd.isna(year) or pd.isna(week):
                    continue
                    
                total_hours = week_df['Durata (Ore)'].sum()
                total_standard_hours = week_df['Ore Standard'].sum()
                
                # Get department
                department = week_df['Departament'].iloc[0] if 'Departament' in week_df.columns else ""
                
                # Get the first and last date of the week
                dates = sorted(week_df['Data_Obiect'].dropna())
                week_start = dates[0].strftime('%d %b') if dates else ""
                week_end = dates[-1].strftime('%d %b') if dates else ""
                week_range = f"{week_start} - {week_end}" if week_start and week_end else f"Săpt. {week}"
                
                weekly_data.append({
                    'Angajat': employee,
                    'Departament': department,
                    'An': year,
                    'Săptămână': week,
                    'Interval': week_range,
                    'Ore Totale': total_hours,
                    'Ore Standard': total_standard_hours,
                    'Diferență': total_hours - total_standard_hours
                })
        
        weekly_df = pd.DataFrame(weekly_data)
        
        # Calculate monthly totals
        monthly_data = []
        
        if not df.empty and 'Luna' in df.columns and 'An' in df.columns:
            for (employee, year, month), month_df in df.groupby(['Angajat', 'An', 'Luna']):
                if pd.isna(year) or pd.isna(month):
                    continue
                    
                # Calculate actual hours worked
                total_hours = month_df['Durata (Ore)'].sum()
                
                # Calculate standard hours for the month
                standard_hours = calculate_standard_monthly_hours(int(year), int(month))
                
                # Get department
                department = month_df['Departament'].iloc[0] if 'Departament' in month_df.columns else ""
                
                # Get month name
                month_name = month_df['Luna_Nume'].iloc[0] if not month_df['Luna_Nume'].isna().all() else ""
                
                monthly_data.append({
                    'Angajat': employee,
                    'Departament': department,
                    'An': int(year),
                    'Luna': int(month),
                    'Luna_Nume': month_name,
                    'Ore Totale': total_hours,
                    'Ore Standard': standard_hours,
                    'Diferență': total_hours - standard_hours,
                    'Zile Lucrătoare': calculate_working_days(int(year), int(month))
                })
        
        monthly_df = pd.DataFrame(monthly_data)
        
        return df, weekly_df, monthly_df, date_range, report_year
    except Exception as e:
        st.error(f"Eroare la procesarea datelor: {e}")
        st.exception(e)
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), "N/A", datetime.now().year

# Custom CSS
st.markdown("""
<style>
    .main { padding: 2rem; }
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
        transition: background-color 0.3s;
    }
    .download-link:hover {
        background-color: #45a049;
    }
    .highlight-positive { color: green; font-weight: bold; }
    .highlight-negative { color: red; font-weight: bold; }
    .absent-row { background-color: #fff3f3; }
    .stTabs [data-baseweb="tab-list"] {
        gap: 1px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: white;
        border-radius: 4px 4px 0 0;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #f0f0f0;
        border-bottom: 2px solid #4CAF50;
    }
    .stSelectbox {
        margin-bottom: 10px;
    }
    .stMetric {
        background-color: #f9f9f9;
        padding: 10px;
        border-radius: 5px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# App header
st.title("📊 Analizor Prezență Angajați")
st.markdown("Încărcați datele de prezență și obțineți o analiză completă")

# File upload section
st.markdown("### Încărcați Datele de Prezență")
uploaded_file = st.file_uploader("Alegeți un fișier", type=['xlsx', 'csv'])

# Load historical data
historical_df = load_historical_data()

if not historical_df.empty:
    st.info(f"📊 Istoric disponibil: {len(historical_df)} înregistrări")

# Main application logic
if uploaded_file is not None:
    try:
        # Process the uploaded file
        if uploaded_file.name.endswith('.xlsx'):
            # For Excel files
            xls = pd.ExcelFile(uploaded_file)
            sheet_name = st.selectbox("Selectați Foaia", xls.sheet_names)
            df_raw = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            file_content = df_raw.to_csv(index=False)
        else:
            # For CSV files
            file_content = uploaded_file.getvalue().decode('utf-8')
        
        # Process the data
        daily_df, weekly_df, monthly_df, date_range, report_year = process_attendance_data(file_content)
        
        if not daily_df.empty:
            # Save new data to history
            updated_history = save_to_historical_data(daily_df)
            
            st.success(f"✅ Date procesate cu succes! Interval de date: {date_range}")
            
            # Add rounding percentage selector
            col1, col2 = st.columns([1, 3])
            with col1:
                rounding_percentage = st.selectbox(
                    "Procent rotunjire ore lucrate (>0)",
                    [0, 10, 15, 20],
                    key="rounding_percentage"
                )
            with col2:
                if rounding_percentage > 0:
                    st.info(f"Valorile pozitive din coloana 'Durata (Ore)' vor fi rotunjite în sus cu {rounding_percentage}%")
            
            # Create tabs for different views
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Analiză Zilnică", "📅 Sumar Săptămânal", "📆 Prezentare Lunară", "📊 Vizualizări"])

            with tab1:
                st.markdown("### Înregistrări Zilnice de Prezență")
                
                # Filter by employee
                if 'Angajat' in daily_df.columns:
                    employees = sorted(daily_df['Angajat'].unique())
                    selected_employee = st.selectbox("Selectați Angajatul", ['Toți'] + list(employees), key="daily_employee")
                    
                    if selected_employee != 'Toți':
                        filtered_df = daily_df[daily_df['Angajat'] == selected_employee]
                    else:
                        filtered_df = daily_df
                else:
                    filtered_df = daily_df
                
                # Display the DataFrame
                if not filtered_df.empty:
                    # Create copy for display, dropping unwanted columns
                    display_df = filtered_df.drop(columns=['Departament', 'ID Legitimație'])
                    
                    # Apply rounding if selected
                    if rounding_percentage > 0:
                        display_df['Durata (Ore)'] = display_df.apply(
                            lambda row: round(row['Durata (Ore)'] * (1 + rounding_percentage/100), 2) if row['Durata (Ore)'] > 0 else row['Durata (Ore)'], 
                            axis=1
                        )
                        # Recalculate difference
                        display_df['Diferență'] = display_df['Durata (Ore)'] - display_df['Ore Standard']
                                    
                    # Highlight differences
                    def highlight_difference(row):
                        if pd.isna(row['Ora Sosire']) or row['Ora Sosire'] == '':
                            return ['background-color: #fff3f3'] * len(row)
                        if row['Diferență'] > 0:
                            return ['background-color: #c6efce; color: #006100' if col == 'Diferență' else '' for col in row.index]
                        elif row['Diferență'] < 0:
                            return ['background-color: #ffc7ce; color: #9c0006' if col == 'Diferență' else '' for col in row.index]
                        return [''] * len(row)
                                    
                    styled_df = display_df.style.apply(highlight_difference, axis=1)
                                    
                    st.dataframe(styled_df, use_container_width=True)
                    
                    # Summary for displayed data
                    total_presence = display_df['Durata (Ore)'].sum()
                    total_standard = display_df['Ore Standard'].sum()
                    total_difference = total_presence - total_standard
                                    
                    # Metrics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ore Lucrate", f"{total_presence:.2f}")
                    with col2:
                        st.metric("Total Ore Standard", f"{total_standard:.2f}")
                    with col3:
                        st.metric("Diferență", f"{total_difference:.2f}", 
                                delta=f"{(total_difference/total_standard*100):.1f}%" if total_standard > 0 else None)
                    
                    # Download links
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(get_download_link(filtered_df, "prezenta_zilnica_original.csv", "📥 Descărcați Date Originale (CSV)"), unsafe_allow_html=True)
                    with col2:
                        st.markdown(get_excel_download_link(display_df, "prezenta_zilnica_afisate.xlsx", "📥 Descărcați Date Afișate (Excel)"), unsafe_allow_html=True)
                else:
                    st.info("Nu există date de afișat pentru selecția curentă.")

            with tab2:
                st.markdown("### Sumar Săptămânal")
                
                # Filter by employee
                if 'Angajat' in weekly_df.columns:
                    weekly_employees = sorted(weekly_df['Angajat'].unique())
                    selected_weekly_employee = st.selectbox("Selectați Angajatul", ['Toți'] + list(weekly_employees), key="weekly_employee")
                    
                    if selected_weekly_employee != 'Toți':
                        filtered_weekly_df = weekly_df[weekly_df['Angajat'] == selected_weekly_employee]
                    else:
                        filtered_weekly_df = weekly_df
                else:
                    filtered_weekly_df = weekly_df
                
                # Display the DataFrame
                if not filtered_weekly_df.empty:
                    # Create copy for display, dropping unwanted columns
                    display_weekly_df = filtered_weekly_df.drop(columns=['Departament'])
                    
                    # Apply rounding if selected
                    if rounding_percentage > 0:
                        display_weekly_df['Ore Totale'] = display_weekly_df['Ore Totale'].apply(
                            lambda x: round(x * (1 + rounding_percentage/100), 2) if x > 0 else x
                        )
                        # Recalculate difference
                        display_weekly_df['Diferență'] = display_weekly_df['Ore Totale'] - display_weekly_df['Ore Standard']
                    
                    # Format the DataFrame for display
                    def highlight_weekly_diff(row):
                        if row['Diferență'] > 0:
                            return ['background-color: #c6efce; color: #006100' if col == 'Diferență' else '' for col in row.index]
                        elif row['Diferență'] < 0:
                            return ['background-color: #ffc7ce; color: #9c0006' if col == 'Diferență' else '' for col in row.index]
                        return [''] * len(row)
                    
                    styled_weekly_df = display_weekly_df.style.apply(highlight_weekly_diff, axis=1)
                    
                    st.dataframe(styled_weekly_df, use_container_width=True)
                    
                    # Weekly metrics
                    week_total_hours = display_weekly_df['Ore Totale'].sum()
                    week_standard_hours = display_weekly_df['Ore Standard'].sum()
                    week_diff = week_total_hours - week_standard_hours
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ore Săptămânale", f"{week_total_hours:.2f}")
                    with col2:
                        st.metric("Standard Săptămânal", f"{week_standard_hours:.2f}")
                    with col3:
                        st.metric("Balanță", f"{week_diff:.2f}", 
                               delta=f"{(week_diff/week_standard_hours*100):.1f}%" if week_standard_hours > 0 else None)
                    
                    # Download links
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(get_download_link(filtered_weekly_df, "prezenta_saptamanala_original.csv", "📥 Descărcați Date Originale (CSV)"), unsafe_allow_html=True)
                    with col2:
                        st.markdown(get_excel_download_link(display_weekly_df, "prezenta_saptamanala_afisate.xlsx", "📥 Descărcați Date Afișate (Excel)"), unsafe_allow_html=True)
                else:
                    st.info("Nu există date săptămânale de afișat pentru selecția curentă.")

            with tab3:
                st.markdown("### Prezentare Lunară")
                
                # Filter by employee
                if 'Angajat' in monthly_df.columns:
                    monthly_employees = sorted(monthly_df['Angajat'].unique())
                    selected_monthly_employee = st.selectbox("Selectați Angajatul", ['Toți'] + list(monthly_employees), key="monthly_employee")
                    
                    if selected_monthly_employee != 'Toți':
                        filtered_monthly_df = monthly_df[monthly_df['Angajat'] == selected_monthly_employee]
                    else:
                        filtered_monthly_df = monthly_df
                else:
                    filtered_monthly_df = monthly_df
                
                if not filtered_monthly_df.empty:
                    # Create copy for display, dropping unwanted columns
                    display_monthly_df = filtered_monthly_df.drop(columns=['Departament'])
                    
                    # Apply rounding if selected
                    if rounding_percentage > 0:
                        display_monthly_df['Ore Totale'] = display_monthly_df['Ore Totale'].apply(
                            lambda x: round(x * (1 + rounding_percentage/100), 2) if x > 0 else x
                        )
                        # Recalculate difference
                        display_monthly_df['Diferență'] = display_monthly_df['Ore Totale'] - display_monthly_df['Ore Standard']
                    
                    # Format the DataFrame for display
                    def highlight_monthly_diff(row):
                        if row['Diferență'] > 0:
                            return ['background-color: #c6efce; color: #006100' if col == 'Diferență' else '' for col in row.index]
                        elif row['Diferență'] < 0:
                            return ['background-color: #ffc7ce; color: #9c0006' if col == 'Diferență' else '' for col in row.index]
                        return [''] * len(row)
                    
                    styled_monthly_df = display_monthly_df.style.apply(highlight_monthly_diff, axis=1)
                    
                    st.dataframe(styled_monthly_df, use_container_width=True)
                    
                    # Calculate working days for the selected month-year combination
                    if 'Luna' in filtered_monthly_df.columns and 'An' in filtered_monthly_df.columns:
                        # Get unique month-year combinations
                        month_year_combinations = filtered_monthly_df[['Luna_Nume', 'Luna', 'An']].drop_duplicates()
                        
                        if not month_year_combinations.empty:
                            # Format options for select box
                            month_year_options = [f"{row['Luna_Nume']} {row['An']}" for _, row in month_year_combinations.iterrows()]
                            selected_month_year = st.selectbox("Selectați Luna pentru Analiza Detaliată", month_year_options)
                            
                            # Parse selection to get month and year
                            selected_month_name = selected_month_year.split(' ')[0]
                            selected_year = int(selected_month_year.split(' ')[1])
                            
                            # Map month name to number
                            month_map = {
                                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
                            }
                            
                            if selected_month_name in month_map:
                                month_num = month_map[selected_month_name]
                                
                                # Calculate working days and standard hours dynamically
                                working_days = calculate_working_days(selected_year, month_num)
                                standard_hours = calculate_standard_monthly_hours(selected_year, month_num)
                                
                                # First and last day of the month
                                first_day = date(selected_year, month_num, 1)
                                last_day = date(selected_year, month_num, calendar.monthrange(selected_year, month_num)[1])
                                
                                # Display month information
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Zile în Lună", calendar.monthrange(selected_year, month_num)[1])
                                with col2:
                                    st.metric("Zile Lucrătoare", working_days)
                                with col3:
                                    st.metric("Ore Standard Totale", f"{standard_hours:.1f}")
                                with col4:
                                    # Calculate holidays
                                    holidays = get_holidays_for_year(selected_year)
                                    holiday_count = sum(1 for h in holidays if h.startswith(f"{selected_year}-{month_num:02d}"))
                                    st.metric("Sărbători Legale", holiday_count)
                                
                                # Detailed employee information for the selected month
                                month_data = display_monthly_df[
                                    (display_monthly_df['Luna'] == month_num) & 
                                    (display_monthly_df['An'] == selected_year)
                                ]
                                
                                if not month_data.empty:
                                    total_month_hours = month_data['Ore Totale'].sum() 
                                    total_month_standard = month_data['Ore Standard'].sum()
                                    
                                    # Calculate monthly metrics
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Total Ore Lucrate în Lună", f"{total_month_hours:.1f}")
                                    with col2:
                                        st.metric("Total Ore Standard în Lună", f"{total_month_standard:.1f}")
                                    with col3:
                                        month_diff = total_month_hours - total_month_standard
                                        st.metric("Balanță Lunară", f"{month_diff:.1f}", 
                                               delta=f"{(month_diff/total_month_standard*100):.1f}%" if total_month_standard > 0 else None)
                    
                    # Download links
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(get_download_link(filtered_monthly_df, "prezenta_lunara_original.csv", "📥 Descărcați Date Originale (CSV)"), unsafe_allow_html=True)
                    with col2:
                        st.markdown(get_excel_download_link(display_monthly_df, "prezenta_lunara_afisate.xlsx", "📥 Descărcați Date Afișate (Excel)"), unsafe_allow_html=True)
                else:
                    st.info("Nu există date lunare de afișat pentru selecția curentă.")

            with tab4:
                st.markdown("### Vizualizări")
                
                if not daily_df.empty:
                    # Filter by employee
                    if 'Angajat' in daily_df.columns:
                        viz_employees = sorted(daily_df['Angajat'].unique())
                        selected_viz_employee = st.selectbox("Selectați Angajatul", ['Toți'] + list(viz_employees), key="viz_employee")
                        
                        if selected_viz_employee != 'Toți':
                            filtered_viz_df = daily_df[daily_df['Angajat'] == selected_viz_employee]
                        else:
                            filtered_viz_df = daily_df
                    else:
                        filtered_viz_df = daily_df
                    
                    # Apply rounding for visualization if selected
                    viz_df = filtered_viz_df.copy()
                    if rounding_percentage > 0:
                        viz_df['Durata (Ore)'] = viz_df.apply(
                            lambda row: round(row['Durata (Ore)'] * (1 + rounding_percentage/100), 2) if row['Durata (Ore)'] > 0 else row['Durata (Ore)'],
                            axis=1
                        )
                    
                    # Select visualization type
                    viz_type = st.selectbox(
                        "Selectați Vizualizarea", 
                        ["Ore Zilnice per Angajat", "Comparație Săptămânală", "Distribuția Orelor de Sosire", "Distribuția Orelor de Plecare", "Prezența Zilnică"]
                    )
                    
                    try:
                        if viz_type == "Ore Zilnice per Angajat":
                            # If filtering by employee, show day by day data
                            if selected_viz_employee != 'Toți':
                                daily_emp_df = viz_df.groupby('Data')['Durata (Ore)'].sum().reset_index()
                                daily_std_df = viz_df.groupby('Data')['Ore Standard'].sum().reset_index()
                                
                                daily_merged = pd.merge(daily_emp_df, daily_std_df, on='Data')
                                
                                # Sort by date if available
                                if 'Data_Obiect' in viz_df.columns:
                                    date_mapping = dict(zip(viz_df['Data'], viz_df['Data_Obiect']))
                                    daily_merged['Data_Obiect'] = daily_merged['Data'].map(date_mapping)
                                    daily_merged = daily_merged.sort_values('Data_Obiect')
                                
                                fig = px.bar(
                                    daily_merged,
                                    x='Data',
                                    y=['Durata (Ore)', 'Ore Standard'],
                                    barmode='group',
                                    title=f"Ore Zilnice Lucrate: {selected_viz_employee}",
                                    labels={"value": "Ore", "Data": "Data", "variable": "Tip"},
                                    height=500,
                                    color_discrete_map={'Durata (Ore)': '#4CAF50', 'Ore Standard': '#2196F3'}
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                # Group by employee and date
                                pivot_df = viz_df.pivot_table(
                                    index='Data', 
                                    columns='Angajat', 
                                    values='Durata (Ore)',
                                    aggfunc='sum'
                                ).fillna(0)
                                
                                # Sort pivot table by date if possible
                                date_obj_map = {}
                                for date_str, date_obj in zip(viz_df['Data'], viz_df['Data_Obiect']):
                                    if date_str not in date_obj_map and date_obj is not None:
                                        date_obj_map[date_str] = date_obj
                                
                                if date_obj_map:
                                    pivot_df['sort_key'] = pd.Series(date_obj_map)
                                    pivot_df = pivot_df.sort_values('sort_key').drop('sort_key', axis=1)
                                
                                # Create bar chart
                                fig = px.bar(
                                    pivot_df, 
                                    barmode='group',
                                    title="Ore Zilnice Lucrate per Angajat",
                                    labels={"value": "Ore", "Data": "Data", "variable": "Angajat"},
                                    height=600
                                )
                                
                                st.plotly_chart(fig, use_container_width=True)
                            
                        elif viz_type == "Comparație Săptămânală":
                            # Filter weekly df based on selected employee
                            if selected_viz_employee != 'Toți':
                                filtered_weekly_viz = weekly_df[weekly_df['Angajat'] == selected_viz_employee]
                            else:
                                filtered_weekly_viz = weekly_df
                            
                            if not filtered_weekly_viz.empty:
                                # Apply rounding if selected
                                weekly_viz_df = filtered_weekly_viz.copy()
                                if rounding_percentage > 0:
                                    weekly_viz_df['Ore Totale'] = weekly_viz_df['Ore Totale'].apply(
                                        lambda x: round(x * (1 + rounding_percentage/100), 2) if x > 0 else x
                                    )
                                    weekly_viz_df['Diferență'] = weekly_viz_df['Ore Totale'] - weekly_viz_df['Ore Standard']
                                
                                # Create comparison chart
                                weekly_comp_fig = px.bar(
                                    weekly_viz_df,
                                    x='Angajat' if selected_viz_employee == 'Toți' else 'Interval',
                                    y=['Ore Totale', 'Ore Standard'],
                                    barmode='group',
                                    title="Ore Săptămânale: Efectiv vs. Standard",
                                    labels={"value": "Ore", "variable": "Categorie"},
                                    height=500,
                                    color_discrete_map={'Ore Totale': '#4CAF50', 'Ore Standard': '#2196F3'}
                                )
                                
                                st.plotly_chart(weekly_comp_fig, use_container_width=True)
                                
                                # Create difference chart
                                weekly_diff_fig = px.bar(
                                    weekly_viz_df,
                                    x='Angajat' if selected_viz_employee == 'Toți' else 'Interval',
                                    y='Diferență',
                                    title="Diferența de Ore față de Programul Standard",
                                    labels={"Diferență": "Ore +/-"},
                                    color='Diferență',
                                    color_continuous_scale=["red", "yellow", "green"],
                                    height=500
                                )
                                
                                weekly_diff_fig.add_hline(y=0, line_width=2, line_dash="dash", line_color="gray")
                                
                                st.plotly_chart(weekly_diff_fig, use_container_width=True)
                            else:
                                st.warning("Nu există date săptămânale pentru vizualizare.")
                            
                        elif viz_type == "Distribuția Orelor de Sosire":
                            # Convert time strings to numeric for visualization
                            arrival_df = viz_df.copy()
                            arrival_df['Ora Sosire (Numeric)'] = arrival_df['Ora Sosire'].apply(
                                lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60 if isinstance(x, str) and ':' in x else None
                            )
                            
                            # Filter out None values
                            arrival_df = arrival_df.dropna(subset=['Ora Sosire (Numeric)'])
                            
                            if not arrival_df.empty:
                                # Create arrival time histogram
                                if selected_viz_employee != 'Toți':
                                    arrival_fig = px.histogram(
                                        arrival_df,
                                        x='Ora Sosire (Numeric)',
                                        nbins=24,
                                        range_x=[6, 12],  # Focus on 6 AM to 12 PM
                                        title=f"Distribuția Orelor de Sosire pentru {selected_viz_employee}",
                                        labels={"Ora Sosire (Numeric)": "Ora Zilei", "count": "Frecvență"},
                                        height=500,
                                        color_discrete_sequence=['#2196F3']
                                    )
                                else:
                                    arrival_fig = px.histogram(
                                        arrival_df,
                                        x='Ora Sosire (Numeric)',
                                        color='Angajat',
                                        nbins=24,
                                        range_x=[6, 12],  # Focus on 6 AM to 12 PM
                                        title="Distribuția Orelor de Sosire",
                                        labels={"Ora Sosire (Numeric)": "Ora Zilei", "count": "Frecvență"},
                                        height=500
                                    )
                                
                                # Add reference line for standard start time (8:30 AM)
                                arrival_fig.add_vline(x=8.5, line_width=2, line_dash="dash", line_color="red", annotation_text="Ora Standard de Început (8:30)")
                                
                                st.plotly_chart(arrival_fig, use_container_width=True)
                            else:
                                st.warning("Nu există date de sosire pentru vizualizare.")
                            
                        elif viz_type == "Distribuția Orelor de Plecare":
                            # Convert time strings to numeric for visualization
                            departure_df = viz_df.copy()
                            departure_df['Ora Plecare (Numeric)'] = departure_df['Ora Plecare'].apply(
                                lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60 if isinstance(x, str) and ':' in x else None
                            )
                            
                            # Filter out None values
                            departure_df = departure_df.dropna(subset=['Ora Plecare (Numeric)'])
                            
                            if not departure_df.empty:
                                # Create departure time histogram
                                if selected_viz_employee != 'Toți':
                                    departure_fig = px.histogram(
                                        departure_df,
                                        x='Ora Plecare (Numeric)',
                                        nbins=24,
                                        range_x=[14, 20],  # Focus on 2 PM to 8 PM
                                        title=f"Distribuția Orelor de Plecare pentru {selected_viz_employee}",
                                        labels={"Ora Plecare (Numeric)": "Ora Zilei", "count": "Frecvență"},
                                        height=500,
                                        color_discrete_sequence=['#4CAF50']
                                    )
                                else:
                                    departure_fig = px.histogram(
                                        departure_df,
                                        x='Ora Plecare (Numeric)',
                                        color='Angajat',
                                        nbins=24,
                                        range_x=[14, 20],  # Focus on 2 PM to 8 PM
                                        title="Distribuția Orelor de Plecare",
                                        labels={"Ora Plecare (Numeric)": "Ora Zilei", "count": "Frecvență"},
                                        height=500
                                    )
                                
                                # Add reference lines for standard end times
                                departure_fig.add_vline(x=17, line_width=2, line_dash="dash", line_color="red", annotation_text="Sfârșit Luni-Joi (17:00)")
                                departure_fig.add_vline(x=14.5, line_width=2, line_dash="dash", line_color="orange", annotation_text="Sfârșit Vineri (14:30)")
                                
                                st.plotly_chart(departure_fig, use_container_width=True)
                            else:
                                st.warning("Nu există date de plecare pentru vizualizare.")
                                
                        elif viz_type == "Prezența Zilnică":
                            # Create daily presence chart
                            presence_df = viz_df.copy()
                            
                            # Add status column (present/absent)
                            presence_df['Status'] = presence_df['Durata (Ore)'].apply(
                                lambda x: 'Prezent' if x > 0 else 'Absent'
                            )
                            
                            # Create pivot for heatmap
                            if 'Data' in presence_df.columns and 'Angajat' in presence_df.columns:
                                # Ensure consistent date format
                                if 'Data_Obiect' in presence_df.columns:
                                    presence_df = presence_df.sort_values('Data_Obiect')
                                
                                # Create presence heatmap
                                if selected_viz_employee != 'Toți':
                                    # For single employee, show date vs. status
                                    pivot_presence = presence_df.pivot_table(
                                        index='Data',
                                        values='Durata (Ore)',
                                        aggfunc='sum'
                                    ).fillna(0)
                                    
                                    # Create heatmap
                                    presence_heatmap = px.imshow(
                                        pivot_presence,
                                        title=f"Prezența Zilnică pentru {selected_viz_employee}",
                                        labels=dict(x="Data", color="Ore"),
                                        color_continuous_scale=["white", "yellow", "green"],
                                        height=300
                                    )
                                else:
                                    # For all employees, show employee vs. date
                                    pivot_presence = presence_df.pivot_table(
                                        index='Angajat',
                                        columns='Data',
                                        values='Durata (Ore)',
                                        aggfunc='sum'
                                    ).fillna(0)
                                    
                                    # Create heatmap
                                    presence_heatmap = px.imshow(
                                        pivot_presence,
                                        title="Prezența Zilnică per Angajat",
                                        labels=dict(x="Data", y="Angajat", color="Ore"),
                                        color_continuous_scale=["white", "yellow", "green"],
                                        height=400
                                    )
                                
                                st.plotly_chart(presence_heatmap, use_container_width=True)
                                
                                # Create bar chart for daily presence
                                try:
                                    if selected_viz_employee != 'Toți':
                                        # For single employee
                                        daily_presence = presence_df.groupby('Data')['Durata (Ore)'].sum().reset_index()
                                        daily_std = presence_df.groupby('Data')['Ore Standard'].sum().reset_index()
                                    else:
                                        # For all employees
                                        daily_presence = viz_df.groupby('Data')['Durata (Ore)'].sum().reset_index()
                                        daily_std = viz_df.groupby('Data')['Ore Standard'].sum().reset_index()
                                    
                                    daily_combined = pd.merge(daily_presence, daily_std, on='Data', suffixes=('_Actual', '_Standard'))
                                    
                                    daily_combined_clean = daily_combined.dropna(subset=['Data', 'Durata (Ore)_Actual', 'Ore Standard_Standard']).drop_duplicates(subset=['Data'])
                                    daily_combined_clean['Durata (Ore)_Actual'] = pd.to_numeric(daily_combined_clean['Durata (Ore)_Actual'], errors='coerce').fillna(0)
                                    daily_combined_clean['Ore Standard_Standard'] = pd.to_numeric(daily_combined_clean['Ore Standard_Standard'], errors='coerce').fillna(0)

                                    if not daily_combined_clean.empty:
                                        # Sort by date if possible
                                        if 'Data_Obiect' in viz_df.columns:
                                            date_mapping = dict(zip(viz_df['Data'], viz_df['Data_Obiect']))
                                            daily_combined_clean['Data_Obiect'] = daily_combined_clean['Data'].map(date_mapping)
                                            daily_combined_clean = daily_combined_clean.sort_values('Data_Obiect')
                                        
                                        daily_bar = px.bar(
                                            daily_combined_clean,
                                            x='Data',
                                            y=['Durata (Ore)_Actual', 'Ore Standard_Standard'],
                                            barmode='group',
                                            title="Ore Lucrate vs. Standard pe Zile",
                                            labels={"value": "Ore", "variable": "Tip"},
                                            height=400,
                                            color_discrete_map={'Durata (Ore)_Actual': '#4CAF50', 'Ore Standard_Standard': '#2196F3'}
                                        )
                                        
                                        st.plotly_chart(daily_bar, use_container_width=True)
                                    else:
                                        st.warning("⚠️ Nu există suficiente date valide pentru generarea graficului zilnic.")
                                except Exception as e:
                                    st.error(f"Eroare la generarea graficului zilnic: {e}")
                    except Exception as e:
                        st.error(f"Eroare la generarea vizualizărilor: {e}")
                        st.exception(e)
                else:
                    st.info("Încărcați date pentru a vizualiza grafice.")
    except Exception as e:
        st.error(f"A apărut o eroare: {e}")
        st.exception(e)
else:
    # Display example data and instructions
    st.info("📌 Vă rugăm să încărcați un fișier Excel (.xlsx) sau CSV care conține datele de prezență ale angajaților.")
    
    st.markdown("""
    ### Format de Date Așteptat
    
    Aplicația așteaptă date de prezență într-un format similar cu următorul:
    
    ```
    Report by first and last card presenting per calendar day
    from 24 March 2025 to 27 March 2025
    
    NUME_ANGAJAT ID_ANGAJAT,DEPARTAMENT,,,,NUMĂR_ID
    Mon,Tue,Wed,Thu,Fri,Sat,Sun
    24 March,25 March,26 March,27 March,28 March,,
    08:26 - 17:26,09:00 - 17:10,08:58 - 17:15,08:37 - 17:11,,,
    ```
    
    ### Funcționalități
    
    - **Procesare Automată a Datelor**: Extrage datele de prezență ale angajaților și calculează orele lucrate
    - **Comparație cu Programul Standard**: Compară orele efective cu programul standard de lucru
    - **Analiză Completă**: Vizualizează rapoarte de prezență zilnice, săptămânale și lunare
    - **Informații Vizuale**: Vizualizează modele de prezență cu grafice interactive
    - **Funcționalitate de Export**: Descarcă datele procesate în formate CSV sau Excel
    - **Păstrarea Istoricului**: Aplicația păstrează datele încărcate anterior și actualizează doar înregistrările noi
    - **Calculul Zilelor Lucrătoare**: Aplicația calculează automat numărul de zile lucrătoare pentru fiecare lună
    """)

# Footer
st.markdown("---")
st.markdown("### 📋 Ore Standard de Lucru")
st.markdown("""
- **Luni-Joi**: 08:30 - 17:00 (8.5 ore)
- **Vineri**: 08:30 - 14:30 (6 ore)
- **Sâmbătă-Duminică**: Zile libere
""")

# Display information about working day calculation
with st.expander("ℹ️ Calculul Zilelor Lucrătoare"):
    st.markdown("""
    **Regulile pentru calculul zilelor lucrătoare**:
    
    1. Zilele de Luni-Vineri sunt considerate zile lucrătoare
    2. Zilele de Sâmbătă-Duminică sunt considerate zile libere
    3. Sărbătorile legale din România sunt excluse din calculul zilelor lucrătoare
    4. Orele standard pentru zilele lucrătoare sunt:
        - Luni-Joi: 8.5 ore (8 ore și 30 minute)
        - Vineri: 6 ore
    
    **Exemplu de calcul pentru o săptămână completă (5 zile lucrătoare)**:
    - 4 zile x 8.5 ore = 34 ore
    - 1 zi x 6 ore = 6 ore
    - Total: 40 ore
    """)

# Display information about holidays
with st.expander("📅 Sărbători Legale"):
    try:
        # Determine which years to show based on data and current year
        years_to_show = [datetime.now().year, datetime.now().year + 1]
        
        all_holidays = {}
        for year in years_to_show:
            holidays = get_holidays_for_year(year)
            all_holidays[year] = holidays
        
        # Create tabs for each year
        year_tabs = st.tabs([str(year) for year in years_to_show])
        
        for i, year in enumerate(years_to_show):
            with year_tabs[i]:
                if year in all_holidays and all_holidays[year]:
                    # Generate descriptions based on dates
                    descriptions = []
                    for holiday_date in all_holidays[year]:
                        month_day = holiday_date[5:]  # Gets MM-DD
                        
                        # Map common Romanian holidays
                        if month_day == "01-01":
                            descriptions.append("Anul Nou")
                        elif month_day == "01-02":
                            descriptions.append("A doua zi după Anul Nou")
                        elif month_day == "01-24":
                            descriptions.append("Ziua Unirii Principatelor Române")
                        elif month_day == "05-01":
                            descriptions.append("Ziua Muncii")
                        elif month_day == "08-15":
                            descriptions.append("Adormirea Maicii Domnului")
                        elif month_day == "11-30":
                            descriptions.append("Sfântul Andrei")
                        elif month_day == "12-01":
                            descriptions.append("Ziua Națională a României")
                        elif month_day == "12-25":
                            descriptions.append("Crăciunul")
                        elif month_day == "12-26":
                            descriptions.append("A doua zi de Crăciun")
                        else:
                            descriptions.append("Sărbătoare legală")
                    
                    holidays_df = pd.DataFrame({
                        "Data": all_holidays[year],
                        "Descriere": descriptions
                    })
                    
                    st.dataframe(holidays_df, use_container_width=True)
                else:
                    st.info(f"Nu există informații despre sărbătorile legale pentru anul {year}")
    except Exception as e:
        st.warning(f"Nu s-au putut afișa sărbătorile legale: {e}")

# Application footer
st.markdown("---")
st.markdown("### 📊 Analizor Prezență Angajați v3.0")
### st.markdown("Dezvoltat pentru monitorizarea și analiza prezenței angajaților")
