import streamlit as st
import json
import os
import time
from datetime import datetime

# Custom auto-refresh implementation using meta refresh and session state
def auto_refresh():
    # Add meta refresh tag for auto-refresh every 3 seconds
    st.markdown("""
    <meta http-equiv="refresh" content="3">
    <script>
    setTimeout(function(){
        window.location.reload(1);
    }, 3000);
    </script>
    """, unsafe_allow_html=True)

# Initialize auto-refresh
auto_refresh()

# File paths for persistent storage
POLLS_FILE = "polls_data.json"
VOTES_FILE = "user_votes.json"

# Load data from files
def load_polls():
    if os.path.exists(POLLS_FILE):
        try:
            with open(POLLS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_polls(polls_data):
    with open(POLLS_FILE, 'w') as f:
        json.dump(polls_data, f)

def load_user_votes():
    if os.path.exists(VOTES_FILE):
        try:
            with open(VOTES_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_user_votes(votes_data):
    with open(VOTES_FILE, 'w') as f:
        json.dump(votes_data, f)

# Initialize session state for user role and unique ID
if "user_role" not in st.session_state:
    st.session_state.user_role = "user"
if "user_id" not in st.session_state:
    st.session_state.user_id = f"user_{int(time.time() * 1000)}"

# Admin credentials (you can change these)
ADMIN_USERNAME = "SRMS"
ADMIN_PASSWORD = "SRMS@450"

st.title("🗳️ Dynamic Polling App")
st.caption("🔄 Auto-refreshing every 3 seconds for real-time updates")

# Load current data from files
polls_data = load_polls()
user_votes_data = load_user_votes()

# Admin login in sidebar
if st.session_state.user_role == "user":
    with st.sidebar:
        st.header("🔐 Admin Login")
        with st.form("admin_login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login as Admin")
            
            if login_btn:
                if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                    st.session_state.user_role = "admin"
                    st.success("Admin login successful!")
                    st.rerun()
                else:
                    st.error("Invalid credentials!")

# Logout button for admin
if st.session_state.user_role == "admin":
    if st.sidebar.button("🚪 Logout"):
        st.session_state.user_role = "user"
        st.rerun()

# Display current role
st.sidebar.write(f"**Current Role:** {st.session_state.user_role.title()}")

# Admin section for managing polls (ONLY FOR ADMIN)
if st.session_state.user_role == "admin":
    st.sidebar.header("🔧 Admin Controls")
    
    # Add new poll
    with st.sidebar.expander("➕ Add New Poll"):
        poll_question = st.text_input("Enter your question:")
        poll_options = st.text_area("Enter options (one per line):")
        
        if st.button("Create Poll"):
            if poll_question and poll_options:
                options = [opt.strip() for opt in poll_options.split("\n") if opt.strip()]
                if len(options) >= 2:
                    # Load fresh data and add new poll
                    current_polls = load_polls()
                    current_polls[poll_question] = {opt: 0 for opt in options}
                    save_polls(current_polls)
                    st.success("Poll created successfully!")
                    st.rerun()
                else:
                    st.error("Please provide at least 2 options.")
            else:
                st.error("Please enter a question and options.")
    
    # Delete existing polls
    if polls_data:
        with st.sidebar.expander("🗑️ Delete Polls"):
            st.write("Select polls to delete:")
            for question in list(polls_data.keys()):
                if st.button(f"Delete: {question[:30]}...", key=f"delete_{question}"):
                    # Load fresh data and remove poll
                    current_polls = load_polls()
                    current_votes = load_user_votes()
                    
                    if question in current_polls:
                        del current_polls[question]
                        save_polls(current_polls)
                    
                    # Remove associated votes for this poll
                    for user_id in list(current_votes.keys()):
                        if question in current_votes[user_id]:
                            del current_votes[user_id][question]
                    save_user_votes(current_votes)
                    
                    st.success(f"Poll deleted!")
                    st.rerun()
else:
    # Regular user cannot create polls
    st.sidebar.info("👤 Regular User Mode\n\nOnly admins can add or delete questions.")

# Show existing polls (available to both admin and users)
if polls_data:
    st.header("📊 Available Polls")
    for question, votes in polls_data.items():
        st.subheader(question)
        total_votes = sum(votes.values())
        
        # Check if current user has already voted for this poll
        user_has_voted = (st.session_state.user_id in user_votes_data and 
                         question in user_votes_data[st.session_state.user_id])

        # Display options with percentages
        for opt, count in votes.items():
            pct = (count / total_votes * 100) if total_votes > 0 else 0
            
            if user_has_voted:
                # Show results only, disable voting
                user_choice = user_votes_data[st.session_state.user_id][question]
                if opt == user_choice:
                    st.success(f"✓ {opt} ({pct:.1f}%) - Your vote")
                else:
                    st.info(f"{opt} ({pct:.1f}%)")
            else:
                # Allow voting (both admin and users can vote)
                if st.button(f"{opt} ({pct:.1f}%)", key=f"{question}_{opt}"):
                    # Load fresh data and record vote
                    current_polls = load_polls()
                    current_votes = load_user_votes()
                    
                    # Update vote count
                    if question in current_polls and opt in current_polls[question]:
                        current_polls[question][opt] += 1
                        save_polls(current_polls)
                    
                    # Record user's vote
                    if st.session_state.user_id not in current_votes:
                        current_votes[st.session_state.user_id] = {}
                    current_votes[st.session_state.user_id][question] = opt
                    save_user_votes(current_votes)
                    
                    st.success("Thanks for voting!")
                    st.rerun()
        
        if user_has_voted:
            st.write("✅ You have already voted in this poll.")
        
        # Show total votes for this poll
        st.write(f"**Total votes for this poll:** {total_votes}")
        st.markdown("---")
else:
    st.info("No polls available. " + 
           ("Create one from the admin controls in the sidebar." if st.session_state.user_role == "admin" 
            else "Please wait for an admin to create polls."))

# Admin statistics (only for admin)
if st.session_state.user_role == "admin" and polls_data:
    with st.expander("📈 Admin Statistics"):
        st.write("**Poll Overview:**")
        for question, votes in polls_data.items():
            total_votes = sum(votes.values())
            st.write(f"- {question}: {total_votes} total votes")
            for opt, count in votes.items():
                pct = (count / total_votes * 100) if total_votes > 0 else 0
                st.write(f"  - {opt}: {count} votes ({pct:.1f}%)")
        
        # Show total unique users who voted
        total_users = len(user_votes_data)
        st.write(f"**Total unique users:** {total_users}")
