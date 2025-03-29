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
import json

st.set_page_config(page_title="Analizor Prezență Angajați", layout="wide")

# Definirea constantelor pentru orele standard de lucru
STANDARD_HOURS = {
    'Mon': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Tue': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Wed': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Thu': {'start': '08:30', 'end': '17:00', 'duration': 8.5},
    'Fri': {'start': '08:30', 'end': '14:30', 'duration': 6.0},
    'Sat': {'start': None, 'end': None, 'duration': 0},
    'Sun': {'start': None, 'end': None, 'duration': 0}
}

# Sărbători legale în România - exemplu pentru 2025
ROMANIAN_HOLIDAYS_2025 = [
    "2025-01-01",  # Anul Nou
    "2025-01-02",  # A doua zi după Anul Nou
    "2025-01-24",  # Ziua Unirii Principatelor Române
    "2025-04-18",  # Vinerea Mare
    "2025-04-20",  # Paștele ortodox
    "2025-04-21",  # A doua zi de Paște
    "2025-05-01",  # Ziua Muncii
    "2025-06-08",  # Rusalii
    "2025-06-09",  # A doua zi de Rusalii
    "2025-08-15",  # Adormirea Maicii Domnului
    "2025-11-30",  # Sfântul Andrei
    "2025-12-01",  # Ziua Națională a României
    "2025-12-25",  # Crăciunul
    "2025-12-26",  # A doua zi de Crăciun
]

# Funcție pentru a verifica dacă o dată este sărbătoare legală
def is_holiday(check_date):
    date_str = check_date.strftime("%Y-%m-%d")
    return date_str in ROMANIAN_HOLIDAYS_2025

# Funcție pentru calcularea zilelor lucrătoare într-o lună
def calculate_working_days(year, month):
    num_days = calendar.monthrange(year, month)[1]
    working_days = 0
    
    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        if current_date.weekday() < 5:  # 0-4 reprezintă Luni-Vineri
            date_str = current_date.strftime("%Y-%m-%d")
            if date_str not in ROMANIAN_HOLIDAYS_2025:
                working_days += 1
    
    return working_days

# Funcție pentru calcularea orelor standard de lucru pentru o lună
def calculate_standard_monthly_hours(year, month):
    num_days = calendar.monthrange(year, month)[1]
    total_hours = 0
    
    for day in range(1, num_days + 1):
        current_date = date(year, month, day)
        weekday = current_date.weekday()
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Skip weekends and holidays
        if weekday >= 5 or date_str in ROMANIAN_HOLIDAYS_2025:
            continue
        
        # Add hours based on day of week
        if weekday == 4:  # Friday
            total_hours += 6.0
        else:  # Monday to Thursday
            total_hours += 8.5
    
    return total_hours

# Funcție pentru calculul orelor standard pentru o perioadă specifică
def calculate_standard_hours_for_period(start_date, end_date):
    total_hours = 0
    current_date = start_date
    
    while current_date <= end_date:
        weekday = current_date.weekday()
        date_str = current_date.strftime("%Y-%m-%d")
        
        # Skip weekends and holidays
        if weekday < 5 and date_str not in ROMANIAN_HOLIDAYS_2025:
            # Add hours based on day of week
            if weekday == 4:  # Friday
                total_hours += 6.0
            else:  # Monday to Thursday
                total_hours += 8.5
        
        current_date += timedelta(days=1)
    
    return total_hours

# Funcție pentru parsarea formatelor de timp
def parse_time(time_str):
    if pd.isna(time_str) or time_str == '':
        return None
    try:
        return datetime.strptime(time_str.strip(), '%H:%M')
    except:
        return None

# Funcție pentru calcularea duratei între ore
def calculate_duration(entry_time, exit_time):
    if entry_time is None or exit_time is None:
        return 0
    
    duration = exit_time - entry_time
    hours = duration.total_seconds() / 3600
    return round(hours, 2)

