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
from functools import lru_cache

import json
from os import environ as env
from urllib.parse import quote_plus, urlencode

from authlib.integrations.flask_client import OAuth
from dotenv import find_dotenv, load_dotenv
from flask import Flask, redirect, render_template, session, url_for

ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)

app = Flask(__name__)
app.secret_key = env.get("APP_SECRET_KEY")


oauth = OAuth(app)

oauth.register(
    "auth0",
    client_id=env.get("AUTH0_CLIENT_ID"),
    client_secret=env.get("AUTH0_CLIENT_SECRET"),
    client_kwargs={
        "scope": "openid profile email",
    },
    server_metadata_url=f'https://{env.get("AUTH0_DOMAIN")}/.well-known/openid-configuration',
)
# app.py

env["OPENAI_API_KEY"] = str(env.get("APIKEY"))
UPLOAD_FOLDER = "static/data"
ALLOWED_EXTENSIONS = {"txt", "pdf", "png", "jpg", "jpeg", "gif"}

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

"""Enable to save to disk & reuse the model
(for repeated queries on the same data)"""
PERSIST = False


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@lru_cache(maxsize=None)
def initialize_chat_chain(fname):
    loader = UnstructuredPDFLoader("static/" + fname)
    if PERSIST and os.path.exists("persist"):
        print("Reusing index...\n")
        vectorstore = Chroma(
            persist_directory="persist", embedding_function=OpenAIEmbeddings()
        )
        index = VectorStoreIndexWrapper(vectorstore=vectorstore)
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


@app.route("/index")
def home2():
    return render_template("index.html")


@app.route("/chat/<filename>", methods=["GET", "POST"])
def chat(filename):
    filename = UPLOAD_FOLDER.replace("static/", "") + "/" + filename

    chain = initialize_chat_chain(filename)
    if request.method == "POST":
        message = request.form["message"]
        # Get the chat history from the session
        chat_history = session.get("chat_history", [])
        # Store the updated chat history in the session
        result = chain({"question": message, "chat_history": chat_history})
        answer = result["answer"]
        chat_history.append((message, answer))
        session["chat_history"] = chat_history

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


# Controllers API
@app.route("/")
def home():
    return render_template(
        "home.html",
        session=session.get("user"),
        pretty=json.dumps(session.get("user"), indent=4),
    )


@app.route("/callback", methods=["GET", "POST"])
def callback():
    token = oauth.auth0.authorize_access_token()
    session["user"] = token
    return redirect("/")


@app.route("/login")
def login():
    return oauth.auth0.authorize_redirect(
        redirect_uri=url_for("callback", _external=True)
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(
        "https://"
        + env.get("AUTH0_DOMAIN")
        + "/v2/logout?"
        + urlencode(
            {
                "returnTo": url_for("home", _external=True),
                "client_id": env.get("AUTH0_CLIENT_ID"),
            },
            quote_via=quote_plus,
        )
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=env.get("PORT", 3000), debug=True)
