import asyncio
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from mcp import Client
from openai import OpenAI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY is not configured.")

OPENAI_MODEL = "gpt-5.6"
MCP_URL = "http://127.0.0.1:8002/mcp"
MAX_TOOL_ROUNDS = 5

openai_client = OpenAI(api_key=API_KEY)

app = FastAPI(
    title="SharePoint AI Agent Backend",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://calsawsproject",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    results: list[dict] = []
    

def get_tool_result(result) -> str:
    """Convert an MCP tool result into JSON text."""
    if result.is_error:
        raise RuntimeError("MCP tool execution failed.")

    structured_content = getattr(
        result,
        "structured_content",
        None,
    )

    if structured_content is not None:
        return json.dumps(
            structured_content,
            ensure_ascii=False,
            default=str,
        )

    text_parts = [
        item.text
        for item in result.content
        if hasattr(item, "text")
    ]

    return "\n".join(text_parts)


async def run_agent(question: str) -> tuple[str, list[dict]]:
    search_results = []
    
    async with Client(MCP_URL) as mcp_client:
        tool_result = await mcp_client.list_tools()
        mcp_tools = dict(tool_result)["tools"]

        # Map MCP tools to OpenAI function tools.
        supported_file_types = {"pdf", "docx", "xlsx"}

        openai_tools = []

        for tool in mcp_tools:
            if tool.name != "search_sharepoint":
                continue

            openai_tools.append({
                "type": "function",
                "name": tool.name,
                "description": (
                    "Search SharePoint for documents relevant to the user's question. "
                    "Return and use only the available search metadata: title, path, "
                    "snippet, file type, and search rank. Do not attempt to retrieve "
                    "or extract the full contents of documents."
                ),
                "parameters": tool.input_schema,
                "strict": False,
            })

        response = openai_client.responses.create(
            model=OPENAI_MODEL,
            instructions=(
                "You are a SharePoint search assistant. "
                "Use the search_sharepoint tool to find documents relevant to the user's question. "
                "Base your answer only on the search results returned by the tool, especially "
                "their titles, paths, and snippets. "
                "Do not claim to have read the full contents of any document. "
                "Do not invent facts that are not supported by the search results. "
                "If the snippets do not contain enough information to answer the question, "
                "say so clearly and provide links to potentially relevant documents. "
                "Include document titles and links whenever possible. "
                "Answer in the same language as the user's question."
            ),
            input=question,
            tools=openai_tools,
        )

        for _ in range(MAX_TOOL_ROUNDS):
            function_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            if not function_calls:
                return response.output_text, search_results
                
            tool_outputs = []

            for call in function_calls:
                print(f"MCP tool requested: {call.name}")

                try:
                    arguments = json.loads(call.arguments)
                    print(f"MCP tool arguments: {arguments}")

                    result = await mcp_client.call_tool(
                        call.name,
                        arguments,
                    )

                    output_text = get_tool_result(result)
                    
                    print("MCP output preview:")
                    print(output_text[:2000])
                    

                    if call.name == "search_sharepoint":
                        try:
                            parsed_results = json.loads(output_text)

                            # Unwrap the MCP result if it contains a JSON string.
                            if isinstance(parsed_results, dict) and "result" in parsed_results:
                                parsed_results = parsed_results["result"]

                            # Parse the nested JSON string.
                            if isinstance(parsed_results, str):
                                parsed_results = json.loads(parsed_results)

                            if isinstance(parsed_results, list):
                                search_results = parsed_results

                            elif isinstance(parsed_results, dict):
                                search_results = parsed_results.get("results", [])

                            print(
                                "Number of SharePoint results:",
                                len(search_results),
                            )

                        except json.JSONDecodeError as exc:
                            print("Could not parse SharePoint search results as JSON:", exc)
                            
                    print(
                        f"MCP tool completed: {call.name}; "
                        f"result length: {len(output_text)} characters"
                    )

                except Exception as exc:
                    output_text = json.dumps(
                        {
                            "error": (
                                f"Tool {call.name} failed: "
                                f"{type(exc).__name__}"
                            )
                        },
                        ensure_ascii=False,
                    )

                tool_outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": output_text,
                    }
                )

            response = openai_client.responses.create(
                model=OPENAI_MODEL,
                instructions=(
                    "Answer using the available tool results. "
                    "Do not invent facts or document contents. "
                    "Identify source documents by title and URL "
                    "when that information is available."
                ),
                previous_response_id=response.id,
                input=tool_outputs,
                tools=openai_tools,
            )

        raise RuntimeError(
            "The maximum number of tool-calling rounds was exceeded."
        )


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "SharePoint AI Agent Backend",
    }


@app.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=400,
            detail="Question must not be empty.",
        )

    try:
        answer, results = await run_agent(request.question)

        return AskResponse(
            answer=answer,
            results=results,
        )
        
    except Exception:
        raise HTTPException(
            status_code=502,
            detail=(
                "The AI agent failed to process the request. "
                "Check the backend console logs."
            ),
        )