# Funcție pentru extragerea datelor angajaților din conținutul CSV
def process_attendance_data(file_content):
    # Citirea conținutului CSV
    lines = file_content.strip().split('\n')
    
    # Extragerea datelor din antet
    date_range_line = lines[1] if len(lines) > 1 else ""
    date_match = re.search(r'from\s+(\d+\s+\w+\s+\d+)\s+to\s+(\d+\s+\w+\s+\d+)', date_range_line)
    date_range = f"{date_match.group(1)} - {date_match.group(2)}" if date_match else "N/A"
    
    # Extragerea datelor de început și sfârșit pentru a calcula zilele lucrătoare
    start_date_str = date_match.group(1) if date_match else None
    end_date_str = date_match.group(2) if date_match else None
    
    try:
        start_date = datetime.strptime(start_date_str, '%d %B %Y') if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%d %B %Y') if end_date_str else None
    except:
        start_date = None
        end_date = None
    
    data = []
    current_employee = None
    badge_id = None
    days_data = []
    weekdays = None
    dates = None
    
    for line in lines:
        line = line.strip()
        
        # Ignorarea liniilor goale
        if not line:
            continue
        
        # Verificarea dacă este o linie de antet pentru angajat
        employee_match = re.search(r',([^,]+\s+[^,]+\s+\d+),([^,]*),', line)
        if employee_match:
            # Procesarea datelor angajatului anterior dacă există
            if current_employee and days_data:
                for day_idx, (day, date_str, time_range) in enumerate(zip(weekdays, dates, days_data)):
                    if time_range and '-' in time_range:
                        entry_time_str, exit_time_str = time_range.split(' - ')
                        entry_time = parse_time(entry_time_str)
                        exit_time = parse_time(exit_time_str)
                        
                        if entry_time and exit_time:
                            duration = calculate_duration(entry_time, exit_time)
                            standard_duration = STANDARD_HOURS.get(day, {'duration': 0})['duration']
                            
                            data.append({
                                'Angajat': current_employee,
                                'ID Legitimație': badge_id,
                                'Zi': day,
                                'Data': date_str,
                                'Ora Sosire': entry_time_str,
                                'Ora Plecare': exit_time_str,
                                'Durata (Ore)': duration,
                                'Ore Standard': standard_duration,
                                'Diferență': duration - standard_duration
                            })
            
            # Setarea datelor pentru noul angajat
            current_employee = employee_match.group(1).strip()
            
            # Extragerea ID-ului legitimației
            badge_match = re.search(r'(\d{3}[A-Z0-9]+)$', line)
            badge_id = badge_match.group(1) if badge_match else "N/A"
            
            days_data = []
            continue
        
        # Verificarea dacă este o linie de antet pentru zilele săptămânii
        if line.startswith('Mon,Tue,Wed,Thu,Fri,Sat,Sun'):
            weekdays = line.split(',')
            continue
        
        # Verificarea dacă este o linie de dată
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
        
        # Verificarea dacă este o linie de interval de timp
        time_range_match = re.match(r'(\d{1,2}:\d{2}\s+-\s+\d{1,2}:\d{2})?,(\d{1,2}:\d{2}\s+-\s+\d{1,2}:\d{2})?,', line)
        if time_range_match:
            days_data = line.split(',')
            days_data = [d.strip() if d.strip() else None for d in days_data]
            
            # Procesarea datelor angajatului curent
            if current_employee and days_data:
                for day_idx, (day, date_str, time_range) in enumerate(zip(weekdays, dates, days_data)):
                    if date_str:  # Verificăm dacă există dată
                        if time_range and '-' in time_range:
                            entry_time_str, exit_time_str = time_range.split(' - ')
                            entry_time = parse_time(entry_time_str)
                            exit_time = parse_time(exit_time_str)
                            
                            if entry_time and exit_time:
                                duration = calculate_duration(entry_time, exit_time)
                                standard_duration = STANDARD_HOURS.get(day, {'duration': 0})['duration']
                                
                                data.append({
                                    'Angajat': current_employee,
                                    'ID Legitimație': badge_id,
                                    'Zi': day,
                                    'Data': date_str,
                                    'Ora Sosire': entry_time_str,
                                    'Ora Plecare': exit_time_str,
                                    'Durata (Ore)': duration,
                                    'Ore Standard': standard_duration,
                                    'Diferență': duration - standard_duration
                                })
                        else:
                            # Data există dar nu există interval de timp (zi absentă)
                            standard_duration = STANDARD_HOURS.get(day, {'duration': 0})['duration']
                            
                            data.append({
                                'Angajat': current_employee,
                                'ID Legitimație': badge_id,
                                'Zi': day,
                                'Data': date_str,
                                'Ora Sosire': '',
                                'Ora Plecare': '',
                                'Durata (Ore)': 0,
                                'Ore Standard': standard_duration,
                                'Diferență': -standard_duration  # Negativ deoarece este absentă
                            })
            
            days_data = []
            continue
    
    # Crearea DataFrame-ului
    df = pd.DataFrame(data)
    
    # Adăugarea zilelor lucrătoare lipsă pentru fiecare angajat
    if not df.empty and start_date and end_date:
        all_employees = df['Angajat'].unique()
        
        for employee in all_employees:
            current_date = start_date
            while current_date <= end_date:
                weekday_num = current_date.weekday()
                
                # Verificăm dacă este zi lucrătoare (Luni-Vineri și nu e sărbătoare)
                if weekday_num < 5 and not is_holiday(current_date):
                    date_str = current_date.strftime("%d %B")
                    weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][weekday_num]
                    
                    # Verificăm dacă această zi există deja pentru acest angajat
                    employee_df = df[df['Angajat'] == employee]
                    if not ((employee_df['Data'] == date_str) & (employee_df['Zi'] == weekday)).any():
                        standard_duration = STANDARD_HOURS.get(weekday, {'duration': 0})['duration']
                        
                        # Adaugă ziua lipsă
                        badge_id = df[df['Angajat'] == employee]['ID Legitimație'].iloc[0] if not employee_df.empty else "N/A"
                        
                        new_row = {
                            'Angajat': employee,
                            'ID Legitimație': badge_id,
                            'Zi': weekday,
                            'Data': date_str,
                            'Ora Sosire': '',
                            'Ora Plecare': '',
                            'Durata (Ore)': 0,
                            'Ore Standard': standard_duration,
                            'Diferență': -standard_duration
                        }
                        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
                
                current_date += timedelta(days=1)
        
        # Sortăm DataFrame-ul după angajat și dată
        if 'Data' in df.columns and not df.empty:
            df['Data_sort'] = pd.to_datetime(df['Data'] + ' 2025', format='%d %B %Y', errors='coerce')
            df = df.sort_values(['Angajat', 'Data_sort']).drop('Data_sort', axis=1)
    
    # Calcularea totalurilor săptămânale pentru fiecare angajat
    weekly_data = []
    
    for employee, emp_df in df.groupby('Angajat'):
        total_hours = emp_df['Durata (Ore)'].sum()
        total_standard_hours = emp_df['Ore Standard'].sum()
        
        weekly_data.append({
            'Angajat': employee,
            'Ore Totale': total_hours,
            'Ore Standard': total_standard_hours,
            'Diferență': total_hours - total_standard_hours
        })
    
    weekly_df = pd.DataFrame(weekly_data)
    
    # Extragerea lunii din date pentru calculele lunare
    if not df.empty and 'Data' in df.columns:
        df['Luna'] = df['Data'].apply(lambda x: x.split(' ')[1] if x and ' ' in x else None)
        
        # Calcularea totalurilor lunare
        monthly_data = []
        for (employee, month), month_df in df.groupby(['Angajat', 'Luna']):
            if month:  # Se ignoră dacă luna este None
                total_hours = month_df['Durata (Ore)'].sum()
                total_standard_hours = month_df['Ore Standard'].sum()
                
                monthly_data.append({
                    'Angajat': employee,
                    'Luna': month,
                    'Ore Totale': total_hours,
                    'Ore Standard': total_standard_hours,
                    'Diferență': total_hours - total_standard_hours
                })
        
        monthly_df = pd.DataFrame(monthly_data)
    else:
        monthly_df = pd.DataFrame()
    
    return df, weekly_df, monthly_df, date_range

