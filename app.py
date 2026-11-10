import os
from datetime import datetime, timedelta, date
from functools import wraps

import oracledb
from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash
)


# ================= APPLICATION CONFIGURATION =================

app = Flask(__name__)

app.secret_key = os.environ.get("FLASK_SECRET_KEY")

if not app.secret_key:
    raise RuntimeError(
        "FLASK_SECRET_KEY environment variable is not set."
    )


# ================= DATABASE CONNECTION =================

def get_connection():
    return oracledb.connect(
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        dsn=os.environ.get(
            "DB_DSN",
            "localhost:1521/FREEPDB1"
        )
    )


# ================= ROLE-BASED SECURITY =================

def librarian_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "librarian":

            if session.get("role") == "student":
                return redirect(url_for("student_home"))

            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


def student_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "student":

            if session.get("role") == "librarian":
                return redirect(url_for("home"))

            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


# ================= MAIN STARTING PAGE =================

@app.route("/")
def index():
    return redirect(url_for("login"))


# ================= LIBRARIAN DASHBOARD =================

@app.route("/home")
@librarian_required
def home():

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM SYS.BOOK")
        total_books = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM SYS.STUDENT")
        total_students = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM SYS.E_BORROW")
        total_borrows = cursor.fetchone()[0]

        cursor.execute("""
            SELECT
                ISBN_NO,
                BOOK_NAME,
                AUTHOR,
                PUBLISHER,
                PRICE
            FROM SYS.BOOK
            ORDER BY BOOK_NAME
        """)

        books = cursor.fetchmany(5)

        return render_template(
            "index.html",
            total_books=total_books,
            total_students=total_students,
            total_borrows=total_borrows,
            books=books
        )

    finally:
        cursor.close()
        conn.close()


# ================= BOOK MANAGEMENT =================

@app.route("/books")
@librarian_required
def books():

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if search:
            cursor.execute("""
                SELECT
                    ISBN_NO,
                    BOOK_NAME,
                    AUTHOR,
                    PUBLISHER,
                    PRICE,
                    PUBLICATION_YEAR,
                    EDITION
                FROM SYS.BOOK
                WHERE LOWER(ISBN_NO) LIKE :s
                   OR LOWER(BOOK_NAME) LIKE :s
                   OR LOWER(AUTHOR) LIKE :s
                ORDER BY BOOK_NAME
            """, {"s": f"%{search.lower()}%"})

        else:
            cursor.execute("""
                SELECT
                    ISBN_NO,
                    BOOK_NAME,
                    AUTHOR,
                    PUBLISHER,
                    PRICE,
                    PUBLICATION_YEAR,
                    EDITION
                FROM SYS.BOOK
                ORDER BY BOOK_NAME
            """)

        book_list = cursor.fetchall()

        return render_template(
            "books.html",
            books=book_list,
            search=search
        )

    finally:
        cursor.close()
        conn.close()


# ================= ADD BOOK =================

