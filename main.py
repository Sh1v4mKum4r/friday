#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from agent import get_agent

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    print("Initializing Friday...")
    try:
        chat = get_agent()
        print("Friday is online. Type 'exit' to quit.")
        while True:
            try:
                user_input = input("\nYou: ")
                if user_input.lower() in ['exit', 'quit']:
                    break
                if not user_input.strip():
                    continue
                
                print("Friday is thinking...")
                response = chat.send_message(user_input)
                print(f"Friday: {response.text}")
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"\nError: {e}")
                
    except Exception as e:
        print(f"Failed to initialize: {e}")

if __name__ == "__main__":
    main()