# Funcție pentru a încărca datele istorice
def load_historical_data():
    if 'historical_data' not in st.session_state:
        # Încercarea de a încărca date din sesiunea de aplicație
        try:
            if os.path.exists('data/attendance_history.csv'):
                historical_df = pd.read_csv('data/attendance_history.csv')
                st.session_state.historical_data = historical_df
            else:
                st.session_state.historical_data = pd.DataFrame()
        except Exception as e:
            st.warning(f"Nu s-a putut încărca istoricul: {e}")
            st.session_state.historical_data = pd.DataFrame()
    
    return st.session_state.historical_data

# Funcție pentru a salva date în istoric
def save_to_historical_data(new_data):
    historical_df = load_historical_data()
    
    if historical_df.empty:
        historical_df = new_data
    else:
        # Verificarea dacă există înregistrări duplicate și actualizarea lor
        # Cheie unică: Angajat + Data
        if 'Angajat' in new_data.columns and 'Data' in new_data.columns:
            # Eliminarea înregistrărilor existente care se suprapun cu noile date
            for _, row in new_data.iterrows():
                mask = (historical_df['Angajat'] == row['Angajat']) & (historical_df['Data'] == row['Data'])
                historical_df = historical_df[~mask]
            
            # Adăugarea noilor date
            historical_df = pd.concat([historical_df, new_data], ignore_index=True)
    
    # Salvarea datelor actualizate
    st.session_state.historical_data = historical_df
    
    # Salvarea în fișier dacă este posibil
    try:
        os.makedirs('data', exist_ok=True)
        historical_df.to_csv('data/attendance_history.csv', index=False)
    except Exception as e:
        st.warning(f"Nu s-a putut salva istoricul: {e}")
    
    return historical_df

