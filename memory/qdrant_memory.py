from pandas.core.ops.docstrings import key
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams,PointStruct,Filter,Distance,FieldCondition,MatchValue
from sentence_transformers import SentenceTransformer
from config.settings import setting
from uuid import uuid4
from typing import List



class QdrantMemory:
    def __init__(self):
        self.client=QdrantClient(
            url=setting.QDRANT_URL,
            api_key=setting.QDRANT_API_KEY
        )
        self.embedding = SentenceTransformer("all-mpnet-base-v2")
        self.collection_name="User-memory"

        if not self.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=768,
                    distance=Distance.COSINE
                )
            )
    
    def store_fact(self, user_id: str, fact_text: str,session_id:str):

        vector = self.embedding.encode(fact_text).tolist()
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
        query_vector= self.embedding.encode(query).tolist()
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
            score = hit.score
            fact = hit.payload["fact"]
            result +=f"- {fact} score: {score}\n\n"
        return result
            
        