@app.route("/books/add", methods=["GET", "POST"])
@librarian_required
def add_book():

    if request.method == "POST":

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO SYS.BOOK
                (
                    ISBN_NO,
                    BOOK_NAME,
                    AUTHOR,
                    PUBLISHER,
                    PRICE,
                    PUBLICATION_YEAR,
                    EDITION
                )
                VALUES
                (
                    :isbn,
                    :book_name,
                    :author,
                    :publisher,
                    :price,
                    :pub_year,
                    :edition
                )
            """, {
                "isbn": request.form["isbn"].strip(),
                "book_name": request.form["book_name"].strip(),
                "author": request.form["author"].strip(),
                "publisher": request.form["publisher"].strip(),
                "price": float(request.form["price"]),
                "pub_year": int(request.form["year"]),
                "edition": request.form["edition"].strip()
            })

            conn.commit()

            flash("Book added successfully!", "success")
            return redirect(url_for("books"))

        except (oracledb.Error, ValueError, TypeError) as e:
            conn.rollback()

            return render_template(
                "add_book.html",
                error=str(e)
            )

        finally:
            cursor.close()
            conn.close()

    return render_template("add_book.html")


# ================= EDIT BOOK =================

@app.route("/books/edit/<isbn>", methods=["GET", "POST"])
@librarian_required
def edit_book(isbn):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if request.method == "POST":

            try:
                cursor.execute("""
                    UPDATE SYS.BOOK
                    SET
                        BOOK_NAME = :book_name,
                        AUTHOR = :author,
                        PUBLISHER = :publisher,
                        PRICE = :price,
                        PUBLICATION_YEAR = :pub_year,
                        EDITION = :edition
                    WHERE ISBN_NO = :isbn
                """, {
                    "book_name": request.form["book_name"].strip(),
                    "author": request.form["author"].strip(),
                    "publisher": request.form["publisher"].strip(),
                    "price": float(request.form["price"]),
                    "pub_year": int(request.form["year"]),
                    "edition": request.form["edition"].strip(),
                    "isbn": isbn
                })

                if cursor.rowcount == 0:
                    conn.rollback()
                    return "Book not found.", 404

                conn.commit()

                flash("Book updated successfully!", "success")
                return redirect(url_for("books"))

            except (oracledb.Error, ValueError, TypeError) as e:
                conn.rollback()

                cursor.execute("""
                    SELECT
                        ISBN_NO,
                        BOOK_NAME,
                        AUTHOR,
                        PUBLISHER,
                        PRICE,
                        PUBLICATION_YEAR,
                        EDITION
                    FROM SYS.BOOK
                    WHERE ISBN_NO = :isbn
                """, {"isbn": isbn})

                book = cursor.fetchone()

                if book is None:
                    return "Book not found.", 404

                return render_template(
                    "edit_book.html",
                    book=book,
                    error=str(e)
                )

        cursor.execute("""
            SELECT
                ISBN_NO,
                BOOK_NAME,
                AUTHOR,
                PUBLISHER,
                PRICE,
                PUBLICATION_YEAR,
                EDITION
            FROM SYS.BOOK
            WHERE ISBN_NO = :isbn
        """, {"isbn": isbn})

        book = cursor.fetchone()

        if book is None:
            return "Book not found.", 404

        return render_template(
            "edit_book.html",
            book=book
        )

    finally:
        cursor.close()
        conn.close()


# ================= DELETE BOOK =================

@app.route("/books/delete/<isbn>", methods=["POST"])
@librarian_required
def delete_book(isbn):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM SYS.BOOK
            WHERE ISBN_NO = :isbn
        """, {"isbn": isbn})

        if cursor.rowcount == 0:
            conn.rollback()
            return "Book not found.", 404

        conn.commit()

        flash("Book deleted successfully!", "success")
        return redirect(url_for("books"))

    except oracledb.Error:
        conn.rollback()

        return (
            "Cannot delete this book because it may be linked "
            "to another database record.",
            409
        )

    finally:
        cursor.close()
        conn.close()
        # ================= STUDENT MANAGEMENT =================

@app.route("/students")
@librarian_required
def students():

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if search:
            cursor.execute("""
                SELECT
                    ENROLL_ID,
                    CONTACT_NO,
                    USER_ID,
                    DEPT_NAME
                FROM SYS.STUDENT
                WHERE LOWER(ENROLL_ID) LIKE :s
                   OR TO_CHAR(CONTACT_NO) LIKE :s
                   OR TO_CHAR(USER_ID) LIKE :s
                   OR LOWER(DEPT_NAME) LIKE :s
                ORDER BY ENROLL_ID
            """, {"s": f"%{search.lower()}%"})

        else:
            cursor.execute("""
                SELECT
                    ENROLL_ID,
                    CONTACT_NO,
                    USER_ID,
                    DEPT_NAME
                FROM SYS.STUDENT
                ORDER BY ENROLL_ID
            """)

        student_list = cursor.fetchall()

        return render_template(
            "students.html",
            students=student_list,
            search=search
        )

    finally:
        cursor.close()
        conn.close()


# ================= ADD STUDENT =================

