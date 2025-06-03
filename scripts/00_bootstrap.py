import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Please set OPENAI_API_KEY in your .env file")

client = OpenAI(api_key=api_key)

assistant = client.beta.assistants.create(
    name="Study Q&A Assistant",
    instructions=(
        "You are a helpful tutor."
        "Use the knowledge in the attached files to answer questions."
        "Cite sources where possible."
    ),
    model="gpt-4o-mini",
    tools=[{"type": "file_search"}]
)
print(f"Created assistant with ID: {assistant.id}")

file_paths = ["data/james-stewart-calculus-early-transcendentals-7th-edition-2012-1-20ng7to-1ck11on.pdf"]
file_ids = []
for path in file_paths:
    with open(path, "rb") as f:
        file_obj = client.files.create(
            purpose="assistants",
            file=f
        )
    file_ids.append(file_obj.id)
    print(f"Uploaded {path} -> file_id: {file_obj.id}")


"""Create a vector store and add files to it."""
print("\nCreating vector store...")
    
vector_store = client.vector_stores.create(
    name="Tricks_Companies_Use_to_Manip",
)
    
print(f"Vector store created: {vector_store.id}")
file_batch = client.vector_stores.file_batches.create_and_poll(
    vector_store_id=vector_store.id,
    file_ids=file_ids
)
    
print(f"File batch status: {file_batch.status}")
print(f"Files processed: {file_batch.file_counts.completed}/{file_batch.file_counts.total}")

assistant = client.beta.assistants.update(
    assistant_id=assistant.id,
    tool_resources={
        "file_search": {
            "vector_store_ids": [vector_store.id]
        }
    }
)
print("Assistant updated with file_search resources.")

with open(".assistant_id", "w") as f:
    f.write(assistant.id)
print("Saved assistant ID to .assistant_id")


