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
import pandas as pd
try:
    import altair as alt
    _has_altair = True
except Exception:
    _has_altair = False

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
if "user_authenticated" not in st.session_state:
    st.session_state.user_authenticated = False

# Note: We'll trigger auto-refresh right before rendering the results section,
# so only vote counts/percentages effectively change while inputs remain intact.

# Admin credentials (prefer secrets; fallback to defaults)
ADMIN_USERNAME ="srms"
ADMIN_PASSWORD ="srms@450"
USER_PASSWORD = "cetr"  # Password for regular users to access polls

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

# User password check
if st.session_state.user_role == "user" and not st.session_state.user_authenticated:
    st.header("🔐 Enter Password to Access Polls")
    with st.form("user_password_form"):
        user_password = st.text_input("Enter password to access polls:", type="password")
        password_btn = st.form_submit_button("Access Polls")
        
        if password_btn:
            if user_password == USER_PASSWORD:
                st.session_state.user_authenticated = True
                st.success("Access granted! You can now participate in polls.")
                st.rerun()
            else:
                st.error("Incorrect password! Please try again.")
    st.stop()  # Stop execution here if user is not authenticated

# Logout button for admin
if st.session_state.user_role == "admin":
    if st.sidebar.button("🚪 Logout"):
        st.session_state.user_role = "user"
        st.session_state.user_authenticated = False  # Reset user authentication
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
    with st.sidebar.expander("➕ Add New Poll", expanded=True):
        # Show flash message after rerun if we just created a poll
        if st.session_state.get("flash_poll_created"):
            st.success("Poll created successfully!")
            del st.session_state["flash_poll_created"]

    with st.form("new_poll_form", clear_on_submit=True):
            poll_question = st.text_input("Enter your question:", key="new_poll_question")
            poll_options = st.text_area("Enter options (one per line):", key="new_poll_options")
            overwrite = st.checkbox("Overwrite if question exists", value=False, key="new_poll_overwrite")
            create_submitted = st.form_submit_button("Create Poll")
        
    if create_submitted:
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
                            # Prepare to clear inputs and show success after rerun
                            for k in ("new_poll_question", "new_poll_options", "new_poll_overwrite"):
                                if k in st.session_state:
                                    del st.session_state[k]
                            st.session_state["flash_poll_created"] = True
                            trigger_refresh()
                            st.rerun()
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
    
    # Statistics button
    if polls_data:
        if st.sidebar.button("📈 View Statistics", key="view_stats_btn"):
            st.session_state.show_stats = not st.session_state.get('show_stats', False)
    
    # Delete existing polls (no confirmation per request)
    if polls_data:
        with st.sidebar.expander("🗑️ Delete Polls"):
            delete_all = st.checkbox("Select all polls", key="delete_all_polls")
            if not delete_all:
                del_q = st.selectbox("Select a poll to delete:", options=list(polls_data.keys()), key="delete_select_question")
            action_label = "Delete All Polls" if delete_all else "Delete Selected Poll"
            if st.button(action_label, key="delete_poll_btn"):
                store = get_store()
                with store['lock']:
                    current_polls = load_polls().copy()
                    current_votes = load_user_votes().copy()
                    if delete_all:
                        # Clear all polls and all votes
                        current_polls.clear()
                        save_polls(current_polls)
                        for user_id in list(current_votes.keys()):
                            del current_votes[user_id]
                        save_user_votes(current_votes)
                    else:
                        if del_q in current_polls:
                            del current_polls[del_q]
                            save_polls(current_polls)
                        for user_id in list(current_votes.keys()):
                            if del_q in current_votes[user_id]:
                                del current_votes[user_id][del_q]
                            if len(current_votes[user_id]) == 0:
                                del current_votes[user_id]
                        save_user_votes(current_votes)
                st.success("All polls deleted!" if delete_all else "Poll deleted!")
                st.info("💡 Click 'Refresh All Users' to update everyone's screen")
                try:
                    trigger_refresh()
                except Exception:
                    pass
                st.rerun()
else:
    # Regular user cannot create polls
    st.sidebar.info("👤 Regular User Mode\n\nOnly admins can add or delete questions.")