@app.route("/students/add", methods=["GET", "POST"])
@librarian_required
def add_student():

    if request.method == "POST":

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO SYS.STUDENT
                (
                    ENROLL_ID,
                    CONTACT_NO,
                    USER_ID,
                    DEPT_NAME
                )
                VALUES
                (
                    :enroll_id,
                    :contact_no,
                    :user_id,
                    :dept_name
                )
            """, {
                "enroll_id": request.form["enroll_id"].strip(),
                "contact_no": int(request.form["contact_no"]),
                "user_id": int(request.form["user_id"]),
                "dept_name": request.form["dept_name"].strip()
            })

            conn.commit()

            flash("Student added successfully!", "success")
            return redirect(url_for("students"))

        except (oracledb.Error, ValueError, TypeError) as e:
            conn.rollback()

            return render_template(
                "add_student.html",
                error=str(e)
            )

        finally:
            cursor.close()
            conn.close()

    return render_template("add_student.html")


# ================= EDIT STUDENT =================

@app.route("/students/edit/<enroll_id>", methods=["GET", "POST"])
@librarian_required
def edit_student(enroll_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if request.method == "POST":

            try:
                cursor.execute("""
                    UPDATE SYS.STUDENT
                    SET
                        CONTACT_NO = :contact_no,
                        USER_ID = :user_id,
                        DEPT_NAME = :dept_name
                    WHERE ENROLL_ID = :enroll_id
                """, {
                    "contact_no": int(request.form["contact_no"]),
                    "user_id": int(request.form["user_id"]),
                    "dept_name": request.form["dept_name"].strip(),
                    "enroll_id": enroll_id
                })

                if cursor.rowcount == 0:
                    conn.rollback()
                    return "Student not found.", 404

                conn.commit()

                flash("Student updated successfully!", "success")
                return redirect(url_for("students"))

            except (oracledb.Error, ValueError, TypeError) as e:
                conn.rollback()

                cursor.execute("""
                    SELECT
                        ENROLL_ID,
                        CONTACT_NO,
                        USER_ID,
                        DEPT_NAME
                    FROM SYS.STUDENT
                    WHERE ENROLL_ID = :eid
                """, {"eid": enroll_id})

                student = cursor.fetchone()

                if student is None:
                    return "Student not found.", 404

                return render_template(
                    "edit_student.html",
                    student=student,
                    error=str(e)
                )

        cursor.execute("""
            SELECT
                ENROLL_ID,
                CONTACT_NO,
                USER_ID,
                DEPT_NAME
            FROM SYS.STUDENT
            WHERE ENROLL_ID = :eid
        """, {"eid": enroll_id})

        student = cursor.fetchone()

        if student is None:
            return "Student not found.", 404

        return render_template(
            "edit_student.html",
            student=student
        )

    finally:
        cursor.close()
        conn.close()


# ================= DELETE STUDENT =================

@app.route("/students/delete/<enroll_id>", methods=["POST"])
@librarian_required
def delete_student(enroll_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            DELETE FROM SYS.STUDENT
            WHERE ENROLL_ID = :eid
        """, {"eid": enroll_id})

        if cursor.rowcount == 0:
            conn.rollback()
            return "Student not found.", 404

        conn.commit()

        flash("Student deleted successfully!", "success")
        return redirect(url_for("students"))

    except oracledb.Error:
        conn.rollback()

        return (
            "Cannot delete this student because the student "
            "may be linked to borrowing or other records.",
            409
        )

    finally:
        cursor.close()
        conn.close()


# ================= BORROW RECORDS =================

@app.route("/borrow")
@librarian_required
def borrow_records():

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                B.E_BORROW_ID,
                B.ENROLL_ID,
                B.BOOK_ACCESSION_NO,
                BK.BOOK_NAME,
                B.E_BOOK_ISSUE_DATE,
                B.E_BOOK_DUE_DATE,
                B.E_BOOK_RETURN_DATE,
                B.FINE_AMOUNT,
                B.QUANTITY
            FROM SYS.E_BORROW B
            JOIN SYS.E_BOOK_COPY C
                ON B.BOOK_ACCESSION_NO = C.BOOK_ACCESSION_NO
            JOIN SYS.BOOK BK
                ON C.ISBN_NO = BK.ISBN_NO
            ORDER BY B.E_BORROW_ID DESC
        """)

        records = cursor.fetchall()

        return render_template(
            "borrow.html",
            records=records
        )

    finally:
        cursor.close()
        conn.close()


# ================= MY SHELF =================

@app.route("/my-shelf")
@student_required
def my_shelf():

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                EB.E_BORROW_ID,
                B.BOOK_NAME,
                B.AUTHOR,
                C.BOOK_ACCESSION_NO,
                EB.E_BOOK_ISSUE_DATE,
                EB.E_BOOK_DUE_DATE,
                EB.E_BOOK_RETURN_DATE,
                EB.FINE_AMOUNT,
                CASE
                    WHEN EB.E_BOOK_RETURN_DATE IS NOT NULL
                        THEN 'Returned'
                    WHEN TRUNC(EB.E_BOOK_DUE_DATE) < TRUNC(SYSDATE)
                        THEN 'Overdue'
                    ELSE 'Active'
                END AS BORROW_STATUS
            FROM SYS.E_BORROW EB
            JOIN SYS.STUDENT S
                ON EB.ENROLL_ID = S.ENROLL_ID
            JOIN SYS.E_BOOK_COPY C
                ON EB.BOOK_ACCESSION_NO = C.BOOK_ACCESSION_NO
            JOIN SYS.BOOK B
                ON C.ISBN_NO = B.ISBN_NO
            WHERE S.USER_ID = :user_id
            ORDER BY EB.E_BORROW_ID DESC
        """, {"user_id": session["user_id"]})

        borrowed_books = cursor.fetchall()

        return render_template(
            "my_shelf.html",
            borrowed_books=borrowed_books
        )

    finally:
        cursor.close()
        conn.close()


