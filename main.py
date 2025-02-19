import sqlite3

conn = sqlite3.connect('test.db')
cursor = conn.cursor()

# Creating the Contacts table with constraints
contacts_table = """
CREATE TABLE IF NOT EXISTS CONTACTS (
    NAME VARCHAR(100) NOT NULL,
    PHONE INTEGER UNIQUE NOT NULL CHECK(LENGTH(PHONE) = 10),
    EMAIL VARCHAR(100) UNIQUE NOT NULL,
    ADDRESS TEXT
);
"""
cursor.execute(contacts_table)

# Inserting data into CONTACTS
contacts_data = [
    ('ansh', 9876543210, 'vivekchoudhary75@gmail.com', '123, Lorem Ipsum Street, New York, NY 10001'),
    ('vivek', 9999701072, 'vivekchoudhary795@gmail.com', 'Delhi'),
    ('Akshit', 9999701034, 'vivekchoudhary565@gmail.com', 'Delhi'),
    ('Vivek Choudhary', 9999701071, 'vivekchoudhary789@gmail.com', 'Delhi 110088'),
    ('John Doe', 5551234123, 'john@example.com', '123 Main St'),
    ('ishani', 1234567890, 'john.new@example.com', '456 New St'),
    ('Vaibhav', 9999807097, 'vaibhav@gmail.com', 'jaipur'),
    ('mohit', 9920128977, 'mohit@gmail.com', 'mumbai')
]

cursor.executemany("INSERT INTO CONTACTS VALUES (?, ?, ?, ?)", contacts_data)

# Creating the Tasks table with constraints
tasks_table = """
CREATE TABLE IF NOT EXISTS TASKS (
    ID INTEGER PRIMARY KEY AUTOINCREMENT,
    TITLE VARCHAR(255) NOT NULL,
    DESCRIPTION TEXT,
    DUEDATE DATE NOT NULL,
    STATUS TEXT CHECK(STATUS IN ('on going', 'completed', 'not started')) NOT NULL DEFAULT 'on going',
    ASSIGNED_TO INTEGER NOT NULL CHECK(LENGTH(ASSIGNED_TO) = 10),
    FOREIGN KEY (ASSIGNED_TO) REFERENCES CONTACTS(PHONE)
);
"""
cursor.execute(tasks_table)

# Inserting data into TASKS
tasks_data = [
    ('Project Planning', 'Plan the initial phase of the project', '2025-03-01', 'on going', 9999701072),
    ('Database Setup', 'Set up the database schema and tables', '2025-03-05', 'not started', 9999701034),
    ('UI Design', 'Design the user interface for the application', '2025-03-10', 'on going', 9999807097),
    ('Testing', 'Perform unit and integration testing', '2025-03-15', 'not started', 9920128977),
    ('Deployment', 'Deploy the application to the production server', '2025-03-20', 'completed', 5551234123)
]

cursor.executemany("INSERT INTO TASKS (TITLE, DESCRIPTION, DUEDATE, STATUS, ASSIGNED_TO) VALUES (?, ?, ?, ?, ?)", tasks_data)

# Committing changes and closing connection
conn.commit()
conn.close()
