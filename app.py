import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from werkzeug.utils import secure_filename
from azure.storage.blob import BlobServiceClient

app = Flask(__name__)
app.secret_key = "mediaflow-secret-key"

DATABASE = "mediaflow.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

# Paste your Azure Storage connection string here
AZURE_CONNECTION_STRING = os.environ.get('AZURE_CONNECTION_STRING')

CONTAINER_NAME = "media-images"

blob_service_client = BlobServiceClient.from_connection_string(
    AZURE_CONNECTION_STRING
)


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            filename TEXT NOT NULL,
            category TEXT,
            uploaded_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    conn = get_db()
    images = conn.execute("SELECT * FROM images ORDER BY id DESC").fetchall()
    conn.close()
    return render_template("index.html", images=images)


@app.route("/upload", methods=["GET", "POST"])
def upload():
    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]
        file = request.files["image"]

        if file.filename == "":
            flash("Please select an image.")
            return redirect(url_for("upload"))

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"{timestamp}_{filename}"

            # Upload image directly to Azure Blob Storage
            blob_client = blob_service_client.get_blob_client(
                container=CONTAINER_NAME,
                blob=filename
                
            )

            blob_client.upload_blob(file, overwrite=True)
            blob_url = blob_client.url

            print("Uploaded to Azure:", blob_url)

            # Save Azure image URL as metadata in SQLite
            conn = get_db()
            conn.execute("""
                INSERT INTO images (title, description, filename, category, uploaded_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                title,
                description,
                blob_url,
                category,
                datetime.now().strftime("%Y-%m-%d %H:%M")
            ))
            conn.commit()
            conn.close()

            flash("Image uploaded successfully to Azure Blob Storage.")
            return redirect(url_for("index"))

        flash("Only image files are allowed.")
        return redirect(url_for("upload"))

    return render_template("upload.html")


@app.route("/edit/<int:image_id>", methods=["GET", "POST"])
def edit(image_id):
    conn = get_db()
    image = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        category = request.form["category"]

        conn.execute("""
            UPDATE images
            SET title = ?, description = ?, category = ?
            WHERE id = ?
        """, (title, description, category, image_id))

        conn.commit()
        conn.close()

        flash("Image metadata updated.")
        return redirect(url_for("index"))

    conn.close()
    return render_template("edit.html", image=image)


@app.route("/delete/<int:image_id>", methods=["POST"])
def delete(image_id):
    conn = get_db()
    image = conn.execute("SELECT * FROM images WHERE id = ?", (image_id,)).fetchone()

    if image:
        conn.execute("DELETE FROM images WHERE id = ?", (image_id,))
        conn.commit()

    conn.close()
    flash("Image metadata deleted from database.")
    return redirect(url_for("index"))


@app.route("/azure")
def azure():
    return render_template("azure.html")


if __name__ == "__main__":
    init_db()
    app.run(host="127.0.0.1", port=8000, debug=True)