# Show existing polls (available to both admin and users)
if polls_data:
    if st.session_state.user_role == "admin":
        # Show statistics and charts if button was clicked
        if st.session_state.get('show_stats', False):
            # Auto-refresh for admin to see real-time vote updates in statistics
            st_autorefresh(interval=1000, key="admin_stats_refresh")
            
            st.header("📈 Poll Statistics")
            
            # Calculate global Y-axis scale for all polls to ensure consistency
            global_max_votes = 0
            for question, votes in polls_data.items():
                vote_values = list(votes.values())
                poll_max = max(vote_values) if vote_values else 0
                global_max_votes = max(global_max_votes, poll_max)
            
            # Set consistent Y-axis scale for all charts
            y_max = max(10, global_max_votes + 1)
            
            # Display charts for each poll in statistics
            for idx, (question, votes) in enumerate(polls_data.items(), 1):
                st.write(f"**Poll {idx}**")
                total_votes = sum(votes.values())
                
                # Show chart in statistics
                if total_votes > 0:
                    chart_df = pd.DataFrame({
                        'Option': list(votes.keys()),
                        'Votes': list(votes.values()),
                    })
                    chart_df['Percent'] = (chart_df['Votes'] / total_votes) * 100.0
                    if _has_altair:
                        # Bar chart with vote counts inside bars using global Y-axis scale
                        bars = alt.Chart(chart_df).mark_bar(size=40).encode(
                            x=alt.X('Option:N', title='Options', axis=alt.Axis(labelPadding=5), scale=alt.Scale(paddingInner=0.2)),
                            y=alt.Y('Votes:Q', title='Vote Count', scale=alt.Scale(domain=[0, y_max])),
                            color=alt.Color('Option:N', legend=None),
                            tooltip=[
                                alt.Tooltip('Option:N', title='Option'),
                                alt.Tooltip('Votes:Q', title='Votes'),
                                alt.Tooltip('Percent:Q', title='Percent', format='.1f')
                            ]
                        ).properties(width=400, height=300)
                        
                        # Add text labels with vote counts inside bars
                        text = alt.Chart(chart_df).mark_text(
                            align='center',
                            baseline='middle',
                            dy=0,
                            fontSize=14,
                            fontWeight='bold',
                            color='white'
                        ).encode(
                            x=alt.X('Option:N'),
                            y=alt.Y('Votes:Q', scale=alt.Scale(domain=[0, y_max])),
                            text=alt.Text('Votes:Q')
                        )
                        
                        chart = bars + text
                        st.altair_chart(chart, use_container_width=True)
                    else:
                        # Fallback to a simple bar chart if Altair isn't available
                        # Note: Streamlit's bar_chart doesn't support custom y-axis limits
                        st.bar_chart(chart_df.set_index('Option'))
                    
                    # Show total votes for this poll
                    st.write(f"**Total votes:** {total_votes}")
                else:
                    st.caption("No votes yet to display a chart.")
                st.markdown("---")
        else:
            # Show message when statistics are not displayed
            st.info("Click the '📈 View Statistics' button in the sidebar to see detailed poll statistics and charts.")
    else:
        # Regular user view: Show questions one by one
        # Auto-refresh for users to see real-time vote updates
        st_autorefresh(interval=1000, key="polls_results_refresh")
        
        st.header("📊 Available Polls")
        
        # Get list of questions to determine current question
        question_list = list(polls_data.keys())
        
        if question_list:
            # Find the first unanswered question for this user
            current_question_idx = 0
            for idx, question in enumerate(question_list):
                user_has_voted = (st.session_state.user_id in user_votes_data and 
                                question in user_votes_data[st.session_state.user_id])
                if not user_has_voted:
                    current_question_idx = idx
                    break
            else:
                # All questions have been answered
                current_question_idx = len(question_list)
            
            # Show progress
            st.progress(current_question_idx / len(question_list))
            st.write(f"Progress: {current_question_idx}/{len(question_list)} questions answered")
            
            if current_question_idx < len(question_list):
                # Show current question
                question = question_list[current_question_idx]
                votes = polls_data[question]
                
                st.subheader(f"Question {current_question_idx + 1}: {question}")
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
                        # Allow voting
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
                            
                            st.success("Thanks for voting! Moving to next question...")
                            st.rerun()
                
                if user_has_voted:
                    st.write("✅ You have answered this question.")
                    if st.button("Continue to Next Question"):
                        st.rerun()
            else:
                # All questions completed
                st.success("🎉 Congratulations! You have completed all questions!")
                
                # Show summary of all answers
                st.subheader("📋 Your Answer Summary")
                for idx, question in enumerate(question_list, 1):
                    if st.session_state.user_id in user_votes_data and question in user_votes_data[st.session_state.user_id]:
                        user_answer = user_votes_data[st.session_state.user_id][question]
                        st.write(f"**Question {idx}:** {question}")
                        st.write(f"**Your Answer:** {user_answer}")
                        st.markdown("---")
        else:
            st.info("No polls available. Please wait for an admin to create polls.")
else:
    st.info("No polls available. " + 
           ("Create one from the admin controls in the sidebar." if st.session_state.user_role == "admin" 

            else "Please wait for an admin to create polls."))
