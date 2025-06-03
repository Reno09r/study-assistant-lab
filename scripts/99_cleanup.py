import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Please set OPENAI_API_KEY in your .env file")

client = OpenAI(api_key=api_key)

print("Listing files...")
files = client.files.list().data
for f in files:
    if f.purpose == "assistants":
        try:
            client.files.delete(f.id)
            print(f"Deleted file: {f.id} (name={f.filename})")
        except Exception as e:
            print(f"Error deleting file {f.id}: {e}")

print("Listing assistants...")
assists = client.beta.assistants.list().data
for a in assists:
    if "study q&a" in a.name.lower():
        try:
            client.beta.assistants.delete(a.id)
            print(f"Deleted assistant: {a.id} (name={a.name})")
        except Exception as e:
            print(f"Error deleting assistant {a.id}: {e}")

print("Cleanup complete.")