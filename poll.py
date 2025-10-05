import streamlit as st
try:
        from streamlit_autorefresh import st_autorefresh
except Exception:
        # Fallback: minimal JS-based auto-refresh if streamlit-autorefresh isn't installed
        def st_autorefresh(interval: int = 1000, key: str | None = None):
                safe_key = key or "auto_refresh"
                st.markdown(
                        f"""
                        <script>
                        (function() {{
                            const interval = {interval};
                            const key = {safe_key!r};
                            window._stAuto = window._stAuto || {{}};
                            if (!window._stAuto[key]) {{
                                window._stAuto[key] = true;
                                setTimeout(function() {{
                                    // Trigger a full page reload; Streamlit preserves widget state across reruns
                                    window.location.reload();
                                }}, interval);
                            }}
                        }})();
                        </script>
                        """,
                        unsafe_allow_html=True,
                )
                return 0
import time
from uuid import uuid4
from threading import Lock

@st.cache_resource(show_spinner=False)
def get_store():
    # A process-wide shared store (per Streamlit server process)
    return {
        'polls': {},                 # {question: {option: count}}
        'user_votes': {},            # {user_id: {question: option}}
        'last_refresh_ts': 0.0,      # float timestamp
        'lock': Lock(),
    }

def load_polls():
    return get_store()['polls']

def save_polls(new_polls):
    store = get_store()
    store['polls'] = new_polls

def load_user_votes():
    return get_store()['user_votes']

def save_user_votes(new_votes):
    store = get_store()
    store['user_votes'] = new_votes

def get_refresh_trigger():
    return get_store()['last_refresh_ts']

def trigger_refresh():
    get_store()['last_refresh_ts'] = time.time()

def check_for_refresh():
    if 'last_refresh_check' not in st.session_state:
        st.session_state.last_refresh_check = 0
    
    current_trigger = get_refresh_trigger()
    if current_trigger > st.session_state.last_refresh_check:
        st.session_state.last_refresh_check = current_trigger
        st.rerun()

# Check for admin-triggered refresh (only for non-admin users)
if 'user_role' not in st.session_state or st.session_state.user_role != "admin":
    check_for_refresh()

# Initialize session state for user role and unique ID
if "user_role" not in st.session_state:
    st.session_state.user_role = "user"
if "user_id" not in st.session_state:
    st.session_state.user_id = str(uuid4())

# Note: We'll trigger auto-refresh right before rendering the results section,
# so only vote counts/percentages effectively change while inputs remain intact.

# Admin credentials (prefer secrets; fallback to defaults)
ADMIN_USERNAME = st.secrets.get("ADMIN_USERNAME", "SRMS")
ADMIN_PASSWORD = st.secrets.get("ADMIN_PASSWORD", "SRMS@450")

st.title("🗳️ Myth or fact")

