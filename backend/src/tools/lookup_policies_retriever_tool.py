from langchain_core.tools import tool
import weaviate
from langchain.retrievers.document_compressors import CohereRerank, EmbeddingsFilter
# from langchain_cohere import CohereRerank
from langchain.retrievers import ContextualCompressionRetriever, ParentDocumentRetriever
from langchain_community.vectorstores import FAISS
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain.storage import InMemoryStore


@tool
def lookup_policy(query: str) -> str:
    """Consult the company policies to check whether certain options are permitted.
    Use this before making any flight changes performing other 'write' events."""

    gemini_embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
    vectorstore_local = FAISS.load_local(folder_path="src/database/faiss_db",
                                         embeddings=gemini_embeddings, index_name="faiss_db_index",
                                         allow_dangerous_deserialization=True)
    parent_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=0)
    child_splitter = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=0)
    compressor = CohereRerank(top_n=5, user_agent="langchain")
    retriever = ParentDocumentRetriever(vectorstore=vectorstore_local, parent_splitter=parent_splitter,
                                        child_splitter=child_splitter, docstore=InMemoryStore())
    # compressor = FlashrankRerank()
    # retriever = WeaviateHybridSearchRetriever(
    #     alpha=0.7,  # defaults to 0.5, which is equal weighting between keyword and semantic search
    #     client=client,  # keyword arguments to pass to the Weaviate client
    #     index_name="RAG",  # The name of the index to use
    #     text_key="content",  # The name of the text key to use
    #     attributes=[],  # The attributes to return in the results
    #     create_schema_if_missing=True,
    #     k=5
    # )
    context_retriever = ContextualCompressionRetriever(base_compressor=compressor, base_retriever=retriever)
    # retriever_tool = create_retriever_tool(retriever=context_retriever, name="hybrid-search",
    #                       description="")
    # return retriever_tool
    docs = context_retriever.invoke(input=query)
    return "\n\n".join([doc.page_content for doc in docs])

