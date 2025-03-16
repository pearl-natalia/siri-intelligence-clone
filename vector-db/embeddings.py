import requests, sys, os
from sentence_transformers import SentenceTransformer
import chromadb
import numpy as np
import networkx as nx  # Example of a simple knowledge graph

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from model import model  # Your model function for generating responses

# Initialize SentenceTransformer for embeddings and ChromaDB for the vector database
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')  # SentenceTransformer for embeddings
chroma_client = chromadb.Client()
collection = chroma_client.create_collection(name="chat_context")

# Create a simple Knowledge Graph (here we use a networkx graph for simplicity)
G = nx.Graph()

# Example structure of a knowledge graph with movies and relationships
G.add_node("The Hangover", type="movie", genre="comedy", time="8 PM")
G.add_node("Comedy", type="genre")
G.add_edge("The Hangover", "Comedy", relationship="is_a")

# Function to generate embeddings using sentence-transformers
def generate_embedding(text):
    return embedding_model.encode(text).tolist()

# Function to add documents (texts) to ChromaDB
def add_to_vector_db(texts, ids):
    embeddings = [generate_embedding(text) for text in texts]
    collection.add(documents=texts, embeddings=embeddings, ids=ids)

# Function to query the vector database
def query_vector_db(query, n_results=3):
    query_embedding = generate_embedding(query)
    results = collection.query(query_embeddings=[query_embedding], n_results=n_results)
    return results

# Function to query knowledge graph for related information (e.g., movie details)
def query_knowledge_graph(query):
    relevant_nodes = []
    for node in G.nodes:
        if query.lower() in node.lower():
            relevant_nodes.append(node)
    
    # If no exact match found, try matching genres or types
    if not relevant_nodes:
        for node, data in G.nodes(data=True):
            if 'genre' in data and query.lower() in data['genre'].lower():
                relevant_nodes.append(node)
    
    return relevant_nodes

# Sample conversation history
texts = [
    "You (yesterday): Hey, what's up?",
    "Friend (yesterday): Not much, just chilling. How about you?",
    "You (yesterday): Same here, just finished work. Got any plans for next week?",
    "Friend (yesterday): Not really, might watch a movie. What about you?",
    "You (yesterday): I might join you! What movie are you thinking of?",
    "Friend (yesterday): I'm not sure yet, maybe a comedy. What do you think?",
    "You: (yesterday) Comedy sounds perfect! Got any favorites?",
    "Friend (yesterday): Hmm, maybe something classic like 'The Hangover'.",
    "You (yesterday): Oh, that's a good one. I haven't watched it in a while. Actually do you wanna watch Reunion instead?",
    "You (yesterday): Bet!",
    "Friend (yesterday): What time should we start?",
    "You (yesterday): How about 8 PM? Does that work for you?",
    "Friend (yesterday): Sounds good! I'll set up everything. See you at 8 tmrw!",
    "Friend (today): What's the plan?"
]

ids = [str(i) for i in range(len(texts))]
add_to_vector_db(texts, ids)

# User's new query (message)
query = "Wait what movie are we watching?"

# Query the vector database for the most relevant context
results = query_vector_db(query)

# Query the knowledge graph to get more context (movies, times, etc.)
knowledge_graph_info = query_knowledge_graph("The Hangover")

# Combine the most relevant results into a prompt for the LLM
context = " ".join([doc for doc in results['documents'][0]])

prompt = f"""You are pretending to be me and will respond to the most recent text message: {query}. 
            Don't make the tone of the messages sound AI generated. 
            Use the tone of my previous messages as a guide on how to set the tone of this generated response.
            Also match the tone/energy of my friend.
            Keep the messages nonchalant but sound like me.
            Use the time stamps to get relevant context and respond to the user. You can add to the conversation to keep it going.
            Only output exactly what will be sent to the recipient. Use my previous replies to determine if I prefer capitalizing the start of my sentences or not.
            Here is some potentially relevant context from previous conversations: {context}
            Knowledge Graph Information: {knowledge_graph_info}"""

# Generate a response using Gemini Flash or a similar model
response = model(prompt, 1.5)

# Print the generated response
print("Response:", response)