# Load current data from shared store (in-memory)
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
    
    # Admin refresh button
    if st.sidebar.button("🔄 Refresh All Users", help="Update all user screens with latest changes"):
        trigger_refresh()
        st.sidebar.success("All users will see updates now!")
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Add new poll
    with st.sidebar.expander("➕ Add New Poll"):
        poll_question = st.text_input("Enter your question:")
        poll_options = st.text_area("Enter options (one per line):")
        overwrite = st.checkbox("Overwrite if question exists", value=False)
        
        if st.button("Create Poll"):
            if poll_question and poll_options:
                q = poll_question.strip()
                if not q:
                    st.error("Question cannot be empty or whitespace.")
                    st.stop()
                # Deduplicate and validate options (min 2)
                raw_opts = [opt.strip() for opt in poll_options.split("\n") if opt.strip()]
                unique_opts = []
                for o in raw_opts:
                    if o not in unique_opts:
                        unique_opts.append(o)
                if len(unique_opts) >= 2:
                    # Safe write with shared in-memory lock
                    store = get_store()
                    with store['lock']:
                        current_polls = load_polls().copy()
                        current_votes = load_user_votes().copy()
                        if q in current_polls and not overwrite:
                            st.error("Question already exists. Enable 'Overwrite' to replace it.")
                        else:
                            current_polls[q] = {opt: 0 for opt in unique_opts}
                            save_polls(current_polls)
                            # If overwriting existing poll, clear users' recorded votes for this question
                            if q in current_votes:
                                pass  # no direct mapping at top-level; per-user below
                            changed = False
                            for user_id in list(current_votes.keys()):
                                if q in current_votes[user_id]:
                                    del current_votes[user_id][q]
                                    changed = True
                                if len(current_votes[user_id]) == 0:
                                    del current_votes[user_id]
                            if changed:
                                save_user_votes(current_votes)
                            st.success("Poll created successfully!")
                            st.info("💡 Click 'Refresh All Users' to update everyone's screen")
                            trigger_refresh()
                else:
                    st.error("Please provide at least 2 options.")
            else:
                st.error("Please enter a question and options.")

    # Reset polling data (votes) for a question without deleting the question
    if polls_data:
        with st.sidebar.expander("🧹 Reset Polling Data"):
            reset_all = st.checkbox("Select all polls", key="reset_all_polls")
            if not reset_all:
                reset_q = st.selectbox(
                    "Select a poll to reset votes:",
                    options=list(polls_data.keys()),
                    key="reset_select_question",
                )
            confirm_text = st.text_input("Type RESET to confirm", key="reset_confirm_text")
            action_label = "Reset All Votes" if reset_all else "Reset Votes"
            if st.button(action_label, key="reset_votes_btn"):
                if confirm_text.strip().upper() != "RESET":
                    st.error("Please type RESET to confirm.")
                else:
                    store = get_store()
                    with store['lock']:
                        current_polls = load_polls().copy()
                        current_votes = load_user_votes().copy()

                        if reset_all:
                            # Zero counts for all polls
                            for q in list(current_polls.keys()):
                                for opt in list(current_polls[q].keys()):
                                    current_polls[q][opt] = 0
                            save_polls(current_polls)
                            # Remove all users' recorded votes across all polls
                            for user_id in list(current_votes.keys()):
                                # clear the dict for the user
                                del current_votes[user_id]
                            save_user_votes(current_votes)
                        else:
                            # Zero out vote counts for the selected poll
                            if reset_q in current_polls:
                                for opt in list(current_polls[reset_q].keys()):
                                    current_polls[reset_q][opt] = 0
                                save_polls(current_polls)

                            # Remove users' recorded vote for the selected poll
                            changed = False
                            for user_id in list(current_votes.keys()):
                                if reset_q in current_votes[user_id]:
                                    del current_votes[user_id][reset_q]
                                    changed = True
                                if user_id in current_votes and len(current_votes[user_id]) == 0:
                                    del current_votes[user_id]
                            if changed:
                                save_user_votes(current_votes)

                    st.success("All votes reset!" if reset_all else f"Votes reset for: {reset_q}")
                    try:
                        trigger_refresh()
                    except Exception:
                        pass
                    st.rerun()
    
    # Delete existing polls (no confirmation per request)
    if polls_data:
        with st.sidebar.expander("🗑️ Delete Polls"):
            del_q = st.selectbox("Select a poll to delete:", options=list(polls_data.keys()), key="delete_select_question")
            if st.button("Delete Selected Poll", key="delete_poll_btn"):
                store = get_store()
                with store['lock']:
                    current_polls = load_polls().copy()
                    current_votes = load_user_votes().copy()
                    if del_q in current_polls:
                        del current_polls[del_q]
                        save_polls(current_polls)
                    for user_id in list(current_votes.keys()):
                        if del_q in current_votes[user_id]:
                            del current_votes[user_id][del_q]
                        if len(current_votes[user_id]) == 0:
                            del current_votes[user_id]
                    save_user_votes(current_votes)
                st.success("Poll deleted!")
                st.info("💡 Click 'Refresh All Users' to update everyone's screen")
                st.rerun()
else:
    # Regular user cannot create polls
    st.sidebar.info("👤 Regular User Mode\n\nOnly admins can add or delete questions.")

# Show existing polls (available to both admin and users)
if polls_data:
    # Auto-refresh just before rendering results so counts/percentages update
    if st.session_state.user_role != "admin":
        st_autorefresh(interval=1000, key="polls_results_refresh")
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
                    # Record vote safely with shared in-memory lock
                    store = get_store()
                    with store['lock']:
                        current_polls = load_polls().copy()
                        current_votes = load_user_votes().copy()

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