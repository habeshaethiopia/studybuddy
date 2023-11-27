"""This is the main web app"""
from flask import Flask, render_template, url_for, redirect, request, jsonify
from flask import Flask, request, jsonify, session
from werkzeug.utils import secure_filename
import os

from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain, RetrievalQA
from langchain.document_loaders import (
    DirectoryLoader,
    TextLoader,
    UnstructuredPDFLoader,
)
from langchain.embeddings import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.indexes.vectorstore import VectorStoreIndexWrapper
from langchain.llms import OpenAI
from langchain.vectorstores import Chroma
import constants
import secrets

def generate_secret_key():
    return secrets.token_hex(16)
os.environ["OPENAI_API_KEY"] = constants.APIKEY
app = Flask(__name__)
app.secret_key = generate_secret_key()
UPLOAD_FOLDER = "static/data"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Enable to save to disk & reuse the model (for repeated queries on the same data)
PERSIST = True


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def initialize_chat_chain(fname):
    loader = UnstructuredPDFLoader("static/"+fname)

    if PERSIST:
        index = VectorstoreIndexCreator(
            vectorstore_kwargs={"persist_directory": "persist"}
        ).from_loaders([loader])
    else:
        index = VectorstoreIndexCreator().from_loaders([loader])

    chain = ConversationalRetrievalChain.from_llm(
        llm=ChatOpenAI(model="gpt-3.5-turbo"),
        retriever=index.vectorstore.as_retriever(search_kwargs={"k": 1}),
    )
    return chain

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat/<filename>", methods=["GET", "POST"])
def chat(filename):

    filename = UPLOAD_FOLDER.replace("static/", "") + "/" + filename

    chain = initialize_chat_chain(filename)
    if request.method == "POST":
        message = request.form["message"]
         # Get the chat history from the session
        chat_history = session.get('chat_history', [])
        # Store the updated chat history in the session
        result = chain({"question": message, "chat_history": chat_history})
        answer = result["answer"]
        chat_history.append((message, answer))
        session['chat_history'] = chat_history

        return jsonify({"answer": answer})

    return render_template("chat.html", filename=filename)


@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            return jsonify({"error": "No file part"})

        file = request.files["file"]

        if file.filename == "":
            return jsonify({"error": "No selected file"})

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
            return redirect(url_for("chat", filename=filename))
        else:
            return jsonify({"error": "Invalid file"})

    return render_template("index.html")


if __name__ == "__main__":
    app.run(port=5050,debug=True)
# analyze it if it has server error