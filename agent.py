import os
import google.generativeai as genai
from tools import run_shell, notify, get_clipboard, set_clipboard, hyprctl_command

# Initialize the API Key on module load
api_key = os.getenv("GEMINI_API_KEY")
if api_key:
    genai.configure(api_key=api_key)

class AgentManager:
    def __init__(self):
        self.system_tools = [run_shell, notify, get_clipboard, set_clipboard, hyprctl_command]
        
        # Define the system agent (Friday Core)
        self.system_agent_model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            tools=self.system_tools,
            system_instruction="""
You are Friday (Female Replacement Intelligent Digital Assistant Youth), a highly advanced system-level AI assistant for an Arch Linux user running Wayland/Hyprland.
You have access to tools that can read/write the clipboard, send notifications, run shell commands, and control Hyprland.
Keep your text responses extremely concise, intuitive, and highly efficient.
"""
        )
        
        # Define a pure chat/research agent (no system modification tools)
        self.research_agent_model = genai.GenerativeModel(
            model_name="gemini-1.5-pro",
            system_instruction="""
You are Friday's Research Sub-system. Your job is to answer questions, analyze text, and provide information without modifying the user's system state.
Be concise and helpful.
"""
        )
        
        # Store active chat sessions
        self.chats = {
            "system": self.system_agent_model.start_chat(enable_automatic_function_calling=True),
            "research": self.research_agent_model.start_chat(enable_automatic_function_calling=True)
        }

    def process_message(self, agent_type: str, message: str) -> str:
        """Sends a message to the specified agent type and returns the response."""
        if not api_key:
            return "Error: GEMINI_API_KEY environment variable is not set."
            
        chat = self.chats.get(agent_type, self.chats["system"])
        try:
            response = chat.send_message(message)
            return response.text
        except Exception as e:
            return f"Error from {agent_type} agent: {str(e)}"

# Global instance for the server to use
agent_manager = AgentManager()
