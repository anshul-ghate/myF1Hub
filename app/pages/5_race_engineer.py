import streamlit as st
from utils.ai import RaceEngineer
from app.components.sidebar import render_sidebar

st.set_page_config(page_title="AI Race Engineer", page_icon="🤖", layout="wide")

# Inject Custom CSS
def local_css(file_name):
    with open(file_name) as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

local_css("app/assets/custom.css")

# Render Sidebar
render_sidebar()

st.title("🤖 F1 Intellect: Race Engineer")
st.markdown("Ask **Olof** anything about race strategy, historical data, or technical regulations.")

# Initialize Chat History
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.messages.append({"role": "assistant", "content": "Radio check. Olof here. What data do you need?"})

# Initialize Agent
if "agent" not in st.session_state:
    st.session_state.agent = RaceEngineer()

# Clear Chat Button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🗑️ Clear Chat", type="secondary", width='stretch'):
        # Clear messages
        st.session_state.messages = []
        st.session_state.messages.append({"role": "assistant", "content": "Radio check. Olof here. What data do you need?"})
        
        # Reset AI chat history (handle old agent instances without clear_chat method)
        try:
            if hasattr(st.session_state.agent, 'clear_chat'):
                if st.session_state.agent.clear_chat():
                    st.success("Chat cleared successfully!")
                else:
                    st.warning("Chat messages cleared, but AI history reset failed.")
            else:
                # Reinitialize agent if it doesn't have clear_chat method
                st.session_state.agent = RaceEngineer()
                st.success("Chat cleared successfully!")
        except Exception as e:
            st.warning(f"Chat messages cleared. AI reinitialized due to: {str(e)}")
        
        st.rerun()

st.markdown("---")

# Display Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Ask Olof..."):
    # Add user message to history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Display user message
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generate Response
    with st.chat_message("assistant"):
        with st.spinner("Analyzing telemetry..."):
            response = st.session_state.agent.ask(prompt)
            st.markdown(response)
    
    # Add assistant response to history (outside the chat_message context)
    st.session_state.messages.append({"role": "assistant", "content": response})
    
    # Rerun to update the chat display
    st.rerun()