# ================= STUDENT RETURN BOOK =================

@app.route("/student/return/<int:borrow_id>", methods=["POST"])
@student_required
def student_return_book(borrow_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT E_BOOK_RETURN_DATE
            FROM SYS.E_BORROW
            WHERE E_BORROW_ID = :borrow_id
            FOR UPDATE
        """, {"borrow_id": borrow_id})

        record = cursor.fetchone()

        if record is None:
            conn.rollback()
            flash("Borrowing record not found.", "error")
            return redirect(url_for("my_shelf"))

        if record[0] is not None:
            conn.rollback()
            flash("This book has already been returned.", "warning")
            return redirect(url_for("my_shelf"))

        # Check that the borrowing record belongs to this student.
        cursor.execute("""
            SELECT S.USER_ID
            FROM SYS.E_BORROW EB
            JOIN SYS.STUDENT S
                ON EB.ENROLL_ID = S.ENROLL_ID
            WHERE EB.E_BORROW_ID = :borrow_id
        """, {"borrow_id": borrow_id})

        owner = cursor.fetchone()

        if owner is None or owner[0] != session["user_id"]:
            conn.rollback()
            flash(
                "You are not authorized to return this book.",
                "error"
            )
            return redirect(url_for("my_shelf"))

        cursor.callproc("SYS.RETURNBOOK", [borrow_id])

        cursor.execute("""
            SELECT FINE_AMOUNT
            FROM SYS.E_BORROW
            WHERE E_BORROW_ID = :borrow_id
        """, {"borrow_id": borrow_id})

        fine = cursor.fetchone()[0] or 0

        conn.commit()

        flash(
            f"Book returned successfully! Fine amount: ₹{fine:.2f}",
            "success"
        )

    except Exception as e:
        conn.rollback()
        flash(f"Book return failed: {str(e)}", "error")

    finally:
        cursor.close()
        conn.close()

    return redirect(url_for("my_shelf"))
# ================= ISSUE BOOK OPTIONS =================

def get_issue_options(cursor):

    cursor.execute("""
        SELECT ENROLL_ID
        FROM SYS.STUDENT
        ORDER BY ENROLL_ID
    """)

    students_list = cursor.fetchall()

    cursor.execute("""
        SELECT
            C.BOOK_ACCESSION_NO,
            B.BOOK_NAME,
            C.ISBN_NO
        FROM SYS.E_BOOK_COPY C
        JOIN SYS.BOOK B
            ON C.ISBN_NO = B.ISBN_NO
        WHERE LOWER(TRIM(C.AVAILABILITY_STATUS)) = 'available'
        ORDER BY B.BOOK_NAME
    """)

    available_books = cursor.fetchall()

    return students_list, available_books


# ================= STUDENT BORROWING ELIGIBILITY =================

def check_borrowing_eligibility(cursor, enroll_id):

    # Lock the student record to prevent simultaneous borrowing.
    cursor.execute("""
        SELECT ENROLL_ID
        FROM SYS.STUDENT
        WHERE ENROLL_ID = :eid
        FOR UPDATE
    """, {"eid": enroll_id})

    student = cursor.fetchone()

    if student is None:
        raise ValueError("Student record not found.")

    cursor.execute("""
        SELECT
            COUNT(*),
            NVL(
                SUM(
                    CASE
                        WHEN TRUNC(E_BOOK_DUE_DATE) < TRUNC(SYSDATE)
                        THEN 1
                        ELSE 0
                    END
                ),
                0
            )
        FROM SYS.E_BORROW
        WHERE ENROLL_ID = :eid
          AND E_BOOK_RETURN_DATE IS NULL
    """, {"eid": enroll_id})

    active_books, overdue_books = cursor.fetchone()

    if overdue_books > 0:
        raise ValueError(
            "You have an overdue book. Please return it before borrowing another book."
        )

    if active_books >= 3:
        raise ValueError(
            "Borrowing limit reached. Maximum 3 active books are allowed."
        )


# ================= FINE MANAGEMENT =================

@app.route("/fines")
@librarian_required
def fines():

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                B.E_BORROW_ID,
                B.ENROLL_ID,
                BK.BOOK_NAME,
                B.E_BOOK_DUE_DATE,
                B.E_BOOK_RETURN_DATE,

                CASE
                    WHEN B.E_BOOK_RETURN_DATE IS NOT NULL
                        THEN NVL(B.FINE_AMOUNT, 0)

                    WHEN TRUNC(SYSDATE) > TRUNC(B.E_BOOK_DUE_DATE)
                        THEN (
                            TRUNC(SYSDATE) -
                            TRUNC(B.E_BOOK_DUE_DATE)
                        ) * 10

                    ELSE 0
                END AS CALCULATED_FINE,

                CASE
                    WHEN B.E_BOOK_RETURN_DATE IS NOT NULL
                        THEN 'Returned'

                    WHEN TRUNC(SYSDATE) > TRUNC(B.E_BOOK_DUE_DATE)
                        THEN 'Overdue'

                    ELSE 'Not Overdue'
                END AS BOOK_STATUS

            FROM SYS.E_BORROW B

            JOIN SYS.E_BOOK_COPY C
                ON B.BOOK_ACCESSION_NO = C.BOOK_ACCESSION_NO

            JOIN SYS.BOOK BK
                ON C.ISBN_NO = BK.ISBN_NO

            ORDER BY B.E_BORROW_ID DESC
        """)

        fine_records = cursor.fetchall()

        fines_on_returned_books = sum(
            float(record[5] or 0)
            for record in fine_records
            if record[4] is not None
        )

        outstanding_fines = sum(
            float(record[5] or 0)
            for record in fine_records
            if record[4] is None
        )

        total_fines = (
            fines_on_returned_books + outstanding_fines
        )

        return render_template(
            "fines.html",
            fine_records=fine_records,
            fines_on_returned_books=fines_on_returned_books,
            outstanding_fines=outstanding_fines,
            total_fines=total_fines
        )

    finally:
        cursor.close()
        conn.close()


