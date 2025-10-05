import streamlit as st

# Store poll data and user votes in session state
if "polls" not in st.session_state:
    st.session_state.polls = {}
if "user_votes" not in st.session_state:
    st.session_state.user_votes = {}
if "user_role" not in st.session_state:
    st.session_state.user_role = "user"

# Admin credentials (you can change these)
ADMIN_USERNAME = "SRMS"
ADMIN_PASSWORD = "SRMS@450"

st.title("🗳️ Dynamic Polling App")

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
                    st.session_state.polls[poll_question] = {opt: 0 for opt in options}
                    st.success("Poll created successfully!")
                    st.rerun()
                else:
                    st.error("Please provide at least 2 options.")
            else:
                st.error("Please enter a question and options.")
    
    # Delete existing polls
    if st.session_state.polls:
        with st.sidebar.expander("🗑️ Delete Polls"):
            st.write("Select polls to delete:")
            for question in list(st.session_state.polls.keys()):
                if st.button(f"Delete: {question[:30]}...", key=f"delete_{question}"):
                    # Remove poll and associated votes
                    del st.session_state.polls[question]
                    if question in st.session_state.user_votes:
                        del st.session_state.user_votes[question]
                    st.success(f"Poll deleted!")
                    st.rerun()
else:
    # Regular user cannot create polls
    st.sidebar.info("👤 Regular User Mode\n\nOnly admins can add or delete questions.")

# Show existing polls (available to both admin and users)
if st.session_state.polls:
    st.header("📊 Available Polls")
    for question, votes in st.session_state.polls.items():
        st.subheader(question)
        total_votes = sum(votes.values())
        
        # Check if user has already voted for this poll
        has_voted = question in st.session_state.user_votes

        # Display options with percentages
        for opt, count in votes.items():
            pct = (count / total_votes * 100) if total_votes > 0 else 0
            
            if has_voted:
                # Show results only, disable voting
                user_choice = st.session_state.user_votes[question]
                if opt == user_choice:
                    st.success(f"✓ {opt} ({pct:.1f}%) - Your vote")
                else:
                    st.info(f"{opt} ({pct:.1f}%)")
            else:
                # Allow voting (both admin and users can vote)
                if st.button(f"{opt} ({pct:.1f}%)", key=f"{question}_{opt}"):
                    st.session_state.polls[question][opt] += 1
                    st.session_state.user_votes[question] = opt
                    st.success("Thanks for voting!")
                    st.rerun()
        
        if has_voted:
            st.write("✅ You have already voted in this poll.")
        
        # Show total votes for this poll
        st.write(f"**Total votes for this poll:** {total_votes}")
        st.markdown("---")
else:
    st.info("No polls available. " + 
           ("Create one from the admin controls in the sidebar." if st.session_state.user_role == "admin" 
            else "Please wait for an admin to create polls."))

# Admin statistics (only for admin)
if st.session_state.user_role == "admin" and st.session_state.polls:
    with st.expander("📈 Admin Statistics"):
        st.write("**Poll Overview:**")
        for question, votes in st.session_state.polls.items():
            total_votes = sum(votes.values())
            st.write(f"- {question}: {total_votes} total votes")
            for opt, count in votes.items():
                pct = (count / total_votes * 100) if total_votes > 0 else 0
                st.write(f"  - {opt}: {count} votes ({pct:.1f}%)")
