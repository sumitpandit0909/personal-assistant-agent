from redis import Redis
from config.settings import setting
import json
from typing import List, Dict

class RedisMemory:
    def __init__(self):
        self.client = Redis.from_url(setting.REDIS_URL,decode_responses=True)
    
    def append_message(self,session_id:str,role:str,content:str,link:str=None,task_id:str=None,ttl_seconds:int=14400):
        key =f"chat:session:{session_id}"
        msg= json.dumps({
            "role":role,
            "content":content,
            "link":link,
            "task_id":task_id
        })
        self.client.rpush(key,msg)
        self.client.expire(key,ttl_seconds)
    
    def get_messages(self,session_id:str,count:int=20)->List[Dict]:
        key=f"chat:session:{session_id}"
        messages = self.client.lrange(key,-count,-1)
        return [json.loads(msg) for msg in messages]