# ================= LIBRARIAN ISSUE BOOK =================

@app.route("/borrow/issue", methods=["GET", "POST"])
@librarian_required
def issue_book():

    conn = get_connection()
    cursor = conn.cursor()

    today = date.today().isoformat()

    selected_student = ""
    selected_accession = ""
    selected_issue_date = today

    try:
        if request.method == "POST":

            selected_student = request.form["enroll_id"].strip()
            selected_accession = int(request.form["accession_no"])
            selected_issue_date = request.form["issue_date"]

            issue_date = datetime.strptime(
                selected_issue_date,
                "%Y-%m-%d"
            ).date()

            if issue_date < date.today():
                raise ValueError("Issue date cannot be in the past.")

            due_date = issue_date + timedelta(days=14)

            submitted_due_date = datetime.strptime(
                request.form["due_date"],
                "%Y-%m-%d"
            ).date()

            if submitted_due_date != due_date:
                raise ValueError(
                    "Due date must be exactly 14 days after issue date."
                )

            check_borrowing_eligibility(
                cursor,
                selected_student
            )

            # Lock the selected copy.
            cursor.execute("""
                SELECT AVAILABILITY_STATUS
                FROM SYS.E_BOOK_COPY
                WHERE BOOK_ACCESSION_NO = :acc
                FOR UPDATE
            """, {"acc": selected_accession})

            copy = cursor.fetchone()

            if copy is None:
                raise ValueError("Selected book copy does not exist.")

            if (copy[0] or "").strip().lower() != "available":
                raise ValueError("This book copy is currently unavailable.")

            # Generate borrowing ID.
            cursor.execute("""
                SELECT SYS.E_BORROW_ID_SEQ.NEXTVAL
                FROM DUAL
            """)

            borrow_id = cursor.fetchone()[0]

            # Insert borrowing record.
            cursor.execute("""
                INSERT INTO SYS.E_BORROW
                (
                    E_BORROW_ID,
                    ENROLL_ID,
                    BOOK_ACCESSION_NO,
                    E_BOOK_ISSUE_DATE,
                    E_BOOK_DUE_DATE,
                    FINE_AMOUNT,
                    QUANTITY
                )
                VALUES
                (
                    :bid,
                    :eid,
                    :acc,
                    :issue_date,
                    :due_date,
                    0,
                    1
                )
            """, {
                "bid": borrow_id,
                "eid": selected_student,
                "acc": selected_accession,
                "issue_date": issue_date,
                "due_date": due_date
            })

            # Update copy availability.
            cursor.execute("""
                UPDATE SYS.E_BOOK_COPY
                SET AVAILABILITY_STATUS = 'unavailable'
                WHERE BOOK_ACCESSION_NO = :acc
                  AND LOWER(TRIM(AVAILABILITY_STATUS)) = 'available'
            """, {"acc": selected_accession})

            if cursor.rowcount != 1:
                raise ValueError(
                    "Book availability could not be updated. Please try again."
                )

            conn.commit()

            flash(
                "Book issued successfully! Borrow ID: " + str(borrow_id),
                "success"
            )

            return redirect(url_for("borrow_records"))

        students_list, available_books = get_issue_options(cursor)

        return render_template(
            "issue_book.html",
            students=students_list,
            available_books=available_books,
            today=today,
            selected_student=selected_student,
            selected_accession=selected_accession,
            selected_issue_date=selected_issue_date
        )

    except (oracledb.Error, ValueError, TypeError) as e:

        conn.rollback()

        students_list, available_books = get_issue_options(cursor)

        return render_template(
            "issue_book.html",
            students=students_list,
            available_books=available_books,
            today=today,
            selected_student=selected_student,
            selected_accession=selected_accession,
            selected_issue_date=selected_issue_date,
            error=str(e)
        )

    finally:
        cursor.close()
        conn.close()


