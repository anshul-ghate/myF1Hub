import streamlit as st
import os

def render_sidebar():
    with st.sidebar:
        st.header("🏎️ F1 Intellect")
        
        # Initialize Agent lazily to avoid import issues
        if "agent" not in st.session_state:
            try:
                from utils.ai import RaceEngineer
                st.session_state.agent = RaceEngineer()
            except Exception as e:
                st.session_state.agent = None
                
        # Initialize Chat History if needed
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "Radio check. Olof here."}]

        # Chat Interface in Expander (only if agent loaded)
        if st.session_state.agent is not None:
            with st.expander("🤖 Race Engineer (Olof)", expanded=False):
                # Display history
                for msg in st.session_state.messages:
                    if msg["role"] == "user":
                        st.markdown(f"**You:** {msg['content']}")
                    else:
                        st.markdown(f"**Olof:** {msg['content']}")
                
                # Input
                prompt = st.text_input("Ask Olof:", key="sidebar_chat_input")
                if prompt:
                    # Add user message
                    st.session_state.messages.append({"role": "user", "content": prompt})
                    
                    # Generate response
                    with st.spinner("Thinking..."):
                        response = st.session_state.agent.ask(prompt)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    
                    # Rerun to update chat
                    st.rerun()
        
        st.divider()
        
        # Navigation - use proper path resolution
        st.markdown("### Navigation")
        
        # Get the app directory path
        app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Define pages with their paths relative to app/ directory
        pages = [
            ("app/main.py", "Home", "🏠"),
            ("app/pages/1_Season_Central.py", "Season Central", "🏁"),
            ("app/pages/2_analytics.py", "Analytics", "📊"),
            ("app/pages/3_predictions.py", "Predictions", "🔮"),
            ("app/pages/4_live_monitor.py", "Live Monitor", "📡"),
            ("app/pages/5_race_engineer.py", "Race Engineer", "🤖"),
            ("app/pages/6_past_races.py", "Past Races", "🏁"),
        ]
        
        for page_path, label, icon in pages:
            try:
                st.page_link(page_path, label=label, icon=icon)
            except Exception:
                # Fallback: try without app/ prefix (depends on how streamlit is run)
                try:
                    alt_path = page_path.replace("app/", "")
                    st.page_link(alt_path, label=label, icon=icon)
                except Exception:
                    st.markdown(f"{icon} {label}")
