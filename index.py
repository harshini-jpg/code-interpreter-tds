import os
import sys
import json
import traceback
from typing import List
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from io import StringIO

app = FastAPI()

# Enable CORS for verification checks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeRequest(BaseModel):
    code: str

class CodeResponse(BaseModel):
    error: List[int]
    result: str

def execute_python_code(code: str) -> dict:
    old_stdout = sys.stdout
    sys.stdout = StringIO()
    try:
        exec(code, {})
        output = sys.stdout.getvalue()
        return {"success": True, "output": output}
    except Exception as e:
        output = traceback.format_exc()
        return {"success": False, "output": output}
    finally:
        sys.stdout = old_stdout

def analyze_error_with_ai(code: str, tb_text: str) -> List[int]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return []
        
    from google import genai
    from google.genai import types
    
    client = genai.Client(api_key=api_key)
    prompt = f"Analyze this Python code and its error traceback.\nIdentify the exact line number(s) where the error occurred.\n\nCODE:\n{code}\n\nTRACEBACK:\n{tb_text}\n\nReturn the line number(s) where the error is located."

    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash-exp',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "error_lines": types.Schema(
                            type=types.Type.ARRAY,
                            items=types.Schema(type=types.Type.INTEGER)
                        )
                    },
                    required=["error_lines"]
                )
            )
        )
        data = json.loads(response.text)
        return data.get("error_lines", [])
    except Exception:
        return []

@app.post("/code-interpreter", response_model=CodeResponse)
async def code_interpreter(request: CodeRequest):
    exec_result = execute_python_code(request.code)
    if exec_result["success"]:
        return CodeResponse(error=[], result=exec_result["output"])
    
    error_lines = analyze_error_with_ai(request.code, exec_result["output"])
    return CodeResponse(error=error_lines, result=exec_result["output"])