# ================= LIBRARIAN RETURN BOOK =================

@app.route("/borrow/return/<int:borrow_id>", methods=["POST"])
@librarian_required
def return_book(borrow_id):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT E_BOOK_RETURN_DATE
            FROM SYS.E_BORROW
            WHERE E_BORROW_ID = :bid
            FOR UPDATE
        """, {"bid": borrow_id})

        record = cursor.fetchone()

        if record is None:
            conn.rollback()
            flash("Borrowing record not found.", "error")
            return redirect(url_for("borrow_records"))

        if record[0] is not None:
            conn.rollback()
            flash("This book has already been returned.", "warning")
            return redirect(url_for("borrow_records"))

        cursor.callproc("SYS.RETURNBOOK", [borrow_id])

        conn.commit()

        flash(
            "Book returned successfully! Book availability has been updated.",
            "success"
        )

        return redirect(url_for("borrow_records"))

    except Exception as e:
        conn.rollback()
        flash("Unable to return book: " + str(e), "error")
        return redirect(url_for("borrow_records"))

    finally:
        cursor.close()
        conn.close()
        # ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip().lower()
        password = request.form["password"]
        selected_role = request.form["role"].strip().lower()

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT
                    USER_ID,
                    NAME,
                    E_MAIL,
                    ROLE,
                    PASSWORD_HASH
                FROM SYS.USERS
                WHERE LOWER(E_MAIL) = :email
            """, {"email": email})

            user = cursor.fetchone()

            if user is None:
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))

            user_id, name, db_email, db_role, password_hash = user

            if not db_role or db_role.lower() != selected_role:
                flash(
                    "The selected role does not match your account.",
                    "error"
                )
                return redirect(url_for("login"))

            if not password_hash or not check_password_hash(
                password_hash,
                password
            ):
                flash("Invalid email or password.", "error")
                return redirect(url_for("login"))

            # Create a fresh login session.
            session.clear()

            session["user_id"] = user_id
            session["name"] = name
            session["email"] = db_email
            session["role"] = db_role.lower()

            if session["role"] == "librarian":
                return redirect(url_for("home"))

            return redirect(url_for("student_home"))

        finally:
            cursor.close()
            conn.close()

    return render_template("login.html")


# ================= LOGOUT =================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out successfully.", "success")

    return redirect(url_for("login"))


# ================= STUDENT DASHBOARD =================

@app.route("/student/home")
@student_required
def student_home():

    return render_template(
        "student_home.html",
        name=session["name"]
    )


# ================= EXPLORE BOOKS =================

