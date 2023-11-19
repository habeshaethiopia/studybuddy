#!./myGpt/lib/python3.10
import os
import sys

from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationalRetrievalChain, RetrievalQA
from langchain.document_loaders import DirectoryLoader, TextLoader, UnstructuredPDFLoader
from langchain.embeddings import OpenAIEmbeddings
from langchain.indexes import VectorstoreIndexCreator
from langchain.indexes.vectorstore import VectorStoreIndexWrapper
from langchain.llms import OpenAI
from langchain.vectorstores import Chroma

import constants

os.environ["OPENAI_API_KEY"] = constants.APIKEY

# Enable to save to disk & reuse the model (for repeated queries on the same data)
PERSIST = False

query = None
if len(sys.argv) > 1:
  query = sys.argv[1]
def chat(query = None):
  if PERSIST and os.path.exists("persist"):
    print("Reusing index...\n")
    vectorstore = Chroma(persist_directory="persist", embedding_function=OpenAIEmbeddings())
    index = VectorStoreIndexWrapper(vectorstore=vectorstore)
  else:
    # loader = UnstructuredPDFLoader("data/cat.pdf") # Use this line if you only need data.txt
    # loader = TextLoader("data/cat.pdf") # Use this line if you only need data.txt
    loader = DirectoryLoader("data/")
    if PERSIST:
      index = VectorstoreIndexCreator(vectorstore_kwargs={"persist_directory":"persist"}).from_loaders([loader])
    else:
      index = VectorstoreIndexCreator().from_loaders([loader])

  chain = ConversationalRetrievalChain.from_llm(
    llm=ChatOpenAI(model="gpt-3.5-turbo"),
    retriever=index.vectorstore.as_retriever(search_kwargs={"k": 1}),
  )

  chat_history = []
  while True:
    if not query:
      query = input("Prompt: ")
    if query in ['quit', 'q', 'exit']:
      sys.exit()
    # result = chain({"question": query, "chat_history": chat_history})
    result = index.query(query)
    # print(result['answer'])
    print(result)
    # chat_history.append((query, result['answer']))
    query = None
if __name__=="__main__":
    chat(query)