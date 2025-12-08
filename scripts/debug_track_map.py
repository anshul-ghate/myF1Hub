import fastf1
import datetime
import pandas as pd
import matplotlib.pyplot as plt
import io
import base64

# Mocking the logic from main.py
def get_track_map_image(event):
    # print(f"Event keys: {event.keys()}")
    year = event['EventDate'].year
    print(f"Attempting to get track map for: {event['EventName']} ({year})")
    try:
        # Try to get session for the current event
        session = fastf1.get_session(year, event.RoundNumber, 'Q')
        try:
            print("Trying to load current year session...")
            session.load(laps=True, telemetry=True, weather=False, messages=False)
            print("Loaded current year session.")
        except Exception as e:
            print(f"Current year load failed: {e}")
            # If loading fails (likely future race), try previous year
            prev_year = year - 1
            print(f"Trying previous year: {prev_year}")
            schedule_prev = fastf1.get_event_schedule(prev_year)
            
            # Debug: print columns and a few rows
            # print(schedule_prev.head())
            
            # Fuzzy match or exact match on Location/Country
            prev_event = schedule_prev[schedule_prev['Location'] == event.Location]
            if prev_event.empty:
                 print(f"Location match failed for {event.Location}. Trying Country: {event.Country}")
                 prev_event = schedule_prev[schedule_prev['Country'] == event.Country]
            
            if not prev_event.empty:
                round_num = prev_event.iloc[0]['RoundNumber']
                print(f"Found previous event: {prev_event.iloc[0]['EventName']} (Round {round_num})")
                try:
                    session = fastf1.get_session(prev_year, round_num, 'Q')
                    session.load(laps=True, telemetry=True, weather=False, messages=False)
                except Exception as e:
                    print(f"Previous year Q load failed: {e}. Trying Race session...")
                    session = fastf1.get_session(prev_year, round_num, 'R')
                    session.load(laps=True, telemetry=True, weather=False, messages=False)
                print("Loaded previous year session.")
            else:
                print("No previous event found.")
                return None

        lap = session.laps.pick_fastest()
        pos = lap.get_telemetry().add_distance().add_relative_distance()
        
        fig, ax = plt.subplots(figsize=(5, 3), facecolor='none')
        ax.plot(pos['X'], pos['Y'], color='#00f3ff', linewidth=2)
        ax.axis('off')
        ax.set_aspect('equal')
        
        buf = io.BytesIO()
        fig.savefig(buf, format='svg', bbox_inches='tight', transparent=True)
        buf.seek(0)
        img_str = base64.b64encode(buf.getvalue()).decode('utf-8')
        plt.close(fig)
        
        print("Image generated successfully.")
        return f"data:image/svg+xml;base64,{img_str}"
    except Exception as e:
        print(f"Error generating track map: {e}")
        with open("error.log", "w") as f:
            f.write(str(e))
        import traceback
        traceback.print_exc()
        return None

def main():
    now = datetime.datetime.now()
    print(f"Current time: {now}")
    schedule = fastf1.get_event_schedule(now.year)
    if schedule['EventDate'].max() < now:
        print("Schedule ended, checking next year")
        schedule = fastf1.get_event_schedule(now.year + 1)
    
    future_races = schedule[schedule['EventDate'] > now]
    
    if not future_races.empty:
        next_race = future_races.iloc[0]
        print(f"Next race: {next_race['EventName']} at {next_race['Location']}")
        img = get_track_map_image(next_race)
        if img:
            print(f"Result: Image data length {len(img)}")
        else:
            print("Result: None")
    else:
        print("No future races found.")

if __name__ == "__main__":
    main()