@app.route("/explore-books")
@student_required
def explore_books():

    search = request.args.get("search", "").strip()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                B.ISBN_NO,
                B.BOOK_NAME,
                B.AUTHOR,
                B.PUBLISHER,
                B.PRICE,
                B.PUBLICATION_YEAR,
                B.EDITION,
                (
                    SELECT COUNT(*)
                    FROM SYS.E_BOOK_COPY C
                    WHERE C.ISBN_NO = B.ISBN_NO
                      AND UPPER(TRIM(C.AVAILABILITY_STATUS)) = 'AVAILABLE'
                ) AS AVAILABLE_COPIES
            FROM SYS.BOOK B
            WHERE LOWER(B.BOOK_NAME) LIKE :search
               OR LOWER(B.AUTHOR) LIKE :search
               OR LOWER(B.PUBLISHER) LIKE :search
            ORDER BY B.BOOK_NAME
        """, {
            "search": f"%{search.lower()}%"
        })

        books = cursor.fetchall()

        return render_template(
            "explore_books.html",
            books=books,
            search=search
        )

    finally:
        cursor.close()
        conn.close()


# ================= BOOK DETAILS =================

@app.route("/book/<isbn>")
@student_required
def book_details(isbn):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                B.ISBN_NO,
                B.BOOK_NAME,
                B.AUTHOR,
                B.PUBLISHER,
                B.PRICE,
                B.PUBLICATION_YEAR,
                B.EDITION,

                COUNT(
                    CASE
                        WHEN UPPER(TRIM(C.AVAILABILITY_STATUS)) = 'AVAILABLE'
                        THEN 1
                    END
                ) AS AVAILABLE_COPIES,

                COUNT(C.BOOK_ACCESSION_NO) AS TOTAL_COPIES

            FROM SYS.BOOK B

            LEFT JOIN SYS.E_BOOK_COPY C
                ON B.ISBN_NO = C.ISBN_NO

            WHERE B.ISBN_NO = :isbn

            GROUP BY
                B.ISBN_NO,
                B.BOOK_NAME,
                B.AUTHOR,
                B.PUBLISHER,
                B.PRICE,
                B.PUBLICATION_YEAR,
                B.EDITION
        """, {"isbn": isbn})

        book = cursor.fetchone()

        if not book:
            flash("Book not found.", "error")
            return redirect(url_for("explore_books"))

        return render_template(
            "book_details.html",
            book=book
        )

    finally:
        cursor.close()
        conn.close()


# ================= STUDENT BORROW BOOK =================

@app.route("/borrow-book/<isbn>", methods=["POST"])
@student_required
def borrow_book(isbn):

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # Find the logged-in student's enrollment ID.
        cursor.execute("""
            SELECT ENROLL_ID
            FROM SYS.STUDENT
            WHERE USER_ID = :user_id
        """, {"user_id": session["user_id"]})

        student = cursor.fetchone()

        if not student:
            conn.rollback()

            flash("Student record not found.", "error")

            return redirect(url_for("explore_books"))

        enroll_id = student[0]

        # Check borrowing eligibility.
        check_borrowing_eligibility(cursor, enroll_id)

        # Lock one available book copy.
        cursor.execute("""
            SELECT BOOK_ACCESSION_NO
            FROM SYS.E_BOOK_COPY
            WHERE ISBN_NO = :isbn
              AND UPPER(TRIM(AVAILABILITY_STATUS)) = 'AVAILABLE'
            FOR UPDATE SKIP LOCKED
        """, {"isbn": isbn})

        copy = cursor.fetchone()

        if not copy:
            conn.rollback()

            flash(
                "Sorry, no available copies of this book right now.",
                "warning"
            )

            return redirect(
                url_for("book_details", isbn=isbn)
            )

        accession_no = copy[0]

        # Mark the selected copy unavailable.
        cursor.execute("""
            UPDATE SYS.E_BOOK_COPY
            SET AVAILABILITY_STATUS = 'unavailable'
            WHERE BOOK_ACCESSION_NO = :accession_no
              AND UPPER(TRIM(AVAILABILITY_STATUS)) = 'AVAILABLE'
        """, {"accession_no": accession_no})

        if cursor.rowcount != 1:
            raise ValueError(
                "This book copy is no longer available."
            )

        # Generate borrowing ID.
        cursor.execute("""
            SELECT SYS.E_BORROW_ID_SEQ.NEXTVAL
            FROM DUAL
        """)

        borrow_id = cursor.fetchone()[0]

        # Set issue date and 14-day due date.
        issue_date = date.today()
        due_date = issue_date + timedelta(days=14)

        # Insert borrowing record.
        cursor.execute("""
            INSERT INTO SYS.E_BORROW
            (
                E_BORROW_ID,
                ENROLL_ID,
                BOOK_ACCESSION_NO,
                E_BOOK_ISSUE_DATE,
                E_BOOK_DUE_DATE,
                E_BOOK_RETURN_DATE,
                FINE_AMOUNT,
                QUANTITY
            )
            VALUES
            (
                :borrow_id,
                :enroll_id,
                :accession_no,
                :issue_date,
                :due_date,
                NULL,
                0,
                1
            )
        """, {
            "borrow_id": borrow_id,
            "enroll_id": enroll_id,
            "accession_no": accession_no,
            "issue_date": issue_date,
            "due_date": due_date
        })

        # Commit both changes together.
        conn.commit()

        flash(
            "Book borrowed successfully! Return it within 14 days.",
            "success"
        )

    except Exception as e:
        conn.rollback()

        flash(
            f"Borrowing failed: {str(e)}",
            "error"
        )

    finally:
        cursor.close()
        conn.close()

    return redirect(
        url_for("book_details", isbn=isbn)
    )


