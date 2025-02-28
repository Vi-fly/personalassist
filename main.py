import os
import sqlite3
import streamlit as st
from datetime import datetime, time
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
import pandas as pd
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities import SQLDatabase
import json
from datetime import datetime, timedelta

# Load environment variables
load_dotenv('.env')

# Initialize ChatGroq
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
)

# Initialize session state for chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Initialize SQL Agent
try:
    db_agent = SQLDatabase.from_uri(
        "sqlite:///test.db",
        include_tables=['CONTACTS', 'TASKS'],
        sample_rows_in_table_info=2
    )
    
    llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model_name="llama-3.3-70b-versatile",
)
    agent_executor = create_sql_agent(
        llm=llm,
        db=db_agent,
        verbose=True,
        top_k=5,
        max_iterations=10
    )
except Exception as e:
    st.error(f"Failed to initialize SQL agent: {e}")

# Helper Functions
def generate_sql_query(prompt: str, action: str) -> str:
    """Generate SQL query based on selected action and user input."""
    system_prompts = {
        "add": (
            "You are an expert in generating SQL INSERT statements for a contacts database. "
            "The database has one table: CONTACTS.\n\n"
            "CONTACTS Table Structure:\n"
            "- ID (INTEGER, PRIMARY KEY, AUTOINCREMENT)\n"
            "- NAME (VARCHAR, NOT NULL)\n"
            "- PHONE (INTEGER, UNIQUE, NOT NULL, 10 digits)\n"
            "- EMAIL (VARCHAR, UNIQUE, NOT NULL)\n"
            "- ADDRESS (TEXT)\n\n"
            "Rules for INSERT Statements:\n"
            "1. For CONTACTS: INSERT INTO CONTACTS (NAME, PHONE, EMAIL, ADDRESS) VALUES (...);\n"
            "2. Phone numbers must be 10-digit integers.\n"
            "3. Use single quotes for string values.\n"
            "4. Return only the SQL query, no explanations.\n\n"
            "Examples:\n"
            "1. +/(Add new) contact: INSERT INTO CONTACTS (NAME, PHONE, EMAIL, ADDRESS) VALUES ('John Doe', 5551234567, 'john@email.com', '123 Main St');\n"
            "2. Add another contact: INSERT INTO CONTACTS (NAME, PHONE, EMAIL, ADDRESS) VALUES ('Jane Smith', 9876543210, 'jane@email.com', '456 Oak Ave');"
            "3. Add task: none"
        ),
        "view": (
            "You are an expert in generating SQL SELECT queries with JOINs for a contacts and tasks database.\n\n"
            "Rules for SELECT Statements:\n"
            "1. Always use JOINs when showing tasks to include assignee names.\n"
            "2. Use LOWER() for case-insensitive comparisons in WHERE clauses.\n"
            "3. Use proper table aliases (C for CONTACTS, T for TASKS).\n"
            "4. Return only the SQL query, no explanations.\n\n"
            "Examples:\n"
            "1. Show all tasks: SELECT T.ID, T.TITLE, T.DESCRIPTION, T.CATEGORY, T.PRIORITY, T.STATUS, C.NAME AS ASSIGNEE FROM TASKS T LEFT JOIN CONTACTS C ON T.ASSIGNED_TO = C.ID;\n"
            "2. Find contacts from Delhi: SELECT * FROM CONTACTS WHERE LOWER(ADDRESS) LIKE '%delhi%';\n"
            "3. Show ongoing tasks for John: SELECT T.ID, T.TITLE, T.DEADLINE FROM TASKS T JOIN CONTACTS C ON T.ASSIGNED_TO = C.ID WHERE LOWER(C.NAME) = LOWER('John Doe') AND T.STATUS = 'In Progress';"
            "4. Display task 1: SELECT T.* FROM TASKS T JOIN CONTACTS C ON T.ASSIGNED_TO = C.ID WHERE T.ID = 1;"
        ),
        "update": (
            "You are an expert in generating SQL UPDATE statements for a contacts and tasks database.\n\n"
            "Rules for UPDATE Statements:\n"
            "1. For contacts, use ID as the identifier in WHERE clause.\n"
            "2. For tasks, use ID as the identifier in WHERE clause.\n"
            "3. Use single quotes for string values.\n"
            "4. Include only one SET clause per statement.\n"
            "5. Return only the SQL query, no explanations.\n\n"
            "Examples:\n"
            "1. Update contact email: UPDATE CONTACTS SET EMAIL = 'new@email.com' WHERE ID = 2;\n"
            "2. Mark task as completed: UPDATE TASKS SET STATUS = 'Completed' WHERE ID = 5;\n"
            "3. Change task deadline: UPDATE TASKS SET DEADLINE = '2024-12-31 23:59' WHERE ID = 3;\n"
            "4. Reassign task: UPDATE TASKS SET ASSIGNED_TO = (SELECT ID FROM CONTACTS WHERE NAME = 'vivek') WHERE ID = 10;\n"
            "5. Update contact based on name: UPDATE CONTACTS SET ADDRESS = 'New Address' WHERE LOWER(NAME) = LOWER('John Doe');\n"
            "6. Update task status based on title: UPDATE TASKS SET STATUS = 'Reviewed & Approved' WHERE LOWER(TITLE) = LOWER('Project Planning');"
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

def execute_query(sql_query: str, params=None):
    try:
        conn = sqlite3.connect('test.db', check_same_thread=False)
        cur = conn.cursor()
        
        if sql_query.strip().upper().startswith("SELECT"):
            cur.execute(sql_query, params or ())
            rows = cur.fetchall()
            columns = [desc[0] for desc in cur.description] if cur.description else []
            return columns, rows
        else:
            cur.execute(sql_query, params or ())
            affected_rows = cur.rowcount
            conn.commit()
            return None, affected_rows
            
    except sqlite3.Error as e:
        st.error(f"SQL error: {e}")
        return None, None
    finally:
        if conn:
            conn.close()

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

def parse_task_parameters(prompt: str) -> dict:
    """Extract task parameters from natural language input using LLM."""
    system_prompt = """Extract task parameters from user input. Return JSON with:
    - title: string
    - description: string
    - category: string (default: Work)
    - priority: string (default: Medium)
    - deadline: string (date/time in natural language)
    - assigned_to: string (contact name)
    - status: string (default: Not Started)
    Ensure valid JSON format with double quotes. Example output: 
    {"title": "Task", "priority": "High", "deadline": "tomorrow", "assigned_to": "John"}
    "input": "Need to finish client proposal ASAP",
  "output": {
    "title": "Complete Client Proposal",
    "priority": "High",
    "status": "In Progress"}}"""
    
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = llm.invoke(messages)
        parsed = json.loads(response.content.strip())
        # Ensure essential fields exist
        return {
            "title": parsed.get("title", ""),
            "priority": parsed.get("priority", "Medium"),
            "deadline": parsed.get("deadline", ""),
            "assigned_to": parsed.get("assigned_to", ""),
            "category": parsed.get("category", "Work"),
            "status": parsed.get("status", "Not Started"),
            "description": parsed.get("description", "")
        }
    except Exception as e:
        st.error(f"Parameter parsing error: {str(e)}")
        return {}

# Streamlit UI Setup
st.set_page_config(page_title="DB Manager", layout="wide")
st.sidebar.title("Navigation")

# Modify the page selection section
if 'target_page' not in st.session_state:
    st.session_state.target_page = "🏠 Home"

# Override page selection if redirected
if st.session_state.target_page != "🏠 Home":
    page = st.session_state.target_page
else:
    page = st.sidebar.radio("Go to", ["🏠 Home", "📝 New Contact", "✅ New Task", "🔍 Deep Search"])
# Home Page
if page == "🏠 Home":
    
    if 'task_status' in st.session_state:
        st.success(st.session_state.task_status)
        del st.session_state.task_status
    
    st.header("💬 Personal Chat Assistant")

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Main chat logic
    if prompt := st.chat_input("What would you like to do?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        if "add task" in prompt.lower() or "create task" in prompt.lower():
            # Parse parameters and redirect to task page
            params = parse_task_parameters(prompt)
            st.session_state.prefill_task = params
            st.session_state.target_page = "✅ New Task"
            st.rerun()
        else:
            # Classify user intent
            action_type = classify_action(prompt)
        
            # Generate SQL query based on detected action
            sql_query = generate_sql_query(prompt, action_type)
        
            if sql_query:
                # st.session_state.messages.append({"role": "assistant", "content": f"Generated SQL:\n```sql\n{sql_query}\n```"})  # Debugging
                
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

# New Contact Page
elif page == "📝 New Contact":
    st.header("📝 Create New Contact")
    
    with st.form("contact_form", clear_on_submit=True):
        cols = st.columns(2)
        with cols[0]:
            name = st.text_input("Full Name*", help="Required field")
            phone = st.text_input("Phone Number*", max_chars=10, help="10 digits without country code")
        with cols[1]:
            email = st.text_input("Email Address*")
            address = st.text_input("Physical Address")
        
        submitted = st.form_submit_button("💾 Save Contact")
        
        if submitted:
            if not all([name, phone, email]):
                st.error("Please fill required fields (*)")
            elif not phone.isdigit() or len(phone) != 10:
                st.error("Phone must be 10 digits")
            else:
                try:
                    sql = """INSERT INTO CONTACTS (NAME, PHONE, EMAIL, ADDRESS) VALUES (?, ?, ?, ?)"""
                    params = (name.strip(), int(phone), email.strip(), address.strip())
                    _, affected = execute_query(sql, params)
                    if affected:
                        st.success("Contact created successfully!")
                        st.balloons()
                    else:
                        st.error("Error creating contact")
                except Exception as e:
                    st.error(f"Database error: {str(e)}")

# New Task Page
elif page == "✅ New Task":
    st.header("✅ Create New Task")
    
    # st.write("Debug Prefill:", st.session_state.get('prefill_task', {}))
    
    # Get contacts for assignment
    conn = sqlite3.connect('test.db', check_same_thread=False)
    cur = conn.cursor()
    cur.execute("SELECT ID, NAME FROM CONTACTS ORDER BY NAME")
    contacts = cur.fetchall()
    contact_names = [name for _, name in contacts]
    contact_dict = {name: id for id, name in contacts}
    conn.close()
    
    # Check for prefill parameters
    prefill = st.session_state.get('prefill_task', {})
    
    with st.form("task_form", clear_on_submit=True):
        # Basic Info
        col1, col2 = st.columns([2, 1])
        with col1:
            title = st.text_input("Task Title*", value=prefill.get('title', ''))
            description = st.text_area("Detailed Description", 
                                      value=prefill.get('description', ''),
                                      height=100)
        with col2:
            # Handle natural language deadlines
            deadline_input = prefill.get('deadline', '')
            default_date = datetime.today()

            if deadline_input:
                try:
                    # Use simple natural date parsing
                    if 'tomorrow' in deadline_input.lower():
                        default_date += timedelta(days=1)
                    elif 'next week' in deadline_input.lower():
                        default_date += timedelta(weeks=1)
                    elif 'in 2 days' in deadline_input.lower():
                        default_date += timedelta(days=2)
                except:
                    pass

            
            deadline_date = st.date_input("Deadline Date*", 
                                        min_value=datetime.today(),
                                        value=default_date)
            deadline_time = st.time_input("Deadline Time*", datetime.now().time())
        
        # Task Metadata
        st.subheader("Task Details", divider="rainbow")
        cols = st.columns(3)
        with cols[0]:
            category = st.selectbox("Category", ["Work", "Personal", "Project", "Other"],
                                  index=["Work", "Personal", "Project", "Other"].index(
                                      prefill.get('category', 'Work')))
            priority = st.select_slider("Priority*", options=["Low", "Medium", "High"],
                                      value=prefill.get('priority', 'Medium'))
            expected_outcome = st.text_input("Expected Outcome", 
                                           value=prefill.get('expected_outcome', ''),
                                           placeholder="e.g., Complete project setup")
        with cols[1]:
            # Safe index handling for assigned_to
            assigned_to_index = 0
            if prefill.get('assigned_to'):
                # Case-insensitive match
                lower_names = [name.lower() for name in contact_names]
                try:
                    assigned_to_index = lower_names.index(prefill['assigned_to'].lower())
                except ValueError:
                    assigned_to_index = 0
            
            assigned_to = st.selectbox("Assign To*", 
                                     options=contact_names,
                                     index=assigned_to_index)
            
            # Safe status index
            status_index = ["Not Started", "In Progress", "On Hold", "Completed"].index(
                prefill.get('status', 'Not Started'))
            status = st.selectbox("Status*", 
                                ["Not Started", "In Progress", "On Hold", "Completed"],
                                index=status_index)
            
            # Safe support contact index
            support_index = 0
            if prefill.get('support_contact'):
                try:
                    support_index = contact_names.index(prefill['support_contact'])
                except ValueError:
                    support_index = 0
            
            support_contact = st.selectbox("Support Contact", 
                                          options=contact_names,
                                          index=support_index)
        with cols[2]:
            estimated_time = st.text_input("Estimated Time", 
                                         value=prefill.get('estimated_time', ''),
                                         placeholder="e.g., 2 hours")
            required_resources = st.text_input("Required Resources",
                                             value=prefill.get('required_resources', ''))
        
        # Additional Details
        st.subheader("Additional Information", divider="rainbow")
        dependencies = st.text_area("Dependencies", value=prefill.get('dependencies', ''))
        instructions = st.text_area("Instructions", 
                                   value=prefill.get('instructions', ''),
                                   placeholder="Detailed instructions for the task")
        review_process = st.text_area("Review Process", 
                                    value=prefill.get('review_process', ''),
                                    placeholder="Steps for reviewing the task")
        performance_metrics = st.text_area("Success Metrics",
                                         value=prefill.get('performance_metrics', ''))
        notes = st.text_area("Internal Notes", value=prefill.get('notes', ''))
        
        # Proper submit button
        submitted = st.form_submit_button("🚀 Create Task")
        
        if submitted:
            if not all([title, priority, assigned_to, status, deadline_date]):
                st.error("Please fill required fields (*)")
            else:
                try:
                    deadline = datetime.combine(deadline_date, deadline_time).strftime("%Y-%m-%d %H:%M:%S")
                    sql = """INSERT INTO TASKS (
                        TITLE, DESCRIPTION, CATEGORY, PRIORITY, EXPECTED_OUTCOME,
                        DEADLINE, ASSIGNED_TO, DEPENDENCIES, REQUIRED_RESOURCES,
                        ESTIMATED_TIME, INSTRUCTIONS, REVIEW_PROCESS, PERFORMANCE_METRICS,
                        SUPPORT_CONTACT, NOTES, STATUS
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
                    
                    params = (
                        title.strip(),
                        description.strip(),
                        category,
                        priority,
                        expected_outcome.strip(),
                        deadline,
                        contact_dict[assigned_to],
                        dependencies.strip(),
                        required_resources.strip(),
                        estimated_time.strip(),
                        instructions.strip(),
                        review_process.strip(),
                        performance_metrics.strip(),
                        contact_dict.get(support_contact, None),
                        notes.strip(),
                        status
                    )
                    
                    _, affected = execute_query(sql, params)
                    if affected:
                        st.session_state.task_status = f"✅ Task '{title.strip()}' created successfully!"
                        st.session_state.target_page = "🏠 Home"
                        if 'prefill_task' in st.session_state:
                            del st.session_state.prefill_task
                        st.rerun()
                    else:
                        st.error("Error creating task")
                except Exception as e:
                    st.error(f"Database error: {str(e)}")                   

# Deep Search Page
elif page == "🔍 Deep Search":
    st.header("🔍 Deep Search with Natural Language")
    
    with st.form("deep_search_form"):
        query = st.text_area("Ask your data question:", 
                           placeholder="E.g.: Show me all high priority tasks assigned to Vivek due this week")
        
        analyze_cols = st.columns([3, 1])
        with analyze_cols[1]:
            st.markdown("### Query Tips:")
            st.markdown("""
            - Use specific filters: "tasks from last week"
            - Combine criteria: "contacts in Mumbai with email @gmail"
            - Request analysis: "average task duration by priority"
            """)
        
        submitted = st.form_submit_button("🔎 Analyze")
        
        if submitted:
            with st.spinner("Analyzing your query..."):
                try:
                    # Invoke the SQL agent
                    response = agent_executor.invoke({"input": query})
                    
                    # Display the results
                    st.subheader("Analysis Results", divider="rainbow")
                    
                    # Check if the response contains the expected output
                    if "output" in response:
                        st.markdown(f"**Result:**\n{response['output']}")
                        
                        # If the query is a SELECT, try to fetch and display the results
                        if "SELECT" in response['output'].upper():
                            conn = sqlite3.connect('test.db', check_same_thread=False)
                            cur = conn.cursor()
                            cur.execute(response['output'])
                            rows = cur.fetchall()
                            columns = [desc[0] for desc in cur.description]
                            conn.close()
                            
                            if rows:
                                df = pd.DataFrame(rows, columns=columns)
                                st.dataframe(df)
                                st.download_button(
                                    "📥 Export Results",
                                    df.to_csv(index=False),
                                    "results.csv",
                                    mime="text/csv"
                                )
                            else:
                                st.warning("No results found.")
                    else:
                        st.error("The agent did not return a valid response.")
                    
                    st.success("Analysis completed!")
                
                except Exception as e:
                    st.error(f"Search failed: {str(e)}")
                    st.markdown("**Troubleshooting Tips:**")
                    st.markdown("""
                    - Try being more specific with names/dates
                    - Use exact field names you see in forms
                    - Check for typos in contact/task names
                    """)

# Sidebar Examples Guide
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

if st.button("Push Database Changes to GitHub"):
    print('hello')
