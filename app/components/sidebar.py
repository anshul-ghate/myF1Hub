import streamlit as st
from utils.ai import RaceEngineer

def render_sidebar():
    with st.sidebar:
        st.header("🏎️ F1 Intellect")
        
        # Initialize Agent if needed
        if "agent" not in st.session_state:
            st.session_state.agent = RaceEngineer()
            
        # Initialize Chat History if needed
        if "messages" not in st.session_state:
            st.session_state.messages = [{"role": "assistant", "content": "Radio check. Olof here."}]

        # Chat Interface in Expander
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
        st.markdown("### Navigation")
        
        st.page_link("main.py", label="Home", icon="🏠")
        st.page_link("pages/1_analytics.py", label="Analytics", icon="📊")
        st.page_link("pages/2_predictions.py", label="Predictions", icon="🔮")
        st.page_link("pages/3_live_monitor.py", label="Live Monitor", icon="📡")
        st.page_link("pages/4_race_engineer.py", label="Race Engineer", icon="🤖")
