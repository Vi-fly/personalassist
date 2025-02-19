import os
import sqlite3
import subprocess
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

# Load environment variables
load_dotenv('.env')

# Database
DB_PATH='test.db'

# Initialize ChatGroq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

def generate_sql_query(prompt: str, action: str) -> str:
    """Generate SQL query based on selected action and user input."""
    system_prompts = {
        "add": (
            "You are an expert in generating SQL INSERT statements for a contacts and tasks database. "
            "The database has two tables: CONTACTS and TASKS.\n\n"
            
            "CONTACTS Table Structure:\n"
            "- NAME (VARCHAR, NOT NULL)\n"
            "- PHONE (INTEGER, PRIMARY KEY, UNIQUE, NOT NULL, 10 digits)\n"
            "- EMAIL (VARCHAR, UNIQUE, NOT NULL)\n"
            "- ADDRESS (TEXT)\n\n"
            
            "TASKS Table Structure:\n"
            "- ID (INTEGER, PRIMARY KEY, AUTOINCREMENT)\n"
            "- TITLE (VARCHAR, NOT NULL)\n"
            "- DESCRIPTION (TEXT)\n"
            "- DUEDATE (DATE, NOT NULL)\n"
            "- STATUS (TEXT, CHECK: 'on going', 'completed', 'not started', DEFAULT: 'on going')\n"
            "- ASSIGNED_TO (INTEGER, FOREIGN KEY REFERENCES CONTACTS(PHONE), 10 digits)\n\n"
            
            "Rules for INSERT Statements:\n"
            "1. For CONTACTS: INSERT INTO CONTACTS (NAME, PHONE, EMAIL, ADDRESS) VALUES (...)\n"
            "2. For TASKS: INSERT INTO TASKS (TITLE, DESCRIPTION, DUEDATE, STATUS, ASSIGNED_TO) VALUES (...)\n"
            "3. Phone numbers must be 10-digit integers\n"
            "4. STATUS defaults to 'on going' if not specified\n"
            "5. Use single quotes for string values\n"
            "6. Return only the SQL query, no explanations\n\n"
            
            "Examples:\n"
            "1. Add new contact: INSERT INTO CONTACTS (NAME, PHONE, EMAIL, ADDRESS) VALUES ('John Doe', 5551234567, 'john@email.com', 'New York');\n"
            "2. Add new task assign it to ishani: INSERT INTO TASKS (TITLE, DESCRIPTION, DUEDATE, ASSIGNED_TO) VALUES ('Project Setup', 'Initialize project repository', '2024-12-31', (SELECT PHONE FROM CONTACTS WHERE NAME = 'ishani'));"
        ),
        "view": (
            "You are an expert in generating SQL SELECT queries with JOINs for a contacts and tasks database. "
            "The database has two tables: CONTACTS and TASKS.\n\n"
            
            "CONTACTS Table Structure:\n"
            "- NAME (VARCHAR)\n"
            "- PHONE (INTEGER, PRIMARY KEY)\n"
            "- EMAIL (VARCHAR)\n"
            "- ADDRESS (TEXT)\n\n"
            
            "TASKS Table Structure:\n"
            "- ID (INTEGER, PRIMARY KEY)\n"
            "- TITLE (VARCHAR)\n"
            "- DESCRIPTION (TEXT)\n"
            "- DUEDATE (DATE)\n"
            "- STATUS (TEXT)\n"
            "- ASSIGNED_TO (INTEGER, FOREIGN KEY REFERENCES CONTACTS(PHONE))\n\n"
            
            "Rules for SELECT Statements:\n"
            "1. Always use JOINs when showing tasks to include assignee names\n"
            "2. Use LOWER() for case-insensitive comparisons in WHERE clauses\n"
            "3. Use proper table aliases (C for CONTACTS, T for TASKS)\n"
            "4. Return only the SQL query, no explanations\n\n"
            
            "Examples:\n"
            "1. Show all tasks: SELECT T.ID, T.TITLE, T.DESCRIPTION, T.DUEDATE, T.STATUS, C.NAME AS ASSIGNEE FROM TASKS T LEFT JOIN CONTACTS C ON T.ASSIGNED_TO = C.PHONE;\n"
            "2. Find contacts from Delhi: SELECT * FROM CONTACTS WHERE LOWER(ADDRESS) LIKE '%delhi%';\n"
            "3. Show ongoing tasks for John: SELECT T.ID, T.TITLE, T.DUEDATE FROM TASKS T JOIN CONTACTS C ON T.ASSIGNED_TO = C.PHONE WHERE LOWER(C.NAME) = LOWER('John Doe') AND T.STATUS = 'on going';"
        ),
        "update": (
            "You are an expert in generating SQL UPDATE statements for a contacts and tasks database. "
            "The database has two tables: CONTACTS and TASKS.\n\n"
            
            "Rules for UPDATE Statements:\n"
            "1. For contacts, use PHONE as the identifier in WHERE clause\n"
            "2. For tasks, use ID as the identifier in WHERE clause\n"
            "3. Use single quotes for string values\n"
            "4. Include only one SET clause per statement\n"
            "5. Return only the SQL query, no explanations\n\n"
            
            "Examples:\n"
            "1. Update contact email: UPDATE CONTACTS SET EMAIL = 'new@email.com' WHERE PHONE = 5551234567;\n"
            "2. Mark task as completed: UPDATE TASKS SET STATUS = 'completed' WHERE ID = 5;\n"
            "3. Change task due date: UPDATE TASKS SET DUEDATE = '2024-12-31' WHERE ID = 3;\n"
            "4. UPDATE TASKS SET ASSIGNED_TO = (SELECT PHONE FROM CONTACTS WHERE NAME = 'vivek') WHERE ID = 10;"
        )
    }
    
    messages = [
        SystemMessage(content=system_prompts[action]),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        sql_query = response.content.strip()
        
        # Clean markdown formatting if present
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:-3].strip()
        elif sql_query.startswith("```"):
            sql_query = sql_query[3:-3].strip()
            
        return sql_query
    except Exception as e:
        st.error(f"Error generating SQL query: {e}")
        return ""
    

