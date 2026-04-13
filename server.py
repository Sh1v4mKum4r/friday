import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from agent import agent_manager

load_dotenv()

app = FastAPI(title="Friday AI Microservice")

class MessageRequest(BaseModel):
    message: str
    agent_type: str = "system" # 'system' or 'research'

class MessageResponse(BaseModel):
    response: str
    agent_type: str

@app.post("/chat", response_model=MessageResponse)
async def chat_endpoint(request: MessageRequest):
    if request.agent_type not in agent_manager.chats:
        raise HTTPException(status_code=400, detail=f"Agent type '{request.agent_type}' not found.")
        
    response_text = agent_manager.process_message(request.agent_type, request.message)
    return MessageResponse(response=response_text, agent_type=request.agent_type)

@app.get("/health")
def health_check():
    return {"status": "online", "api_key_configured": bool(os.getenv("GEMINI_API_KEY"))}

# Run with: uvicorn server:app --host 127.0.0.1 --port 8000
