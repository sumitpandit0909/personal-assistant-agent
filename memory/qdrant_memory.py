from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams,PointStruct,Filter,Distance,FieldCondition,MatchValue
from config.settings import setting
from uuid import uuid4
from typing import List
from openrouter import OpenRouter
from config.settings import setting



openrouter_app = OpenRouter(setting.OPENROUTER_API_KEY)

def create_embeddings(text):
    response = openrouter_app.embeddings.generate(
        input=text,
        model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
        dimensions=786,

    )
    return response.data[0].embedding

class QdrantMemory:
    def __init__(self):
        self.client=QdrantClient(
            url=setting.QDRANT_URL,
            api_key=setting.QDRANT_API_KEY
        )
        self.embedding = create_embeddings
        self.collection_name="User-memory-v2"

        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=786,
                    distance=Distance.COSINE
                )
            )
    
    def store_fact(self, user_id: str, fact_text: str,session_id:str):

        vector = self.embedding(fact_text)
        point_id = str(uuid4())
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload={
                        "user_id":user_id,
                        "session_id":session_id,
                        "fact":fact_text
                    }
                )
            ]
        )

    def recall_facts(self, user_id:str,query:str,top_k:int=5)-> str:
        query_vector= self.embedding(query)
        results = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=top_k,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="user_id",
                        match=MatchValue(value=user_id)
                        )
                ]
            )
        )
        result=""
        for hit in results:
            fact = hit.payload["fact"]
            result +=f"- {fact} \n\n"
        return result
            
        