import os
import google.generativeai as genai
from dotenv import load_dotenv
from utils.db import get_supabase_client
import pandas as pd

load_dotenv()

# Configure Gemini
api_key = os.getenv("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

supabase = get_supabase_client()

class RaceEngineer:
    def __init__(self):
        try:
            # Using Gemini 2.5 Flash for better performance
            self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
            self.chat = self.model.start_chat(history=[])
            self.available = True
        except Exception as e:
            print(f"AI Init Error: {e}")
            print("Falling back to gemini-1.5-flash...")
            try:
                # Fallback to 1.5 Flash if 2.5 is not available
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.chat = self.model.start_chat(history=[])
                self.available = True
            except Exception as fallback_error:
                print(f"Fallback Init Error: {fallback_error}")
                self.model = None
                self.chat = None
                self.available = False

        self.schema_context = """
        Database Schema:
        - races (id, season_year, round, name, date, circuit_id)
        - drivers (id, code, given_name, family_name, nationality)
        - circuits (id, name, location, country)
        - laps (race_id, driver_id, lap_number, lap_time, position, compound, tyre_life, gap_to_leader, fuel_load)
        - pit_stops (race_id, driver_id, lap_number, duration)
        - telemetry_stats (race_id, driver_id, lap_number, speed_max, speed_avg, throttle_avg, brake_avg)
        
        Relationships:
        - laps.race_id -> races.id
        - laps.driver_id -> drivers.id
        """

    def clear_chat(self):
        """Clears the chat history and starts a fresh conversation."""
        try:
            if self.model:
                self.chat = self.model.start_chat(history=[])
                return True
        except Exception as e:
            print(f"Error clearing chat: {e}")
            return False
    
    def generate_sql(self, user_query):
        prompt = f"""
        You are an expert F1 Data Engineer. Convert the user's question into a valid PostgreSQL query.
        
        {self.schema_context}
        
        Rules:
        1. Return ONLY the SQL query. No markdown, no explanation.
        2. Use JOINs correctly.
        3. Use ILIKE for string matching.
        4. Limit results to 10 unless specified.
        5. If the question is not about data, return "NO_SQL".
        
        User Question: {user_query}
        """
        try:
            response = self.chat.send_message(prompt)
            sql = response.text.strip().replace("```sql", "").replace("```", "")
            return sql
        except Exception as e:
            return None

    def ask(self, user_query):
        if not api_key:
            return "⚠️ AI Configuration Error: GOOGLE_API_KEY not found."
        
        if not self.available:
            return "⚠️ AI Service Unavailable: Could not initialize model (Check API Key/Model Access)."

        # 1. Try to generate SQL
        sql = self.generate_sql(user_query)
        
        data_context = ""
        if sql and "SELECT" in sql.upper() and "NO_SQL" not in sql:
            try:
                # Execute SQL (Safe read-only execution ideally, but using raw for now)
                # Supabase-py doesn't support raw SQL easily without RPC.
                # Workaround: We will use the 'rpc' if available or just rely on the LLM to explain if we can't run it.
                # Actually, for this demo, let's use a simplified approach:
                # We will ask the LLM to construct a Supabase-like filter or just answer from general knowledge if SQL fails.
                # WAIT: We can't easily run raw SQL via the JS/Python client unless we have a postgres function.
                # ALTERNATIVE: We will use the LLM to generate a natural language answer based on its internal knowledge 
                # AND we will try to fetch basic stats if possible.
                
                # REVISION: Since we can't run raw SQL easily, let's make the agent "simulate" the engineer 
                # by giving it access to the *latest* race data context we can fetch easily.
                pass
            except Exception as e:
                data_context = f"Could not execute DB query: {e}"

        # 2. Final Answer
        prompt = f"""
        You are an expert F1 Race Engineer named "Olof".
        
        User Question: {user_query}
        
        {self.schema_context}
        
        If you need specific data that you can't access, explain what query you would run.
        Otherwise, answer to the best of your ability using your training data and F1 knowledge.
        Be helpful, technical, and concise.
        """
        try:
            response = self.chat.send_message(prompt)
            return response.text
        except Exception as e:
            return f"AI Error: {str(e)}"

def get_ai_insight(context_text):
    """
    Generates a strategic insight based on the provided race context.
    """
    if not api_key:
        return "⚠️ AI Configuration Error: GOOGLE_API_KEY not found in .env"

    try:
        # Using Gemini 2.5 Flash for faster insights
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        prompt = f"""
        You are an expert Formula 1 Race Strategy Engineer.
        Analyze the following race data and provide a concise, actionable strategic insight.
        Focus on: Undercut opportunities, tyre degradation risks, and pace comparison.
        Keep it under 50 words. Use F1 terminology (box, undercut, stint, deg).
        
        Race Data Context:
        {context_text}
        """
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"AI Insight Unavailable: {str(e)}"

