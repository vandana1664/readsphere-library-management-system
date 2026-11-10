# ReadSphere – Next Gen Library Management System

ReadSphere is a web-based Library Management System developed using Python Flask and Oracle Database. It provides separate interfaces for students and librarians to manage library activities efficiently.

## Features

### Student
- Student registration and login
- Explore and search books
- View book details and availability
- Borrow available books
- View borrowed books in My Shelf
- Return borrowed books
- View borrowing status

### Librarian
- Secure librarian login
- Dashboard with library statistics
- Add, edit, delete and search books
- Manage student records
- Issue and return books
- View borrowing records
- Fine management

### Additional Features
- Role-based access control
- Password hashing
- Database-driven operations
- Borrowing eligibility checks
- Automatic due-date calculation
- Fine calculation for overdue books

## Technologies Used

| Component | Technology |
|---|---|
| Backend | Python, Flask |
| Frontend | HTML5, CSS3 |
| Database | Oracle Database |
| Database Driver | python-oracledb |
| Authentication | Flask Sessions, Werkzeug |
| Deployment Server | Gunicorn |

## Project Structure

```text
readsphere-library-management-system/
│
├── app.py
├── requirements.txt
├── Procfile
├── .gitignore
│
├── templates/
│   ├── login.html
│   ├── register.html
│   ├── index.html
│   ├── student_home.html
│   └── other HTML templates
│
└── static/
    └── css/
        └── style.css
```

## Installation and Setup

### 1. Clone the repository

```bash
git clone https://github.com/vandana1664/readsphere-library-management-system.git
```

### 2. Navigate to the project directory

```bash
cd readsphere-library-management-system
```

### 3. Create a virtual environment

```bash
python -m venv .venv
```

### 4. Activate the virtual environment

Windows:

```bash
.venv\Scripts\activate
```

### 5. Install dependencies

```bash
pip install -r requirements.txt
```

### 6. Configure environment variables

Set the following environment variables before running the application:

- `FLASK_SECRET_KEY`
- `DB_USER`
- `DB_PASSWORD`
- `DB_DSN`

Use your own Oracle database credentials. Never commit passwords or secret keys to GitHub.

### 7. Run the application

```bash
python app.py
```

Open your browser and visit:

```text
http://127.0.0.1:5000
```

## Database Requirements

The application requires an Oracle Database containing the library tables, sequences, stored procedures and required constraints.

Configure the database connection using environment variables.

## Future Enhancements

- Cloud database integration
- Public cloud deployment
- Improved reporting and analytics
- Additional library management features

## Author

**Vandana Prajapati**

GitHub: [vandana1664](https://github.com/vandana1664)

---

*ReadSphere – Making Library Management Smarter and Simpler.*
