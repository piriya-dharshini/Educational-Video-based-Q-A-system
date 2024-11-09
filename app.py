from fastapi import FastAPI
from pydantic import BaseModel
from langchain_chroma import Chroma
from langserve import add_routes
import uvicorn
import os
from langchain_community.document_loaders import YoutubeLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain.chains import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

os.environ["GOOGLE_API_KEY"] = "AIzaSyAsRbKuPIShShp1SulXg7PLnhmCyzcjgaM"


app = FastAPI(
    title="Langchain Server",
    version="1.0",
    description="An Educational Video Q&A System"
)

# Define the input model
class QAInput(BaseModel):
    youtube_url: str  # Expecting a YouTube URL
    input: str  # Expecting a single input field named 'input'

llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro",
    max_tokens=None,
    timeout=None,
    max_retries=2,
)


# Create a function to index video from YouTube
def index_youtube_video(youtube_url: str):
    loader = YoutubeLoader.from_youtube_url(youtube_url, add_video_info=False)
    trans = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=400, chunk_overlap=60, add_start_index=True
    )
    all_splits = text_splitter.split_documents(trans)
    
    # Create embeddings and vector store
    embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore = Chroma.from_documents(documents=all_splits, embedding=embeddings)
    return vectorstore

# Update your endpoint to accept the model
@app.post("/qa")
async def qa_endpoint(data: QAInput):
    # Index the YouTube video
    vectorstore = index_youtube_video(data.youtube_url)
    
    # Create the retriever
    retriever = vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": 6})
    retrieved_docs = retriever.get_relevant_documents(data.input)

    # Print retrieved documents for debugging
    l=[]
    for i, doc in enumerate(retrieved_docs):
        print(f"Document {i + 1}:")
        print(doc.page_content) 
        l.append(doc.page_content)
    # Create the question-answering chain
    question_answer_chain = create_stuff_documents_chain(
        llm, 
        ChatPromptTemplate.from_messages(
            [
                ("system", "You are an assistant for question-answering tasks. Use the following pieces of retrieved context to answer the question. If you don't know the answer, say that you don't know.\n\n{context}"),
                ("human", "{input}"),
            ]
        )
    )
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)
    
    # Process the question using the rag_chain
    response = rag_chain.invoke({"input": data.input})
    
        
    return {"answer": response["answer"]}

    
    
if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
