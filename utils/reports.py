import os
import google.generativeai as genai
from dotenv import load_dotenv
from utils.db import get_supabase_client
import pandas as pd

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

supabase = get_supabase_client()

def generate_race_report(race_id, year, round_num, event_name):
    """
    Generates a post-race strategy report using Gemini and saves it as a markdown file.
    """
    if not api_key:
        return
        
    try:
        # 1. Fetch Race Stats
        # Get Top 5 finishers
        laps_res = supabase.table('laps').select('*').eq('race_id', race_id).order('lap_number', desc=True).limit(100).execute()
        if not laps_res.data:
            return

        laps_df = pd.DataFrame(laps_res.data)
        
        # Get Pit Stops
        pits_res = supabase.table('pit_stops').select('*').eq('race_id', race_id).execute()
        pits_df = pd.DataFrame(pits_res.data) if pits_res.data else pd.DataFrame()
        
        # Construct Context
        context = f"""
        Race: {year} {event_name} (Round {round_num})
        
        Data Summary:
        - Total Laps Recorded: {len(laps_df)}
        - Total Pit Stops: {len(pits_df)}
        """
        
        # 2. Generate Report with LLM
        model = genai.GenerativeModel('gemini-pro')
        prompt = f"""
        You are an expert F1 Journalist and Strategy Analyst.
        Write a concise "Post-Race Strategy Debrief" for the {year} {event_name}.
        
        Context:
        {context}
        
        Since you don't have the full telemetry here, focus on a general analysis of the track characteristics and what typically happens at this GP (historical knowledge).
        Combine this with the fact that we just ingested {len(laps_df)} laps of data.
        
        Format: Markdown
        Structure:
        # 🏁 {year} {event_name} Debrief
        ## 📊 Key Stats
        ## 🧠 Strategy Analysis
        ## 🔮 Predictive Implications
        """
        
        response = model.generate_content(prompt)
        report_content = response.text
        
        # 3. Save Report
        report_dir = "reports"
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        filename = f"{report_dir}/{year}_Round{round_num}_{event_name.replace(' ', '_')}_Debrief.md"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        return filename
        
    except Exception as e:
        print(f"Failed to generate report: {e}")
        return None