# ================= STUDENT REGISTRATION =================

@app.route("/register", methods=["GET", "POST"])
def register():

    conn = get_connection()
    cursor = conn.cursor()

    error = None

    try:
        # Load department options.
        cursor.execute("""
            SELECT DEPT_NAME
            FROM SYS.DEPARTMENT
            ORDER BY DEPT_NAME
        """)

        departments = [
            row[0]
            for row in cursor.fetchall()
        ]

        if request.method == "POST":

            name = request.form["name"].strip()
            email = request.form["email"].strip().lower()
            enroll_id = request.form["enroll_id"].strip()
            contact = request.form["contact"].strip()
            department = request.form["department"].strip()
            password = request.form["password"]
            confirm_password = request.form["confirm_password"]

            # Validate registration details.
            if not all([
                name,
                email,
                enroll_id,
                contact,
                department
            ]):
                error = "Please fill in all fields."

            elif len(name) > 50:
                error = "Name must not exceed 50 characters."

            elif len(email) > 100 or "@" not in email:
                error = "Please enter a valid email address."

            elif len(enroll_id) > 20:
                error = "Enrollment ID must not exceed 20 characters."

            elif not contact.isdigit() or len(contact) != 10:
                error = "Contact number must contain exactly 10 digits."

            elif department not in departments:
                error = "Please select a valid department."

            elif len(password) < 8:
                error = "Password must contain at least 8 characters."

            elif not any(c.isupper() for c in password):
                error = "Password must contain an uppercase letter."

            elif not any(c.islower() for c in password):
                error = "Password must contain a lowercase letter."

            elif not any(c.isdigit() for c in password):
                error = "Password must contain a number."

            elif password != confirm_password:
                error = "Passwords do not match."

            # Check whether email already exists.
            if error is None:

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM SYS.USERS
                    WHERE LOWER(E_MAIL) = :email
                """, {"email": email})

                if cursor.fetchone()[0] > 0:
                    error = "This email is already registered."

            # Check whether enrollment ID already exists.
            if error is None:

                cursor.execute("""
                    SELECT COUNT(*)
                    FROM SYS.STUDENT
                    WHERE ENROLL_ID = :enroll_id
                """, {"enroll_id": enroll_id})

                if cursor.fetchone()[0] > 0:
                    error = "This enrollment ID is already registered."

            # Create the user and student records.
            if error is None:

                cursor.execute("""
                    SELECT SYS.USER_ID_SEQ.NEXTVAL
                    FROM DUAL
                """)

                user_id = cursor.fetchone()[0]

                password_hash = generate_password_hash(password)

                cursor.execute("""
                    INSERT INTO SYS.USERS
                    (
                        USER_ID,
                        NAME,
                        E_MAIL,
                        ROLE,
                        PASSWORD_HASH
                    )
                    VALUES
                    (
                        :user_id,
                        :name,
                        :email,
                        'student',
                        :password_hash
                    )
                """, {
                    "user_id": user_id,
                    "name": name,
                    "email": email,
                    "password_hash": password_hash
                })

                cursor.execute("""
                    INSERT INTO SYS.STUDENT
                    (
                        ENROLL_ID,
                        CONTACT_NO,
                        USER_ID,
                        DEPT_NAME
                    )
                    VALUES
                    (
                        :enroll_id,
                        :contact,
                        :user_id,
                        :department
                    )
                """, {
                    "enroll_id": enroll_id,
                    "contact": int(contact),
                    "user_id": user_id,
                    "department": department
                })

                conn.commit()

                flash(
                    "Registration successful! Please log in.",
                    "success"
                )

                return redirect(url_for("login"))

        return render_template(
            "register.html",
            departments=departments,
            error=error
        )

    except oracledb.Error:
        conn.rollback()

        error = (
            "Registration failed. Please check your details "
            "and try again."
        )

        return render_template(
            "register.html",
            departments=departments,
            error=error
        )

    finally:
        cursor.close()
        conn.close()


# ================= APPLICATION START =================

if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )