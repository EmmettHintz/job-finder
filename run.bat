@echo off
:: Activate the virtual environment
call venv\Scripts\activate.bat

:: Set the OpenAI API key if provided as an argument
if not "%~1"=="" (
  set OPENAI_API_KEY=%~1
)

:: Run the job finder script
python job_finder.py

:: Deactivate the virtual environment
call deactivate 