# Funcție pentru a crea link de descărcare
def get_download_link(df, filename, link_text):
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}" class="download-link">{link_text}</a>'
    return href

# Funcție pentru a crea link de descărcare Excel
def get_excel_download_link(df, filename, link_text):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    excel_data = output.getvalue()
    b64 = base64.b64encode(excel_data).decode()
    href = f'<a href="data:application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;base64,{b64}" download="{filename}" class="download-link">{link_text}</a>'
    return href

# Definirea CSS personalizat
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
    .absent-row {
        background-color: #fff3f3;
    }
</style>
""", unsafe_allow_html=True)

# Antetul aplicației
st.title("📊 Analizor Prezență Angajați")
st.markdown("Încărcați datele de prezență și obțineți o analiză completă")

# Secțiunea de încărcare fișier
st.markdown("### Încărcați Datele de Prezență")
uploaded_file = st.file_uploader("Alegeți un fișier", type=['xlsx', 'csv'])

# Încărcarea datelor istorice
historical_df = load_historical_data()

if not historical_df.empty:
    st.info(f"📊 Istoric disponibil: {len(historical_df)} înregistrări")

if uploaded_file is not None:
    try:
        # Procesarea fișierului încărcat
        if uploaded_file.name.endswith('.xlsx'):
            # Pentru fișiere Excel
            xls = pd.ExcelFile(uploaded_file)
            sheet_name = st.selectbox("Selectați Foaia", xls.sheet_names)
            df_raw = pd.read_excel(uploaded_file, sheet_name=sheet_name)
            file_content = df_raw.to_csv(index=False)
        else:
            # Pentru fișiere CSV
            file_content = uploaded_file.getvalue().decode('utf-8')
        
        # Procesarea datelor
        daily_df, weekly_df, monthly_df, date_range = process_attendance_data(file_content)
        
        if not daily_df.empty:
            # Salvarea datelor noi în istoric
            updated_history = save_to_historical_data(daily_df)
            
            st.success(f"✅ Date procesate cu succes! Interval de date: {date_range}")
            
            # Crearea taburilor pentru diferite vizualizări
            tab1, tab2, tab3, tab4 = st.tabs(["📋 Analiză Zilnică", "📅 Sumar Săptămânal", "📆 Prezentare Lunară", "📊 Vizualizări"])
            
            with tab1:
                st.markdown("### Înregistrări Zilnice de Prezență")
                
                # Filtrarea după angajat
                if 'Angajat' in daily_df.columns:
                    employees = sorted(daily_df['Angajat'].unique())
                    selected_employee = st.selectbox("Selectați Angajatul", ['Toți'] + list(employees))
                    
                    if selected_employee != 'Toți':
                        filtered_df = daily_df[daily_df['Angajat'] == selected_employee]
                    else:
                        filtered_df = daily_df
                else:
                    filtered_df = daily_df
                
                # Formatarea DataFrame-ului pentru afișare
                display_df = filtered_df.copy()
                
                # Evidențierea diferențelor
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
                
                # Rezumat pentru datele afișate
                if not filtered_df.empty:
                    total_presence = filtered_df['Durata (Ore)'].sum()
                    total_standard = filtered_df['Ore Standard'].sum()
                    total_difference = total_presence - total_standard
                    
                    # Metrici sintetice
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ore Lucrate", f"{total_presence:.2f}")
                    with col2:
                        st.metric("Total Ore Standard", f"{total_standard:.2f}")
                    with col3:
                        st.metric("Diferență", f"{total_difference:.2f}", 
                                delta=f"{(total_difference/total_standard*100):.1f}%" if total_standard > 0 else None)
                
                # Linkuri de descărcare
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(get_download_link(filtered_df, "prezenta_zilnica.csv", "📥 Descărcați Date Zilnice (CSV)"), unsafe_allow_html=True)
                with col2:
                    st.markdown(get_excel_download_link(filtered_df, "prezenta_zilnica.xlsx", "📥 Descărcați Date Zilnice (Excel)"), unsafe_allow_html=True)
            
            with tab2:
                st.markdown("### Sumar Săptămânal de Prezență")
                
                # Formatarea DataFrame-ului pentru afișare
                def highlight_weekly_diff(row):
                    if row['Diferență'] > 0:
                        return ['background-color: #c6efce; color: #006100' if col == 'Diferență' else '' for col in row.index]
                    elif row['Diferență'] < 0:
                        return ['background-color: #ffc7ce; color: #9c0006' if col == 'Diferență' else '' for col in row.index]
                    return [''] * len(row)
                
                styled_weekly_df = weekly_df.style.apply(highlight_weekly_diff, axis=1)
                
                st.dataframe(styled_weekly_df, use_container_width=True)
                
                # Metrici săptămânale
                if not weekly_df.empty:
                    week_total_hours = weekly_df['Ore Totale'].sum()
                    week_standard_hours = weekly_df['Ore Standard'].sum()
                    week_diff = week_total_hours - week_standard_hours
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Ore Săptămânale", f"{week_total_hours:.2f}")
                    with col2:
                        st.metric("Standard Săptămânal", f"{week_standard_hours:.2f}")
                    with col3:
                        st.metric("Balanță", f"{week_diff:.2f}", 
                               delta=f"{(week_diff/week_standard_hours*100):.1f}%" if week_standard_hours > 0 else None)
                
                # Linkuri de descărcare
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(get_download_link(weekly_df, "prezenta_saptamanala.csv", "📥 Descărcați Date Săptămânale (CSV)"), unsafe_allow_html=True)
                with col2:
                    st.markdown(get_excel_download_link(weekly_df, "prezenta_saptamanala.xlsx", "📥 Descărcați Date Săptămânale (Excel)"), unsafe_allow_html=True)
            
            with tab3:
                st.markdown("### Prezentare Lunară de Prezență")
                
                if not monthly_df.empty:
                    # Formatarea DataFrame-ului pentru afișare
                    def highlight_monthly_diff(row):
                        if row['Diferență'] > 0:
                            return ['background-color: #c6efce; color: #006100' if col == 'Diferență' else '' for col in row.index]
                        elif row['Diferență'] < 0:
                            return ['background-color: #ffc7ce; color: #9c0006' if col == 'Diferență' else '' for col in row.index]
                        return [''] * len(row)
                    
                    styled_monthly_df = monthly_df.style.apply(highlight_monthly_diff, axis=1)
                    
                    st.dataframe(styled_monthly_df, use_container_width=True)
                    
                    # Calcularea zilelor lucrătoare pentru luna curentă
                    if 'Luna' in monthly_df.columns:
                        months_available = monthly_df['Luna'].unique()
                        if len(months_available) > 0:
                            selected_month = st.selectbox("Selectați Luna pentru Analiza Detaliată", months_available)
                            
                            # Conversia numelui lunii la număr
                            month_map = {
                                'January': 1, 'February': 2, 'March': 3, 'April': 4, 'May': 5, 'June': 6,
                                'July': 7, 'August': 8, 'September': 9, 'October': 10, 'November': 11, 'December': 12
                            }
                            
                            if selected_month in month_map:
                                month_num = month_map[selected_month]
                                
                                # Presupunem anul 2025 pentru exemplu
                                year = 2025
                                
                                # Calcularea zilelor lucrătoare
                                working_days = calculate_working_days(year, month_num)
                                standard_hours = calculate_standard_monthly_hours(year, month_num)
                                
                                # Primul și ultimul zi a lunii
                                first_day = date(year, month_num, 1)
                                last_day = date(year, month_num, calendar.monthrange(year, month_num)[1])
                                
                                # Afișarea informațiilor despre luna selectată
                                col1, col2, col3, col4 = st.columns(4)
                                with col1:
                                    st.metric("Zile în Lună", calendar.monthrange(year, month_num)[1])
                                with col2:
                                    st.metric("Zile Lucrătoare", working_days)
                                with col3:
                                    st.metric("Ore Standard Totale", f"{standard_hours:.1f}")
                                with col4:
                                    # Calcularea zilelor de sărbătoare
                                    holiday_count = sum(1 for h in ROMANIAN_HOLIDAYS_2025 if h.startswith(f"2025-{month_num:02d}"))
                                    st.metric("Sărbători Legale", holiday_count)
                                
                                # Informații detaliate despre angajați în luna selectată
                                month_data = monthly_df[monthly_df['Luna'] == selected_month]
                                
                                if not month_data.empty:
                                    total_month_hours = month_data['Ore Totale'].sum() 
                                    total_month_standard = month_data['Ore Standard'].sum()
                                    
                                    # Calcul metrici lunare
                                    col1, col2, col3 = st.columns(3)
                                    with col1:
                                        st.metric("Total Ore Lucrate în Lună", f"{total_month_hours:.1f}")
                                    with col2:
                                        st.metric("Total Ore Standard în Lună", f"{total_month_standard:.1f}")
                                    with col3:
                                        month_diff = total_month_hours - total_month_standard
                                        st.metric("Balanță Lunară", f"{month_diff:.1f}", 
                                               delta=f"{(month_diff/total_month_standard*100):.1f}%" if total_month_standard > 0 else None)
                    
                    # Linkuri de descărcare
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(get_download_link(monthly_df, "prezenta_lunara.csv", "📥 Descărcați Date Lunare (CSV)"), unsafe_allow_html=True)
                    with col2:
                        st.markdown(get_excel_download_link(monthly_df, "prezenta_lunara.xlsx", "📥 Descărcați Date Lunare (Excel)"), unsafe_allow_html=True)
                else:
                    st.info("Datele lunare nu au putut fi calculate. Verificați dacă formatul datei este corect.")
            
            with tab4:
                st.markdown("### Vizualizări de Prezență")
                
                # Selectarea tipului de vizualizare
                viz_type = st.selectbox(
                    "Selectați Vizualizarea", 
                    ["Ore Zilnice per Angajat", "Comparație Săptămânală", "Distribuția Orelor de Sosire", "Distribuția Orelor de Plecare", "Prezența Zilnică"]
                )
                
                if viz_type == "Ore Zilnice per Angajat":
                    # Gruparea după angajat și dată
                    pivot_df = daily_df.pivot_table(
                        index='Data', 
                        columns='Angajat', 
                        values='Durata (Ore)',
                        aggfunc='sum'
                    ).fillna(0)
                    
                    # Crearea unui grafic cu bare
                    fig = px.bar(
                        pivot_df, 
                        barmode='group',
                        title="Ore Zilnice Lucrate per Angajat",
                        labels={"value": "Ore", "Data": "Data", "variable": "Angajat"},
                        height=600
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                elif viz_type == "Comparație Săptămânală":
                    # Crearea graficului de comparație
                    weekly_comp_fig = px.bar(
                        weekly_df,
                        x='Angajat',
                        y=['Ore Totale', 'Ore Standard'],
                        barmode='group',
                        title="Ore Săptămânale: Efectiv vs. Standard",
                        labels={"value": "Ore", "variable": "Categorie"},
                        height=500
                    )
                    
                    st.plotly_chart(weekly_comp_fig, use_container_width=True)
                    
                    # Crearea graficului de diferență
                    weekly_diff_fig = px.bar(
                        weekly_df,
                        x='Angajat',
                        y='Diferență',
                        title="Diferența de Ore față de Programul Standard",
                        labels={"Diferență": "Ore +/-"},
                        color='Diferență',
                        color_continuous_scale=["red", "yellow", "green"],
                        height=500
                    )
                    
                    weekly_diff_fig.add_hline(y=0, line_width=2, line_dash="dash", line_color="gray")
                    
                    st.plotly_chart(weekly_diff_fig, use_container_width=True)
                    
                elif viz_type == "Distribuția Orelor de Sosire":
                    # Conversia șirurilor de timp în datetime pentru vizualizare
                    arrival_df = daily_df.copy()
                    arrival_df['Ora Sosire (Numeric)'] = arrival_df['Ora Sosire'].apply(
                        lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60 if isinstance(x, str) and ':' in x else None
                    )
                    
                    # Filtrarea valorilor None
                    arrival_df = arrival_df.dropna(subset=['Ora Sosire (Numeric)'])
                    
                    # Crearea histogramei pentru ora de sosire
                    arrival_fig = px.histogram(
                        arrival_df,
                        x='Ora Sosire (Numeric)',
                        color='Angajat',
                        nbins=24,
                        range_x=[6, 12],  # Focalizare pe 6 AM - 12 PM
                        title="Distribuția Orelor de Sosire",
                        labels={"Ora Sosire (Numeric)": "Ora Zilei", "count": "Frecvență"},
                        height=500
                    )
                    
                    # Adăugarea liniei de referință pentru ora standard de început (8:30 AM)
                    arrival_fig.add_vline(x=8.5, line_width=2, line_dash="dash", line_color="red", annotation_text="Ora Standard de Început (8:30)")
                    
                    st.plotly_chart(arrival_fig, use_container_width=True)
                    
                elif viz_type == "Distribuția Orelor de Plecare":
                    # Conversia șirurilor de timp în datetime pentru vizualizare
                    departure_df = daily_df.copy()
                    departure_df['Ora Plecare (Numeric)'] = departure_df['Ora Plecare'].apply(
                        lambda x: int(x.split(':')[0]) + int(x.split(':')[1])/60 if isinstance(x, str) and ':' in x else None
                    )
                    
                    # Filtrarea valorilor None
                    departure_df = departure_df.dropna(subset=['Ora Plecare (Numeric)'])
                    
                    # Crearea histogramei pentru ora de plecare
                    departure_fig = px.histogram(
                        departure_df,
                        x='Ora Plecare (Numeric)',
                        color='Angajat',
                        nbins=24,
                        range_x=[14, 20],  # Focalizare pe 2 PM - 8 PM
                        title="Distribuția Orelor de Plecare",
                        labels={"Ora Plecare (Numeric)": "Ora Zilei", "count": "Frecvență"},
                        height=500
                    )
                    
                    # Adăugarea liniilor de referință pentru orele standard de sfârșit
                    departure_fig.add_vline(x=17, line_width=2, line_dash="dash", line_color="red", annotation_text="Sfârşit Luni-Joi (17:00)")
                    departure_fig.add_vline(x=14.5, line_width=2, line_dash="dash", line_color="orange", annotation_text="Sfârşit Vineri (14:30)")
                    
                    st.plotly_chart(departure_fig, use_container_width=True)
                
                elif viz_type == "Prezența Zilnică":
                    # Creare grafic de prezență zilnică
                    presence_df = daily_df.copy()
                    
                    # Adăugare coloană pentru status (prezent/absent)
                    presence_df['Status'] = presence_df['Durata (Ore)'].apply(
                        lambda x: 'Prezent' if x > 0 else 'Absent'
                    )
                    
                    # Creare pivot pentru heatmap
                    if 'Data' in presence_df.columns and 'Angajat' in presence_df.columns:
                        # Asigurăm că avem un format consistent pentru dată
                        presence_df['Data_sort'] = pd.to_datetime(presence_df['Data'] + ' 2025', format='%d %B %Y', errors='coerce')
                        presence_df = presence_df.sort_values('Data_sort')
                        
                        # Creare heatmap de prezență
                        pivot_presence = presence_df.pivot_table(
                            index='Angajat',
                            columns='Data',
                            values='Durata (Ore)',
                            aggfunc='sum'
                        ).fillna(0)
                        
                        # Creare heatmap
                        presence_heatmap = px.imshow(
                            pivot_presence,
                            title="Prezența Zilnică per Angajat",
                            labels=dict(x="Data", y="Angajat", color="Ore"),
                            color_continuous_scale=["white", "yellow", "green"],
                            height=400
                        )
                        
                        st.plotly_chart(presence_heatmap, use_container_width=True)
                        
                        # Creare grafic bar pentru prezență pe zile
                        daily_presence = presence_df.groupby('Data')['Durata (Ore)'].sum().reset_index()
                        daily_std = presence_df.groupby('Data')['Ore Standard'].sum().reset_index()
                        
                        daily_combined = pd.merge(daily_presence, daily_std, on='Data', suffixes=('_Actual', '_Standard'))
                        
                        # Creare grafic
                        daily_bar = px.bar(
                            daily_combined,
                            x='Data',
                            y=['Durata (Ore)_Actual', 'Ore Standard_Standard'],
                            barmode='group',
                            title="Ore Lucrate vs. Standard pe Zile",
                            labels={"value": "Ore", "variable": "Tip"},
                            height=400
                        )
                        
                        st.plotly_chart(daily_bar, use_container_width=True)
                    
        else:
            st.error("❌ Nu s-au putut procesa datele. Verificați formatul fișierului.")
            
    except Exception as e:
        st.error(f"❌ Eroare la procesarea fișierului: {str(e)}")
        st.exception(e)
else:
    # Afișarea datelor din exemplu și instrucțiuni
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

# Subsol
st.markdown("---")
st.markdown("### 📋 Ore Standard de Lucru")
st.markdown("""
- **Luni-Joi**: 08:30 - 17:00 (8.5 ore)
- **Vineri**: 08:30 - 14:30 (6 ore)
- **Sâmbătă-Duminică**: Zile libere
""")

# Afișarea informațiilor despre calculul zilelor lucrătoare
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

# Afișarea informațiilor despre sărbătorile legale
with st.expander("📅 Sărbători Legale 2025"):
    holidays_df = pd.DataFrame({
        "Data": ROMANIAN_HOLIDAYS_2025,
        "Descriere": [
            "Anul Nou", "A doua zi după Anul Nou", "Ziua Unirii Principatelor Române",
            "Vinerea Mare", "Paștele ortodox", "A doua zi de Paște",
            "Ziua Muncii", "Rusalii", "A doua zi de Rusalii",
            "Adormirea Maicii Domnului", "Sfântul Andrei", "Ziua Națională a României",
            "Crăciunul", "A doua zi de Crăciun"
        ]
    })
    st.table(holidays_df)