def execute_query(sql_query: str):
    """Execute SQL query and return results."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)  # Ensure proper handling
        cur = conn.cursor()
        
        # Check if query is SELECT
        if sql_query.strip().upper().startswith("SELECT"):
            cur.execute(sql_query)
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
            cur.close()
            conn.close()
            return columns, rows  # Return fetched data
        
        else:  # For INSERT, UPDATE, DELETE
            cur.execute(sql_query)
            affected_rows = cur.rowcount  # Store before closing
            conn.commit()  # Ensure changes are committed
            cur.close()
            conn.close()
            return None, affected_rows  # Return number of affected rows
            
    except sqlite3.Error as e:
        st.error(f"SQL error: {e}")
        return None, None


def classify_action(prompt: str) -> str:
    """Classify user intent into add/view/update actions using LLM."""
    system_prompt = (
        "Classify the user's database request into one of: add, view, or update. "
        "Respond ONLY with the action keyword. Rules:\n"
        "- 'add' for creating new records (insert)\n"
        "- 'view' for read operations (select)\n"
        "- 'update' for modifying existing records\n"
        "Examples:\n"
        "User: Add new contact -> add\n"
        "User: Show tasks -> view\n"
        "User: Change email -> update\n"
        "User: List contacts in NY -> view\n"
        "User: Mark task 5 completed -> update"
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        action = response.content.strip().lower()
        return action if action in ['add', 'view', 'update'] else 'view'
    except Exception as e:
        st.error(f"Error classifying action: {e}")
        return 'view'

def format_response(action: str, sql_query: str, rowcount: int = None, data: tuple = None):
    """Format the response based on the action."""
    responses = {
        "add": lambda: f"✅ Successfully added {rowcount} record(s)",
        "update": lambda: f"✅ Successfully updated {rowcount} record(s)",
        "view": lambda: (f"🔍 Found {len(data[1])} results:", data)
    }
    return responses[action]()

def push_db_to_github():
    """Commit & push the updated database to GitHub."""
    try:
        if not os.path.exists(DB_PATH):
            st.error("❌ No database file found.")
            return

        # Check if there are changes
        result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        if not result.stdout.strip():
            st.sidebar.success("✅ No changes to commit.")
            return

        subprocess.run(["git", "add", DB_PATH], check=True)
        subprocess.run(["git", "commit", "-m", "Manual update database"], check=True)
        subprocess.run(["git", "push"], check=True)
        st.sidebar.success("✅ Database changes pushed to GitHub successfully!")
    except Exception as e:
        st.sidebar.error(f"❌ Failed to push to GitHub: {e}")

# Streamlit UI Setup
st.set_page_config(page_title="Personal Chat Assistant", layout="wide")
st.header("💬 Personal Chat Assistant")

# Display chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# # Action selection
# action = st.sidebar.selectbox("Choose Action", ["Add Data", "View Data", "Update Data"])

# Main chat logic
if prompt := st.chat_input("What would you like to do?"):
    # Add user message to chat history
    st.session_state.messages.append({"role": "user", "content": prompt})
    
    # Classify user intent
    action_type = classify_action(prompt)
    
    # Generate SQL query based on detected action
    sql_query = generate_sql_query(prompt, action_type)
    
    if sql_query:
        
        #st.session_state.messages.append({"role": "assistant", "content": f"Generated SQL:\n```sql\n{sql_query}\n```"})  #debuging 
        
        # Execute query
        columns, result = execute_query(sql_query)
        
        # Format response
        if action_type == "view" and columns:
            response_text = format_response(action_type, sql_query, data=(columns, result))
            df = pd.DataFrame(result, columns=columns)
            response = f"{response_text[0]}\n\n{df.to_markdown(index=False)}"
        elif action_type in ["add", "update"]:
            response = format_response(action_type, sql_query, rowcount=result)
        else:
            response = "❌ No results found or invalid query"
        
        # Add assistant response
        st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

# Action-specific guidance
st.sidebar.markdown("### Examples Guide")
st.sidebar.markdown("""
**Add Data Examples:**
- "Add new contact: John, 5551234567, john@email.com, London"
- "Create task: Project Setup, Initialize repo, 2024-12-31, 5551234567"

**View Data Examples:**
- "Show contacts from Delhi"
- "List ongoing tasks for John"
- "Display completed tasks"

**Update Data Examples:**
- "Change John's email to new@email.com"
- "Mark task 5 as completed"
- "Update task 3's due date to tomorrow"
""")

if st.sidebar.button("Push Database Changes to GitHub"):
    push_db_to_github()

