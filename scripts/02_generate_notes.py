import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError


class Note(BaseModel):
    id: int = Field(..., ge=1, le=10,
                    description="Note identifier from 1 to 10")
    heading: str = Field(..., description="Title or heading of the note")
    summary: str = Field(..., max_length=150,
                         description="Concise summary up to 150 characters")
    page_ref: int | None = Field(
        None, 
        ge=1, 
        description="Page number in source PDF or null if uncertain"
    )

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("Please set OPENAI_API_KEY in your .env file")

client = OpenAI(api_key=api_key)


if not os.path.exists(".assistant_id"):
    raise FileNotFoundError(
        ".assistant_id not found. Please run 00_bootstrap.py first to create and configure the assistant."
    )
assistant_id = open(".assistant_id").read().strip()


run_instructions = (
    "You are a study summarizer. Your task is to generate exactly 10 unique revision notes "
    "based *exclusively* on the content of the document(s) associated with your file_search tool. "
    "Do not use any external knowledge. "
    "Each note must strictly follow the Note schema: id (integer from 1 to 10), heading (string), "
    "summary (string, max 150 characters), and page_ref (integer page number from the document if available, otherwise null). "
    
    "For page_ref: Only include a page number if you can definitively identify it from the document content. "
    "Look for actual page numbers printed on the pages, not estimated locations. "
    "If uncertain about the exact page number, set page_ref to null. "
    "Prioritize accuracy over completeness for page references. "
    
    "Respond *only* with a single valid JSON object matching the schema: { \"notes\": [ ... ] }. "
    "Do not wrap the JSON in Markdown code fences or any other surrounding text. " 
    "If you cannot find enough distinct information for 10 notes from the document, clearly state this limitation "
    "but still try to provide as many as possible up to 10, ensuring they are from the document."
)


user_message_content = (
    "Please generate 10 exam revision notes from the provided course material. "
    "Focus on key concepts, definitions, and important facts found within the document."
)

print(f"Creating thread with user message: '{user_message_content}'")
thread = client.beta.threads.create(
    messages=[
        {
            "role": "user",
            "content": user_message_content,
        }
    ]
)
print(f"Thread created: {thread.id}")

print(
    f"Creating and polling run for thread {thread.id} with assistant {assistant_id}...")
run = client.beta.threads.runs.create_and_poll(
    thread_id=thread.id,
    assistant_id=assistant_id,
    instructions=run_instructions
)
print(f"Run status: {run.status}")

if run.status != "completed":
    print(f"Run failed. Details: {run.last_error}")
    print(f"Run steps:")
    run_steps = client.beta.threads.runs.steps.list(
        thread_id=thread.id, run_id=run.id, limit=10)
    for step in reversed(run_steps.data):
        print(
            f"  Step ID: {step.id}, Type: {step.type}, Status: {step.status}")
        if step.step_details:
            print(f"    Details: {step.step_details}")
        if step.last_error:
            print(f"    Error: {step.last_error}")
    raise RuntimeError(
        f"Thread run failed with status: {run.status}. Last error: {run.last_error}")

print("Run completed. Fetching messages...")
messages = client.beta.threads.messages.list(thread_id=thread.id, order="asc")

assistant_response_content = None
for msg in reversed(messages.data):
    if msg.role == "assistant":
        if msg.content and isinstance(msg.content, list) and len(msg.content) > 0:
            if hasattr(msg.content[0], 'text') and msg.content[0].text:
                assistant_response_content = msg.content[0].text.value
                break

if not assistant_response_content:
    print("No assistant text response found.")
    raise RuntimeError("Assistant did not provide a usable text response.")

print(f"Raw assistant response:\n{assistant_response_content}")
json_str_to_parse = assistant_response_content.strip()

if json_str_to_parse.startswith("```json"):
    json_str_to_parse = json_str_to_parse[len("```json"):].strip()
elif json_str_to_parse.startswith("```"):
    json_str_to_parse = json_str_to_parse[len("```"):].strip()

if json_str_to_parse.endswith("```"):
    json_str_to_parse = json_str_to_parse[:-len("```")].strip()


try:
    data = json.loads(json_str_to_parse)
    notes_list = data.get("notes", [])
except json.JSONDecodeError as e:
    print(f"Failed to decode JSON from assistant response: {e}")
    print(f"Attempted to parse: {json_str_to_parse}")
    print("Ensure the assistant is configured to ONLY output valid JSON as specified in instructions.")
    raise SystemExit(1)

validated_notes = []
errors_validation = []
for item_idx, item in enumerate(notes_list):
    try:
        note = Note(**item)
        validated_notes.append(note)
    except ValidationError as e:
        print(f"Validation error for item {item_idx}: {item}")
        errors_validation.append(e)

if errors_validation:
    print("Pydantic Validation errors:")
    for err_idx, err in enumerate(errors_validation):
        print(f"Error {err_idx}: {err.errors()}")
    raise SystemExit("Validation errors occurred. Output not saved.")

if not validated_notes:
    print("No notes were successfully validated. Output not saved.")
    raise SystemExit(1)

if len(validated_notes) != 10:
    print(
        f"Warning: Expected 10 notes, but received {len(validated_notes)}. Continuing with received notes.")
    if len(validated_notes) == 0: 
        print("No notes were generated. Please check the input document and assistant's ability to extract information.")
        raise SystemExit("No notes generated.")


output_file = "exam_notes.json"
output_data = {"notes": [note.model_dump() for note in validated_notes]}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, ensure_ascii=False, indent=2)

print(f"Saved {len(validated_notes)} validated notes to {output_file}")