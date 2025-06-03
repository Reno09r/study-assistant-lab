import os
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Please set OPENAI_API_KEY in your .env file")

if not os.path.exists(".assistant_id"):
    raise FileNotFoundError(
        ".assistant_id not found. Please run 00_bootstrap.py first.")
assistant_id = open(".assistant_id").read().strip()

client = OpenAI(api_key=api_key)

GENERAL_QUESTIONS = [
    "hello", "hi",
    "who are you", "what are you", "how are you", "introduce yourself"
]

def is_general_question(question):
    question_lower = question.lower().strip()
    return any(keyword in question_lower for keyword in GENERAL_QUESTIONS)

print("Welcome to the Study Q&A Assistant. Type 'exit' to quit.")
while True:
    question = input("\nYour question: ")
    if question.lower() in ("exit", "quit"):
        print("Goodbye!")
        break
    
    if is_general_question(question):
        instructions = """You are a helpful study assistant. For general questions about yourself, 
        respond naturally without searching documents. For study-related questions, use the file_search 
        tool to find relevant information from uploaded documents and provide citations."""
        
        content = question
    else:
        instructions = """Use the file_search tool to find relevant information from the uploaded documents. 
        Always cite your sources and provide specific references. If the question cannot be answered from 
        the documents, say so clearly."""
        
        content = f"{question}\n\nPlease provide a comprehensive answer based on the uploaded documents and include specific citations."

    thread = client.beta.threads.create(
        messages=[{
            "role": "user",
            "content": content
        }]
    )

    run = client.beta.threads.runs.create_and_poll(
        thread_id=thread.id,
        assistant_id=assistant_id,
        instructions=instructions
    )

    if run.status == "completed":
        messages = client.beta.threads.messages.list(thread_id=thread.id)
        response = messages.data[0].content[0].text.value

        print("Assistant Response:")
        print(response)
        if hasattr(messages.data[0].content[0].text, 'annotations'):
            annotations = messages.data[0].content[0].text.annotations
            if annotations:
                print(f"\nCitations found: {len(annotations)}")
                for j, annotation in enumerate(annotations[:3], 1):
                    if hasattr(annotation, 'file_citation'):
                        print(f"  {j}. File: {annotation.file_citation.file_id}")

        steps = client.beta.threads.runs.steps.list(thread_id=thread.id, run_id=run.id)
        file_search_used = False

        for step in steps.data:
            if step.type == "tool_calls":
               for tool_call in step.step_details.tool_calls:
                    if tool_call.type == "file_search":
                        file_search_used = True
                        print("file_search tool was used")
                        break

        if not file_search_used:
            print("file_search tool was not used")
    else:
        print(f"Run failed with status: {run.status}")
        if hasattr(run, 'last_error') and run.last_error:
            print(f"Error: {run.last_error}")